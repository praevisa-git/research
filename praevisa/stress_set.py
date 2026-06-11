"""Stress set — adversarial robustness battery for the committed artifacts.

Four attacks, all read-only on the predictions (the ledger is append-only and this
module never writes into predictions/):

  A. ledger fragility   — for every item of the 2026-06-15 forward ledger, how much
                          error flips the predicted outcome. Deterministic levers
                          (uniform swing-to-flip, single-group defection, the ***II
                          coalition to 361) plus an empirical Monte Carlo: per-file
                          residual vectors from the historical record (committee rail:
                          plenary − prediction on the calibration pairs; prior rail:
                          plenary − LOO prior on the §9.6 test set) are resampled whole
                          (cluster bootstrap, cross-group correlation preserved) onto
                          the item's per-group prediction. flip_rate = share of draws
                          whose seat tally reverses the committed call.
  B. grading collisions — the pre-registered grader pairs identifier-less items by
                          title-token containment (>= 0.6). Scan the ledger against
                          itself for token sets that could collide or are too thin to
                          match, BEFORE the session, while overrides can still be
                          prepared.
  C. Stage A jackknife  — leave-one-pair-out on the post-audit Stage A rows: does the
                          sign of (committee loss − floor loss) survive every removal,
                          and what does an exact sign test say at n this small.
  D. §9.6 jackknife     — leave-one-file-out on the 18-file re-frozen set: is the
                          "baseline_A no longer edges const_mean" conclusion stable
                          against any single file's removal.

The committee-rail Monte Carlo needs the per-vote detail API once per calibration pair;
if offline, that subsection is reported as skipped and everything else still runs.

Run: uv run python -m praevisa.stress_set        # writes results/stress_set.json
"""

from __future__ import annotations

import json
import random
from itertools import combinations
from pathlib import Path

from . import baselines, ep_flip, plenary_forward as pf, resolve_plenary, stage_a

ROOT = Path(__file__).resolve().parent.parent
RESULTS_PATH = ROOT / "results" / "stress_set.json"
LEDGER_PATH = ROOT / "predictions" / f"plenary_{pf.SESSION}_forward.json"

GROUPS = list(baselines.CANONICAL_GROUPS)
SEATS = pf.SEATS
N_BOOT = 10_000
SEED = 0


# ---------------------------------------------------------------------------
# A. Forward-ledger fragility
# ---------------------------------------------------------------------------

def _tally(per_group: dict) -> tuple[float, float]:
    """Seat tally, ledger convention: abstention-ignored, NI excluded."""
    gyr = {g: (per_group.get(g) if per_group.get(g) is not None else 0.0) for g in GROUPS}
    yes = sum(SEATS[g] * gyr[g] for g in GROUPS if g != "NI")
    no = sum(SEATS[g] * (1.0 - gyr[g]) for g in GROUPS if g != "NI")
    return yes, no


def _seats_against_all(per_group: dict) -> float:
    """***II convention (matches pf._second_reading): every group counts, NI included."""
    return sum(SEATS[g] * (1.0 - (per_group.get(g) or 0.0)) for g in GROUPS)


def _prior_residuals() -> list[dict]:
    """Per-file residual vectors plenary − LOO baseline_A prior, over the §9.6 set."""
    records = baselines.load_testset()
    out = []
    for held in records:
        train = [r for r in records if r is not held]
        res = {}
        for g in GROUPS:
            y, p = held.yes_rates.get(g), baselines.baseline_a(train, g)
            if y is not None and p is not None:
                res[g] = y - p
        if res:
            out.append(res)
    return out


def _committee_residuals() -> list[dict] | None:
    """Per-file residual vectors plenary − prediction on the calibration pairs
    (identity map, alpha=1.0 as committed). Needs the detail API; None if offline."""
    try:
        index = resolve_plenary.load_index()
        pairs = stage_a.build_pairs(index)
    except Exception:
        return None
    if not pairs:
        return None
    prior = ep_flip._baseline_A()
    out = []
    for p in pairs:
        pred = ep_flip.predict_plenary_per_group(p["committee_yes"], prior, alpha=1.0)
        res = {}
        for g in GROUPS:
            y = p["plenary_yes"].get(g)
            if y is not None and pred.get(g) is not None:
                res[g] = y - pred[g]
        if res:
            out.append(res)
    return out


