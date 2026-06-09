"""Corpus health & scrape-drift guard for the committee data — the pipeline's smoke alarm.

The committee corpora are the project's one fragile, accumulate-over-time dependency
(no API; rolling-window PDFs; brittle parsing). Two failure modes can silently rot the
Stage-A / Stage-B evidence without any error being raised:

  1. SHRINKAGE — a re-scrape drops records instead of merging (the accumulate-only
     guarantee in committee_scrape._write_corpus breaks). History we can't re-fetch is
     lost. Detected by comparing record counts to the last committed health snapshot.

  2. SIGNAL DROP-OUT — the subject classifier stops recognising a stage it used to,
     so legitimate lead-committee report votes fall through and the Stage-A sample
     silently shrinks. This is the exact bug fixed on 2026-06-09 (exact-string matching
     vs PDF noise). Detected by the "suspicious unclassified" canary: a COD record whose
     subject *looks* like a signal (mentions a report / final vote / negotiation stage)
     but classifies to None.

This module raises neither silently: it prints a readable report, writes a snapshot to
results/corpus_health.json, and EXITS NON-ZERO on a hard violation so the weekly cadence
(scripts/stage_b_cadence.sh) can gate on it.

Run:  uv run python -m praevisa.corpus_health
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

from .stage0_feasibility import _norm_subject, classify_signal_stage

REPO = Path(__file__).resolve().parent.parent
SNAPSHOT = REPO / "results" / "corpus_health.json"

# Phrases that mean "this is (probably) a substantive committee signal". If a COD record's
# normalized subject contains one of these but classify_signal_stage returns None, that is
# a parser regression canary — the classifier should have caught it.
SIGNAL_HINTS = (
    "adoption of draft report", "draft report", "text as amended", "final vote",
    "provisional agreement", "enter into interinstitutional",
    "mandate to enter", "decision to enter",
)
# ...unless the subject is one of these (legitimately NOT a lead whole-text signal).
HINT_EXCLUSIONS = ("opinion", "second reading", "resolution")


def _load_corpora():
    corpora = {}
    for f in sorted(glob.glob(str(REPO / "committee_corpus_*.json"))):
        com = Path(f).stem.replace("committee_corpus_", "")
        corpora[com] = json.load(open(f)).get("records", [])
    return corpora


def audit(corpora):
    """Per-committee health rows + the suspicious-unclassified canary list."""
    rows = []
    suspicious = []
    for com, recs in corpora.items():
        cod = [r for r in recs if r.get("procedure", "").endswith("(COD)")]
        cod_voted = [r for r in cod if r.get("votes") and not r.get("secret")]
        classified = 0
        for r in cod_voted:
            subj = r.get("subject", "")
            stage = classify_signal_stage(subj)
            if stage is not None:
                classified += 1
                continue
            n = _norm_subject(subj)
            if (any(h in n for h in SIGNAL_HINTS)
                    and not any(x in n for x in HINT_EXCLUSIONS)):
                suspicious.append({"committee": com, "procedure": r.get("procedure"),
                                   "subject": subj})
        reconciled = sum(1 for r in recs if r.get("reconciled"))
        rows.append({
            "committee": com, "n_records": len(recs), "n_cod": len(cod),
            "n_cod_voted": len(cod_voted), "n_classified_signal": classified,
            "n_reconciled": reconciled,
        })
    return rows, suspicious


def main():
    corpora = _load_corpora()
    rows, suspicious = audit(corpora)
    rows.sort(key=lambda r: -r["n_records"])

    prior = {}
    if SNAPSHOT.exists():
        prior = {r["committee"]: r for r in json.load(open(SNAPSHOT)).get("rows", [])}

    print("CORPUS HEALTH — committee data integrity & scrape-drift guard\n")
    print(f"{'cmte':6s}{'records':>8s}{'Δ':>6s}{'COD':>5s}{'voted':>7s}"
          f"{'signal':>8s}{'recon':>7s}")
    print("-" * 47)
    shrunk = []
    for r in rows:
        was = prior.get(r["committee"], {}).get("n_records")
        delta = "" if was is None else f"{r['n_records'] - was:+d}"
        if was is not None and r["n_records"] < was:
            shrunk.append((r["committee"], was, r["n_records"]))
        print(f"{r['committee']:6s}{r['n_records']:>8d}{delta:>6s}{r['n_cod']:>5d}"
              f"{r['n_cod_voted']:>7d}{r['n_classified_signal']:>8d}{r['n_reconciled']:>7d}")
    tot_rec = sum(r["n_records"] for r in rows)
    tot_sig = sum(r["n_classified_signal"] for r in rows)
    tot_voted = sum(r["n_cod_voted"] for r in rows)
    print("-" * 47)
    print(f"{'TOTAL':6s}{tot_rec:>8d}{'':>6s}{sum(r['n_cod'] for r in rows):>5d}"
          f"{tot_voted:>7d}{tot_sig:>8d}{sum(r['n_reconciled'] for r in rows):>7d}")

    # --- verdicts ---
    violations = []
    if shrunk:
        violations.append(
            "SHRINKAGE: " + ", ".join(f"{c} {a}->{b}" for c, a, b in shrunk)
            + " (accumulate-only guarantee broken — a re-scrape lost records).")
    if suspicious:
        violations.append(
            f"SIGNAL DROP-OUT: {len(suspicious)} COD record(s) look like a signal but "
            "classify to None (possible parser regression).")

    print()
    if suspicious:
        print("Suspicious unclassified (signal-like subject, classifier returned None):")
        for s in suspicious[:20]:
            print(f"  {s['committee']:5s} {s['procedure']:16s} {s['subject'][:48]!r}")
        if len(suspicious) > 20:
            print(f"  … and {len(suspicious) - 20} more")
        print()

    out = {"rows": rows, "suspicious": suspicious,
           "totals": {"records": tot_rec, "cod_voted": tot_voted,
                      "classified_signal": tot_sig}}
    SNAPSHOT.parent.mkdir(exist_ok=True)
    SNAPSHOT.write_text(json.dumps(out, indent=1))
    print(f"written: {SNAPSHOT.relative_to(REPO)}  "
          f"(baseline for next run's drift check)")

    if violations:
        print("\nVERDICT: FAIL")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    print(f"\nVERDICT: OK — {tot_rec} records across {len(rows)} committees, "
          f"{tot_sig}/{tot_voted} COD votes classified as a signal, no shrinkage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
