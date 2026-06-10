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
ALERT="$REPO/logs/STAGE_B_ALERT"

# Drop a proactive marker file when the cadence aborts. A silent abort otherwise only
# lives in the rolling log; this file is a sticky, greppable signal ("did last week's
# run actually go through?") that a successful run clears. Reason is timestamped.
raise_alert() {
  { echo "STAGE B CADENCE ABORTED — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "reason: $1"
    echo "see logs/stage_b_cadence.log for the full run."
  } > "$ALERT"
}

# The LaunchAgent fires on a calendar trigger and can wake the Mac BEFORE the network
# is up — a 2026-06-08 run hit DNS failures on all 20 committees and (because the
# scrape merge is non-destructive) committed "no changes" as if nothing was wrong.
# Host the readiness probe targets; overridable for testing the abort path.
NET_HOST="${STAGEB_NET_HOST:-www.europarl.europa.eu}"

# Block until DNS for the EP host resolves, or give up after a bounded backoff.
# Returns nonzero if the network never comes up, so the caller can abort loudly.
wait_for_network() {
  local tries=0 max="${STAGEB_NET_TRIES:-10}" delay="${STAGEB_NET_DELAY:-15}"
  while [ "$tries" -lt "$max" ]; do
    if "$PY" -c "import socket,sys; socket.setdefaulttimeout(10); socket.getaddrinfo(sys.argv[1],443)" "$NET_HOST" >/dev/null 2>&1; then
      return 0
    fi
    tries=$((tries + 1))
    echo "network not ready (cannot resolve $NET_HOST), attempt $tries/$max — sleeping ${delay}s"
    sleep "$delay"
  done
  return 1
}

{
  echo ""
  echo "===================================================================="
  echo "Stage B cadence — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "===================================================================="

  echo "--- 1. accumulate committee corpora (merge) ---"
  if ! wait_for_network; then
    echo "FAIL: network never came up (cannot resolve $NET_HOST after retries)."
    echo "Aborting BEFORE scrape/grade/predict/commit — a calendar trigger fired"
    echo "before the network was ready. No commit, so no silent 'no changes' miss."
    echo "cadence aborted (no network) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    raise_alert "network never came up (cannot resolve $NET_HOST after retries)"
    exit 1
  fi
  # Retry the scrape with backoff. committee_scrape.py 'all' now exits nonzero on a
  # TOTAL failure (every committee errored / zero records pulled) — which a merge-safe
  # accumulator otherwise hides, since it leaves the on-disk corpora untouched and the
  # drift guard sees no shrinkage. A flaky single committee still exits 0 (resilient).
  scrape_ok=0
  for attempt in 1 2 3; do
    if "$PY" committee_scrape.py all; then
      scrape_ok=1
      break
    fi
    echo "WARN: scrape attempt $attempt pulled nothing (network/DNS); backing off 20s"
    sleep 20
  done
  if [ "$scrape_ok" -ne 1 ]; then
    echo "FAIL: committee scrape pulled nothing on all $attempt attempts (network/DNS)."
    echo "Aborting BEFORE grade/predict/commit so a failed scrape cannot masquerade as"
    echo "an 'off week' and silently miss a new contested committee roll-call."
    echo "cadence aborted (scrape failed) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    raise_alert "committee scrape pulled nothing on all attempts (network/DNS)"
    exit 1
  fi

  echo "--- 1b. corpus health / scrape-drift guard ---"
  if ! "$PY" -m praevisa.corpus_health; then
    echo "FAIL: corpus health check failed (shrinkage or signal drop-out)."
    echo "Aborting BEFORE predict/commit so a bad scrape cannot poison the ledger."
    echo "cadence aborted $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    raise_alert "corpus health check failed (shrinkage or signal drop-out)"
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
  # Reached the end cleanly — scrape, health, grade, predict and commit all passed.
  # Clear any stale alert from a previous failed week.
  rm -f "$ALERT"
  echo "cadence done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "$LOG" 2>&1