def _mc_flip_rate(item: dict, residuals: list[dict], rng: random.Random) -> float:
    """Cluster bootstrap: resample one historical residual vector per draw, apply it
    whole to the item's prediction, re-tally. Fraction of draws reversing the call."""
    base = item["per_group"]
    flips = 0
    for _ in range(N_BOOT):
        res = residuals[rng.randrange(len(residuals))]
        shocked = {g: (min(1.0, max(0.0, base[g] + res.get(g, 0.0)))
                       if base.get(g) is not None else None)
                   for g in GROUPS}
        if item.get("second_reading"):
            overturned = _seats_against_all(shocked) >= pf.ABS_MAJORITY
            predicted_stands = item["outcome"] == "ADOPTED"
            if overturned == predicted_stands:
                flips += 1
        else:
            yes, no = _tally(shocked)
            if ("ADOPTED" if yes > no else "REJECTED") != item["outcome"]:
                flips += 1
    return flips / N_BOOT


def _uniform_swing_to_flip(item: dict) -> float:
    """Uniform per-group yes-rate drop (in rate points) that levels the seat tally.
    For ***II: the uniform drop that pushes seats-against to the 361 threshold."""
    if item.get("second_reading"):
        deficit = pf.ABS_MAJORITY - item["second_reading"]["predicted_seats_against"]
        return deficit / sum(SEATS[g] for g in GROUPS)
    yes, no = _tally(item["per_group"])
    return (yes - no) / (2 * sum(SEATS[g] for g in GROUPS if g != "NI"))


def _single_group_flips(item: dict) -> list[str]:
    """Groups whose lone full defection (yes-rate -> 0) reverses the call."""
    out = []
    for g in GROUPS:
        if g == "NI" or item["per_group"].get(g) is None:
            continue
        shocked = dict(item["per_group"])
        shocked[g] = 0.0
        if item.get("second_reading"):
            flipped = _seats_against_all(shocked) >= pf.ABS_MAJORITY
        else:
            yes, no = _tally(shocked)
            flipped = ("ADOPTED" if yes > no else "REJECTED") != item["outcome"]
        if flipped:
            out.append(g)
    return out


def _min_coalition_to_361(item: dict) -> list[str] | None:
    """***II only: smallest set of groups whose full defection to 'against' crosses
    the Rule-68 threshold (everyone else votes as predicted)."""
    if not item.get("second_reading"):
        return None
    groups = [g for g in GROUPS if item["per_group"].get(g) is not None]
    for k in range(1, len(groups) + 1):
        best = None
        for combo in combinations(groups, k):
            shocked = dict(item["per_group"])
            for g in combo:
                shocked[g] = 0.0
            if _seats_against_all(shocked) >= pf.ABS_MAJORITY:
                if best is None or sum(SEATS[g] for g in combo) < sum(
                        SEATS[g] for g in best):
                    best = combo
        if best:
            return list(best)
    return None


def ledger_fragility(ledger: dict) -> dict:
    rng = random.Random(SEED)
    prior_res = _prior_residuals()
    com_res = _committee_residuals()
    items = []
    for it in ledger["items"]:
        on_committee_rail = it["signal"] != "prior"
        residuals = (com_res if on_committee_rail else prior_res)
        entry = {
            "a10": it["a10"], "title": it["title"][:60], "signal": it["signal"],
            "contested": it.get("contested"), "outcome": it["outcome"],
            "ep_yes_share": it.get("ep_yes_share"),
            "uniform_swing_to_flip_pp": round(100 * _uniform_swing_to_flip(it), 2),
            "single_group_full_defection_flips": _single_group_flips(it),
            "mc_flip_rate": (round(_mc_flip_rate(it, residuals, rng), 4)
                             if residuals else None),
            "mc_residual_pool": ("committee-rail calibration pairs" if on_committee_rail
                                 else "§9.6 prior residuals (LOO)")
                                + ("" if residuals else " — UNAVAILABLE (offline?)"),
        }
        coalition = _min_coalition_to_361(it)
        if coalition is not None:
            entry["min_coalition_to_361"] = coalition
        items.append(entry)
    caveat = ("prior-rail flip rates inherit the §9.6 base-rate mix (4/18 files "
              "REJECTED, all COD): they read as 'how often the topic-blind prior call "
              "reversed on historical legislative files', an upper bound for routine "
              "ini/cns items. Committee-rail pools resample whole per-file residual "
              "vectors, so cross-group correlation is preserved but n_files is small.")
    return {"n_boot": N_BOOT, "seed": SEED,
            "n_residual_files": {"prior": len(prior_res),
                                 "committee": len(com_res) if com_res else None},
            "caveat": caveat, "items": items}


