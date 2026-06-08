"""Stage A — pseudo-prospective backtest of the committee->plenary signal.

THE question the whole wedge rests on: on CONTESTED first-reading files, does a group's
pre-vote COMMITTEE vote predict its PLENARY yes-rate better than the §9.6 floors
(const_mean, baseline_A)? Stage 0 proved the data pairs exist; this grades the signal.

Design (time-split, pseudo-prospective — Stage A of the plan):
  * Targets: the Stage-0 usable pairs (committee per-group signal + plenary outcome),
    reported on the CONTESTED subset (the real question) and on all pairs (for power).
  * For each target's plenary per-group yes-rate vector, three predictors:
      - const_mean  : one pooled scalar, mean of the historical base (the §9.6 floor)
      - baseline_A  : per-group historical mean (the §9.6 per-group predictor)
      - committee   : the committee's per-group yes-rate on THIS file (the pre-vote,
                      file-specific signal — the thing being tested)
  * TIME-SPLIT: const_mean / baseline_A are fit ONLY on §9.6 base files with a plenary
    date strictly BEFORE the target's plenary date (and never the target itself). The
    committee vote is, by procedure, cast before the plenary vote — legitimately
    pre-vote. So no predictor sees the target or its future.
  * Metric: per-group squared error, averaged over the groups defined for all three
    predictors (same cells graded for each, for a fair paired comparison). Paired
    committee-vs-floor differences get a bootstrap CI + Wilcoxon, exactly as §5b.

CAVEATS baked into the output: (1) n is tiny (esp. contested) — non-significance is the
expected default; a clean direction matters more than a p-value here. (2) Some contested
signals are provisional-agreement (consensus) stage, a weaker cue (Stage 0). (3) This is
pseudo-prospective (historical data, time-split), NOT pre-committed — Stage B is.

Reproduce (network: resolves plenary ids + per-group via HTV; bulk CSV cached):

    uv run python -m praevisa.stage_a
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy import stats

from . import baselines, resolve_plenary, stage0_feasibility as s0

RESULTS_PATH = Path(__file__).resolve().parent.parent / "results" / "stage_a.json"
GROUPS = list(baselines.CANONICAL_GROUPS)
MIN_TRAIN = 8        # need a reasonable historical base for a fold
SEED, N_BOOT = 0, 10_000


def _date_of(ref, index):
    row = resolve_plenary.resolve_first_reading(ref, index)
    return (row["timestamp"][:10] if row else None), (row["id"] if row else None)


def build_base(index):
    """Historical base = the frozen §9.6 22-file set: {id, date, yes:{g:rate}}."""
    base = []
    for r in baselines.load_testset():
        date, vid = _date_of(r.reference, index)
        base.append({"id": str(vid), "date": date or "", "ref": r.reference,
                     "yes": dict(r.yes_rates)})
    return base


def build_pairs(index):
    """Stage-0 pairs with both sides as per-canonical-group yes-rates."""
    committee = s0.load_committee_cod()
    pairs = []
    for proc, rec in sorted(committee.items()):
        row = resolve_plenary.resolve_first_reading(proc, index)
        if row is None:
            continue
        bg = resolve_plenary.fetch_by_group(row["id"])
        if not bg:
            continue
        plen_yes = {g: baselines._yes_rate(s) for g, s in bg.items()}
        com_yes = s0._committee_group_rates(rec["votes"])
        yes_overall, _n = s0._committee_yes(rec)
        pairs.append({
            "procedure": proc, "committee": rec["committee"], "stage": rec.get("_stage"),
            "plenary_id": str(row["id"]), "date": row["timestamp"][:10],
            "contested": bool(yes_overall is not None and yes_overall < s0.CONTESTED_MAX_YES),
            "committee_yes": com_yes, "plenary_yes": plen_yes,
        })
    return pairs


def _floors(base, target_date, target_id):
    """Time-split const_mean (scalar) and baseline_A (per-group) from pre-target base."""
    train = [b for b in base if b["date"] and b["date"] < target_date and b["id"] != target_id]
    if len(train) < MIN_TRAIN:
        return None, None, len(train)
    all_cells = [v for b in train for v in b["yes"].values() if v is not None]
    const_mean = sum(all_cells) / len(all_cells)
    base_a = {}
    for g in GROUPS:
        vals = [b["yes"][g] for b in train if b["yes"].get(g) is not None]
        base_a[g] = (sum(vals) / len(vals)) if vals else None
    return const_mean, base_a, len(train)


def _loss(pred_fn, pair, graded):
    se = [(pred_fn(g) - pair["plenary_yes"][g]) ** 2 for g in graded]
    return sum(se) / len(se)


def evaluate(pairs, base):
    rows = []
    for p in pairs:
        cm, ba, ntrain = _floors(base, p["date"], p["plenary_id"])
        if cm is None:
            continue
        # cells graded for ALL predictors: observed, committee signal, baseline_A defined
        graded = [g for g in GROUPS
                  if p["plenary_yes"].get(g) is not None
                  and p["committee_yes"].get(g) is not None
                  and ba.get(g) is not None]
        if len(graded) < 5:
            continue
        rows.append({
            "procedure": p["procedure"], "committee": p["committee"], "stage": p["stage"],
            "plenary_id": p["plenary_id"], "date": p["date"], "contested": p["contested"],
            "n_groups": len(graded), "n_train": ntrain,
            "loss_committee": _loss(lambda g: p["committee_yes"][g], p, graded),
            "loss_const_mean": _loss(lambda g: cm, p, graded),
            "loss_baseline_A": _loss(lambda g: ba[g], p, graded),
        })
    return rows


def _paired(rows, key_model, key_floor):
    """Paired model-vs-floor over `rows`. Negative mean_diff = model BETTER."""
    d = np.array([r[key_model] - r[key_floor] for r in rows])
    n = len(d)
    if n == 0:
        return None
    rng = np.random.default_rng(SEED)
    boot = d[rng.integers(0, n, size=(N_BOOT, n))].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    nz = int(np.count_nonzero(d))
    wp = float(stats.wilcoxon(d).pvalue) if (n >= 6 and nz >= 6) else None
    return {
        "n": n,
        "mean_model": float(np.mean([r[key_model] for r in rows])),
        "mean_floor": float(np.mean([r[key_floor] for r in rows])),
        "mean_diff": float(np.mean(d)),
        "mean_diff_ci95": [float(lo), float(hi)],
        "model_better_fraction": float(np.mean(boot < 0)),
        "wilcoxon_p": wp,
        "model_wins": bool(hi < 0 and wp is not None and wp < 0.05),
    }


def main():
    index = resolve_plenary.load_index()
    base = build_base(index)
    pairs = build_pairs(index)
    rows = evaluate(pairs, base)
    contested = [r for r in rows if r["contested"]]

    out = {"protocol": "time-split pseudo-prospective; committee signal vs §9.6 floors",
           "n_pairs_graded": len(rows), "n_contested": len(contested),
           "subsets": {}}
    for label, subset in [("contested", contested), ("all_pairs", rows)]:
        out["subsets"][label] = {
            "vs_const_mean": _paired(subset, "loss_committee", "loss_const_mean"),
            "vs_baseline_A": _paired(subset, "loss_committee", "loss_baseline_A"),
        }
    out["rows"] = rows

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=1))

    print("STAGE A — committee->plenary signal vs the §9.6 floors "
          "(time-split, pseudo-prospective)\n")
    print(f"{'procedure':16s}{'cmte':5s}{'stage':>12s}{'ctd':>5s}{'grp':>4s}"
          f"{'committee':>10s}{'const_mean':>11s}{'base_A':>9s}")
    print("-" * 72)
    for r in sorted(rows, key=lambda r: (not r["contested"], r["date"])):
        print(f"{r['procedure']:16s}{r['committee']:5s}{str(r['stage']):>12s}"
              f"{('YES' if r['contested'] else '-'):>5s}{r['n_groups']:>4d}"
              f"{r['loss_committee']:>10.4f}{r['loss_const_mean']:>11.4f}"
              f"{r['loss_baseline_A']:>9.4f}")

    for label in ("contested", "all_pairs"):
        print(f"\n[{label}]  committee signal vs floors (negative mean_diff = committee BETTER):")
        for floor in ("vs_const_mean", "vs_baseline_A"):
            v = out["subsets"][label][floor]
            if not v:
                continue
            lo, hi = v["mean_diff_ci95"]
            wp = "  n<6" if v["wilcoxon_p"] is None else f"{v['wilcoxon_p']:.3f}"
            print(f"  {floor:14s} n={v['n']:2d}  committee={v['mean_model']:.4f} "
                  f"floor={v['mean_floor']:.4f}  diff={v['mean_diff']:+.4f} "
                  f"CI[{lo:+.4f},{hi:+.4f}]  winfrac={v['model_better_fraction']:.2f}  "
                  f"p={wp}  wins={v['model_wins']}")
    print(f"\nwritten: {RESULTS_PATH}")
    return out


if __name__ == "__main__":
    main()
