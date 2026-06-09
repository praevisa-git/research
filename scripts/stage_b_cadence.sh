#!/bin/bash
# Stage B weekly cadence — the automated pre-commitment loop.
#
# Runs the full prospective pipeline and commits the ledger BEFORE the relevant
# plenary votes happen (the commit timestamp is the pre-commitment proof):
#   1. accumulate committee corpora (merge; rolling-window safe)
#   2. grade any predictions whose plenary vote has now resolved (after-commit only)
#   3. predict newly-eligible pending files (immutable, hash-stamped)
#   4. verify ledger integrity
#   5. commit ledger + corpora + results
#
# Designed for cron. Self-contained: absolute paths, own PATH, append-only log.
# Manual run:  bash scripts/stage_b_cadence.sh
#
# NOTE: this repo has no git remote, so commits are LOCAL. The local commit history
# timestamps the pre-commitment, which is adequate for internal validation. For an
# externally defensible track record, add a remote and `git push` here (or stamp each
# predict with a public hash), so the prediction is provably public before the vote.

set -uo pipefail

REPO="/Users/motazkabbani/praevisa"
PY="$REPO/.venv/bin/python"
export PATH="/Users/motazkabbani/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

cd "$REPO" || { echo "cannot cd to $REPO"; exit 1; }
mkdir -p "$REPO/logs"
LOG="$REPO/logs/stage_b_cadence.log"

{
  echo ""
  echo "===================================================================="
  echo "Stage B cadence — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "===================================================================="

  echo "--- 1. accumulate committee corpora (merge) ---"
  "$PY" committee_scrape.py all || echo "WARN: scrape returned nonzero"

  echo "--- 1b. corpus health / scrape-drift guard ---"
  if ! "$PY" -m praevisa.corpus_health; then
    echo "FAIL: corpus health check failed (shrinkage or signal drop-out)."
    echo "Aborting BEFORE predict/commit so a bad scrape cannot poison the ledger."
    echo "cadence aborted $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    exit 1
  fi

  echo "--- 2. grade resolved predictions ---"
  "$PY" -m praevisa.stage_b grade || echo "WARN: grade returned nonzero"

  echo "--- 3. predict new pending files ---"
  "$PY" -m praevisa.stage_b predict || echo "WARN: predict returned nonzero"

  echo "--- 4. verify ledger integrity ---"
  "$PY" -m praevisa.stage_b verify || echo "WARN: verify returned nonzero"

  echo "--- 4b. refresh prospective track-record report ---"
  "$PY" -m praevisa.stage_b report || echo "WARN: report returned nonzero"

  echo "--- 5. commit (pre-commitment proof) ---"
  git add predictions/stage_b_ledger.json committee_corpus_*.json \
          results/stage0_feasibility.json results/corpus_health.json \
          results/stage_b_report.md 2>/dev/null
  if git diff --cached --quiet; then
    echo "no changes to commit"
  else
    git commit -q \
      -m "stage B cadence $(date -u +%Y-%m-%d): scrape + grade + predict" \
      -m "Automated weekly cadence (scripts/stage_b_cadence.sh): accumulate committee corpora, grade resolved predictions, pre-commit new pending ones." \
      && echo "committed $(git rev-parse --short HEAD)" \
      || echo "WARN: commit failed"
  fi
  echo "cadence done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$LOG" 2>&1