# ---------------------------------------------------------------------------
# B. Grading-collision scan
# ---------------------------------------------------------------------------

def grading_collisions(ledger: dict) -> dict:
    """The grader pairs by procedure, then A10 reference, then title tokens. Items with
    neither identifier live or die on _tokens(); scan for intra-ledger ambiguity."""
    items = ledger["items"]
    toks = [pf._tokens(it["title"]) for it in items]
    title_paired = [not (it.get("procedure") or it.get("a10")) for it in items]
    findings = []
    for i, it in enumerate(items):
        if title_paired[i] and len(toks[i]) < 5:
            findings.append({"kind": "thin-token-set", "item": it["title"][:60],
                             "n_tokens": len(toks[i]),
                             "risk": "one stray word in HTV's title wording can drop "
                                     "containment below 0.6 -> item stuck pending"})
    for i, j in combinations(range(len(items)), 2):
        if not (title_paired[i] or title_paired[j]):
            continue
        if not toks[i] or not toks[j]:
            continue
        ov = max(len(toks[i] & toks[j]) / len(toks[i]),
                 len(toks[i] & toks[j]) / len(toks[j]))
        if ov >= 0.45:
            findings.append({
                "kind": "collision" if ov >= pf.MATCH_THRESHOLD else "near-collision",
                "overlap": round(ov, 2),
                "item_a": items[i]["title"][:60], "item_b": items[j]["title"][:60],
                "risk": "both could containment-match the same session row; the "
                        "double-pairing guard parks the loser as pending until a "
                        "vote_id override is added to the results file",
            })
    return {"match_threshold": pf.MATCH_THRESHOLD,
            "n_title_paired_items": sum(title_paired), "findings": findings}


# ---------------------------------------------------------------------------
# C. Stage A jackknife (post-audit rows)
# ---------------------------------------------------------------------------

def _jackknife(diffs: list[float]) -> dict:
    n = len(diffs)
    full = sum(diffs) / n
    loo = [sum(d for j, d in enumerate(diffs) if j != i) / (n - 1) for i in range(n)]
    wins = sum(1 for d in diffs if d < 0)
    # exact two-sided sign test, ties (d == 0) dropped
    m = sum(1 for d in diffs if d != 0)
    k = min(wins, m - wins)
    from math import comb
    p = min(1.0, 2 * sum(comb(m, t) for t in range(k + 1)) / 2 ** m) if m else None
    return {"n": n, "mean_diff": round(full, 4), "model_wins": wins,
            "loo_mean_range": [round(min(loo), 4), round(max(loo), 4)],
            "loo_sign_flips": sum(1 for v in loo if (v < 0) != (full < 0)),
            "sign_test_p": round(p, 4) if p is not None else None}


def stage_a_jackknife() -> dict:
    rows = json.loads((ROOT / "results" / "stage_a.json").read_text())["rows"]
    out = {}
    for floor in ("const_mean", "baseline_A"):
        diffs_all = [r["loss_committee"] - r[f"loss_{floor}"] for r in rows]
        diffs_ctd = [r["loss_committee"] - r[f"loss_{floor}"]
                     for r in rows if r["contested"]]
        out[f"vs_{floor}"] = {"all_pairs": _jackknife(diffs_all),
                              "contested": _jackknife(diffs_ctd)}
    out["note"] = ("negative mean_diff = committee signal beats the floor. "
                   "loo_sign_flips > 0 means one pair's removal reverses the headline "
                   "direction — at post-audit n, expect fragility, and say so.")
    return out


