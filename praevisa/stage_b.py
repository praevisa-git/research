"""Stage B — true pre-committed, blinded prospective test of the committee->plenary signal.

Stage A was pseudo-prospective (historical, time-split) and gave a first positive
signal on n=10. Stage B removes the last escape hatch: predictions are committed to git
BEFORE the plenary vote happens, so they cannot be retrofitted. This is the §9.6 / v2
blinding protocol applied for real.

How it works:
  predict  — find COD files that have a committee per-group vote but NO plenary
             first-reading vote yet (pending; resolver-confirmed). For each, write an
             immutable prediction to the append-only ledger predictions/stage_b_ledger.json:
               * model       = committee per-group yes-rate (Stage A's winning signal)
               * comparators = the §9.6 floors const_mean & baseline_A (from the frozen
                               22-file base) — so grading later is model-vs-floor
               * derived     = seat-weighted predicted EP yes-share + pass/fail
             plus a content hash (tamper-evidence) and the commit date. NO outcome is
             present (it does not exist yet). COMMIT THE LEDGER TO GIT NOW — the git
             history is the actual proof of pre-commitment; the hash is secondary.
  grade    — for ledger entries whose plenary vote now EXISTS and is dated strictly
             after the commit date, fetch the per-group outcome and score model vs
             floors. Refuses to grade a vote not strictly after the commit date (that
             would not be a prospective prediction).
  verify   — recompute every entry's content hash; flag any tampering.
  status   — summarise pending vs graded, model-vs-floor, and the CONTESTED-pending count
             (the binding metric for whether prospective contested evidence is accruing).
  report   — write results/stage_b_report.md: a legible prospective scoreboard (graded
             track record vs floors, pending queue, contested counts) for review.

Integrity rules enforced in code:
  - an entry is written ONCE; predict never re-predicts a procedure already in the ledger
    (no peeking / no swapping a prediction after the fact);
  - grade only scores plenary votes dated AFTER the commit date;
  - the hash covers the prediction fields only (not the later grade).

Run:
    uv run python -m praevisa.stage_b predict   # then: git add/commit the ledger
    uv run python -m praevisa.stage_b grade      # after plenary votes happen
    uv run python -m praevisa.stage_b status
    uv run python -m praevisa.stage_b verify
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

from . import baselines, resolve_plenary, stage0_feasibility as s0

LEDGER = Path(__file__).resolve().parent.parent / "predictions" / "stage_b_ledger.json"
GROUPS = list(baselines.CANONICAL_GROUPS)
SEAT_W = baselines.SEAT_WEIGHTS

# fields that are frozen at prediction time and covered by the content hash
HASH_FIELDS = ("procedure", "committee", "signal_stage", "committee_per_group",
               "predicted_plenary_per_group", "predicted_ep_yes_share",
               "predicted_outcome", "comparator_const_mean", "comparator_baseline_A",
               "committed_at")


def _today() -> str:
    return datetime.date.today().isoformat()


def _hash(entry: dict) -> str:
    payload = {k: entry[k] for k in HASH_FIELDS}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _load() -> list[dict]:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return []


def _save(ledger: list[dict]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False))


def _floors():
    """§9.6 floors from the frozen 22-file base: pooled const_mean + per-group baseline_A."""
    base = baselines.load_testset()
    cells = [v for r in base for v in r.yes_rates.values() if v is not None]
    const_mean = sum(cells) / len(cells)
    base_a = {}
    for g in GROUPS:
        vals = [r.yes_rates[g] for r in base if r.yes_rates[g] is not None]
        base_a[g] = (sum(vals) / len(vals)) if vals else None
    return round(const_mean, 6), {g: (round(v, 6) if v is not None else None)
                                  for g, v in base_a.items()}


def _ep_share(per_group: dict) -> float:
    num = den = 0.0
    for g in GROUPS:
        v = per_group.get(g)
        if v is None:
            continue
        num += SEAT_W[g] * v
        den += SEAT_W[g]
    return num / den if den else float("nan")


def predict() -> None:
    index = resolve_plenary.load_index()
    const_mean, base_a = _floors()
    committee = s0.load_committee_cod()
    ledger = _load()
    seen = {e["procedure"] for e in ledger}
    today = _today()

    added = []
    for proc, rec in sorted(committee.items()):
        if proc in seen:
            continue                                   # never re-predict (no peeking)
        if resolve_plenary.resolve_first_reading(proc, index) is not None:
            continue                                   # plenary already happened — not prospective
        com = {g: (round(v, 6) if v is not None else None)
               for g, v in s0._committee_group_rates(rec["votes"]).items()}
        if sum(1 for v in com.values() if v is not None) < 5:
            continue
        yes_overall, n = s0._committee_yes(rec)
        model = dict(com)                              # model: plenary ≈ committee per-group
        share = _ep_share(model)
        entry = {
            "procedure": proc, "committee": rec["committee"],
            "signal_stage": rec.get("_stage"), "committee_n": n,
            "committee_yes_overall": round(yes_overall, 4) if yes_overall is not None else None,
            "contested_ex_ante": bool(yes_overall is not None and yes_overall < s0.CONTESTED_MAX_YES),
            "committee_per_group": com,
            "predicted_plenary_per_group": model,
            "predicted_ep_yes_share": round(share, 4),
            "predicted_outcome": "ADOPTED" if share > 0.5 else "REJECTED",
            "comparator_const_mean": const_mean,
            "comparator_baseline_A": base_a,
            "committed_at": today,
            "plenary_status": "pending",
            "graded": None,
        }
        entry["content_hash"] = _hash(entry)
        added.append(entry)

    ledger.extend(added)
    _save(ledger)
    nc = sum(e["contested_ex_ante"] for e in added)
    print(f"predict: +{len(added)} new pending predictions ({nc} contested); "
          f"ledger now {len(ledger)} entries.")
    for e in added:
        print(f"  + {e['procedure']:16s} {e['committee']:5s} {str(e['signal_stage']):11s} "
              f"cmte_yes={e['committee_yes_overall']}  pred={e['predicted_outcome']} "
              f"({e['predicted_ep_yes_share']:.2f}){'  CONTESTED' if e['contested_ex_ante'] else ''}")
    if added:
        print("\n>>> COMMIT predictions/stage_b_ledger.json TO GIT NOW (before the plenary votes).")


def _mse(pred, observed, groups):
    return sum((pred[g] - observed[g]) ** 2 for g in groups) / len(groups)


def grade() -> None:
    index = resolve_plenary.load_index()
    ledger = _load()
    today = _today()
    n_new = 0
    for e in ledger:
        if e.get("graded"):
            continue
        row = resolve_plenary.resolve_first_reading(e["procedure"], index)
        if row is None:
            continue                                   # still pending
        plen_date = row["timestamp"][:10]
        if plen_date <= e["committed_at"]:
            e["grade_note"] = (f"plenary {plen_date} NOT after commit {e['committed_at']} "
                               f"— not gradeable as prospective")
            continue
        bg = resolve_plenary.fetch_by_group(row["id"])
        if not bg:
            continue
        observed = {g: baselines._yes_rate(s) for g, s in bg.items()}
        groups = [g for g in GROUPS
                  if observed.get(g) is not None
                  and e["committee_per_group"].get(g) is not None
                  and e["comparator_baseline_A"].get(g) is not None]
        if len(groups) < 5:
            continue
        cm = e["comparator_const_mean"]
        e["plenary_status"] = "resolved"
        e["graded"] = {
            "plenary_id": row["id"], "plenary_date": plen_date,
            "plenary_result": row["result"],
            "observed_per_group": {g: round(observed[g], 6) for g in groups},
            "n_groups": len(groups),
            "mse_committee": round(_mse(e["predicted_plenary_per_group"], observed, groups), 6),
            "mse_const_mean": round(_mse({g: cm for g in groups}, observed, groups), 6),
            "mse_baseline_A": round(_mse(e["comparator_baseline_A"], observed, groups), 6),
            "outcome_correct": (e["predicted_outcome"] == row["result"]),
            "graded_at": today,
        }
        n_new += 1
    _save(ledger)
    print(f"grade: scored {n_new} newly-resolved predictions.")
    status()


def verify() -> None:
    ledger = _load()
    bad = [e["procedure"] for e in ledger if e.get("content_hash") != _hash(e)]
    if bad:
        print(f"verify: TAMPERING — {len(bad)} entries have a hash mismatch: {bad}")
    else:
        print(f"verify: OK — all {len(ledger)} entries hash-match (untampered).")


def status() -> None:
    ledger = _load()
    pending = [e for e in ledger if not e.get("graded")]
    graded = [e for e in ledger if e.get("graded")]
    cont_pending = [e for e in pending if e.get("contested_ex_ante")]
    print(f"\nStage B ledger: {len(ledger)} predictions — {len(pending)} pending, "
          f"{len(graded)} graded.")
    # The headline metric: the prospective contested track record is the whole point,
    # and it is gated on contested files that have voted in committee but NOT yet in
    # plenary. Surface that count explicitly — it is usually the binding constraint.
    print(f"  CONTESTED pending (the binding metric): {len(cont_pending)}"
          + (f"  [{', '.join(e['procedure'] for e in cont_pending)}]" if cont_pending else
             "  — none in the current rolling window; awaiting new committee votes"))
    if graded:
        import statistics as st
        def mean(k, rows=graded):
            return st.mean(e["graded"][k] for e in rows)
        nc = [e for e in graded if e["contested_ex_ante"]]
        acc = sum(e["graded"]["outcome_correct"] for e in graded) / len(graded)
        print(f"  graded model vs floors (per-group MSE): committee={mean('mse_committee'):.4f} "
              f"const_mean={mean('mse_const_mean'):.4f} baseline_A={mean('mse_baseline_A'):.4f}")
        print(f"  outcome accuracy: {acc:.2f}  |  contested graded: {len(nc)}")
    if pending:
        print(f"  pending (awaiting plenary): "
              f"{', '.join(e['procedure'] for e in pending[:12])}"
              f"{' ...' if len(pending) > 12 else ''}")


def report() -> None:
    """Write a legible markdown track-record artifact from the ledger.

    This is the prospective scoreboard a CTO / investor would read: what was predicted
    before the vote, how it scored against the §9.6 floors once the vote resolved, and —
    most importantly — how much CONTESTED prospective evidence has actually accumulated
    (the only evidence that upgrades Stage A from "promising snapshot" to "track record").
    Honest by construction: it shows the pending queue and the contested count even when
    they are zero, so the artifact never overstates what exists.
    """
    import statistics as st

    ledger = _load()
    pending = [e for e in ledger if not e.get("graded")]
    graded = [e for e in ledger if e.get("graded")]
    cont_pending = [e for e in pending if e.get("contested_ex_ante")]
    cont_graded = [e for e in graded if e.get("contested_ex_ante")]
    today = _today()

    L = []
    L.append("# Stage B — prospective pre-commitment track record")
    L.append("")
    L.append(f"_As of {today}. Generated by `uv run python -m praevisa.stage_b report`._")
    L.append("")
    L.append("Each prediction below was written to the git-committed ledger **before** its "
             "plenary vote existed (the commit timestamp is the proof) and is graded only "
             "on a plenary vote dated strictly after the commit. Model = the committee "
             "per-group vote; floors = the frozen §9.6 baselines.")
    L.append("")
    L.append("## Scoreboard")
    L.append("")
    L.append(f"- **Total predictions:** {len(ledger)}  ·  graded {len(graded)}  ·  "
             f"pending {len(pending)}")
    L.append(f"- **Contested predictions:** graded {len(cont_graded)}  ·  "
             f"pending {len(cont_pending)}")
    if not cont_graded:
        L.append("- **Contested prospective evidence so far: none graded yet.** This is the "
                 "metric that matters; until it is non-zero, Stage A's contested result "
                 "(p=0.039, pseudo-prospective) is *not* yet confirmed prospectively.")
    if graded:
        def mean(k, rows):
            return st.mean(e["graded"][k] for e in rows)
        acc = sum(e["graded"]["outcome_correct"] for e in graded) / len(graded)
        beats = sum(e["graded"]["mse_committee"] < e["graded"]["mse_const_mean"]
                    for e in graded)
        L.append(f"- **Outcome accuracy (graded):** {acc:.0%} "
                 f"({sum(e['graded']['outcome_correct'] for e in graded)}/{len(graded)})")
        L.append(f"- **Model beats const_mean floor on:** {beats}/{len(graded)} graded files")
        L.append(f"- **Mean per-group MSE (graded):** committee "
                 f"{mean('mse_committee', graded):.4f} · const_mean "
                 f"{mean('mse_const_mean', graded):.4f} · baseline_A "
                 f"{mean('mse_baseline_A', graded):.4f}")
        if cont_graded:
            L.append(f"- **Contested-only mean MSE:** committee "
                     f"{mean('mse_committee', cont_graded):.4f} · const_mean "
                     f"{mean('mse_const_mean', cont_graded):.4f} · baseline_A "
                     f"{mean('mse_baseline_A', cont_graded):.4f}")
    L.append("")

    L.append("## Graded predictions")
    L.append("")
    if graded:
        L.append("| procedure | cmte | stage | contested | predicted | actual | ✓ | "
                 "MSE cmte | MSE const | MSE base_A |")
        L.append("|---|---|---|:--:|---|---|:--:|--:|--:|--:|")
        for e in sorted(graded, key=lambda e: e["graded"]["plenary_date"]):
            g = e["graded"]
            L.append(f"| {e['procedure']} | {e['committee']} | {e['signal_stage']} | "
                     f"{'YES' if e['contested_ex_ante'] else '–'} | {e['predicted_outcome']} | "
                     f"{g['plenary_result']} | {'✓' if g['outcome_correct'] else '✗'} | "
                     f"{g['mse_committee']:.4f} | {g['mse_const_mean']:.4f} | "
                     f"{g['mse_baseline_A']:.4f} |")
    else:
        L.append("_None graded yet._")
    L.append("")

    L.append("## Pending predictions (committed, awaiting their plenary vote)")
    L.append("")
    if pending:
        L.append("| procedure | cmte | stage | contested | committed | predicted | EP yes-share |")
        L.append("|---|---|---|:--:|---|---|--:|")
        for e in sorted(pending, key=lambda e: (not e.get("contested_ex_ante"), e["procedure"])):
            L.append(f"| {e['procedure']} | {e['committee']} | {e['signal_stage']} | "
                     f"{'YES' if e['contested_ex_ante'] else '–'} | {e['committed_at']} | "
                     f"{e['predicted_outcome']} | {e['predicted_ep_yes_share']:.2f} |")
    else:
        L.append("_None pending._")
    L.append("")
    L.append("---")
    L.append("_Integrity: every entry is hash-stamped and append-only; "
             "`uv run python -m praevisa.stage_b verify` recomputes the hashes. "
             "Grading refuses any plenary vote not strictly after the commit date._")

    out = LEDGER.parent.parent / "results" / "stage_b_report.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    print(f"report: wrote {out.relative_to(LEDGER.parent.parent)} "
          f"({len(graded)} graded, {len(pending)} pending, "
          f"{len(cont_pending)} contested pending).")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"predict": predict, "grade": grade, "verify": verify, "status": status,
     "report": report}.get(
        cmd, lambda: print(f"unknown command {cmd!r}; "
                           "use predict|grade|verify|status|report"))()


if __name__ == "__main__":
    main()