# ---------------------------------------------------------------------------
# D. §9.6 baseline jackknife
# ---------------------------------------------------------------------------

def baseline_jackknife() -> dict:
    """LOO per-file errors for baseline_A vs const_mean (the §9.6 protocol), then
    jackknife the 'A no longer edges const_mean' headline over file removals."""
    records = baselines.load_testset()
    diffs = []
    per_file = []
    for held in records:
        train = [r for r in records if r is not held]
        cm = baselines.const_mean(train)
        ea, em, n = 0.0, 0.0, 0
        for g in GROUPS:
            y = held.yes_rates.get(g)
            a = baselines.baseline_a(train, g)
            if y is None or a is None or cm is None:
                continue
            ea += (a - y) ** 2
            em += (cm - y) ** 2
            n += 1
        diffs.append(ea / n - em / n)
        per_file.append({"reference": held.reference, "diff_A_minus_const":
                         round(ea / n - em / n, 4)})
    jk = _jackknife(diffs)
    return {**jk, "per_file": per_file,
            "headline": ("'baseline_A behind const_mean' is single-file-stable"
                         if jk["loo_sign_flips"] == 0 else
                         f"headline sign reverses under {jk['loo_sign_flips']} of "
                         f"{jk['n']} single-file removals — report as indistinguishable,"
                         " never as a ranking")}


# ---------------------------------------------------------------------------

def main() -> int:
    ledger = json.loads(LEDGER_PATH.read_text())
    out = {
        "protocol": "stress set over committed artifacts; ledger read-only",
        "ledger_rev": ledger["engine_rev"], "ledger_generated": ledger["generated_at"],
        "A_ledger_fragility": ledger_fragility(ledger),
        "B_grading_collisions": grading_collisions(ledger),
        "C_stage_a_jackknife": stage_a_jackknife(),
        "D_baseline_96_jackknife": baseline_jackknife(),
    }
    RESULTS_PATH.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")

    frag = out["A_ledger_fragility"]
    print(f"STRESS SET — ledger {ledger['session_dates']} @ {ledger['engine_rev']}\n")
    print(f"A. fragility (MC n={frag['n_boot']}, residual files: {frag['n_residual_files']})")
    ranked = sorted(frag["items"], key=lambda e: -(e["mc_flip_rate"] or 0))
    for e in ranked[:8]:
        fr = "n/a " if e["mc_flip_rate"] is None else f"{e['mc_flip_rate']:.1%}"
        print(f"  flip {fr:>6}  swing {e['uniform_swing_to_flip_pp']:>5.1f}pp  "
              f"{e['signal']:<22} {e['title'][:46]}")
    col = out["B_grading_collisions"]
    print(f"\nB. grading: {col['n_title_paired_items']} items pair by title; "
          f"{len(col['findings'])} flagged")
    for f in col["findings"]:
        what = f.get("item") or f"{f['item_a'][:34]} <-> {f['item_b'][:34]}"
        print(f"  [{f['kind']}] {what}"
              + (f" (overlap {f['overlap']})" if "overlap" in f else ""))
    sa = out["C_stage_a_jackknife"]
    for floor in ("vs_const_mean", "vs_baseline_A"):
        c = sa[floor]["contested"]
        print(f"\nC. Stage A {floor} contested: n={c['n']} mean_diff={c['mean_diff']} "
              f"LOO range {c['loo_mean_range']} sign flips {c['loo_sign_flips']} "
              f"sign-test p={c['sign_test_p']}")
    bj = out["D_baseline_96_jackknife"]
    print(f"\nD. §9.6 A−const_mean: mean {bj['mean_diff']:+.4f}, LOO range "
          f"{bj['loo_mean_range']}, sign flips {bj['loo_sign_flips']}/{bj['n']}")
    print(f"   {bj['headline']}")
    print(f"\nwrote {RESULTS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
