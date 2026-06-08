# Competitor benchmark on the contested tail (2026-06-08)

**Question:** can we put a real number behind "Praevisa wins the contested tail" vs the
two rivals? **Short answer:** vs **EU Matrix** it is a *structural forfeit* (it makes no
forward prediction for our files); vs **MEPanalytics** it is *open* (gated access — the
benchmark that actually matters, still to run); vs the **naive baseline** Praevisa already
wins (Stage A: committee signal 0.05 vs floor 0.21 per-group MSE on contested files).

## EU Matrix — cannot be benchmarked forward, by construction

Investigated the live EU Matrix API (`eumatrix.eu/api`, open, no key). Findings:

1. **It is a single frozen snapshot.** Every predicted group vote
   (`/api/quiz_cache_vote_groups`, 45,333 rows) is stamped `createdAt = 2024-07-18`. The
   product is 306 fixed policy "quizzes" with only **105** historical roll-call links
   (`/api/quiz_rcvs`), all pre-July-2024.
2. **Our contested files postdate it.** The contested files Praevisa targets are 2025–26
   (`2025/0059`, `2025/0101`, `2025/0132`, `2025/0825`, `2025/0826`, …). A model frozen in
   July 2024 has, by construction, **zero predictions** for them. There is no overlap to
   grade.
3. **So on the forward contested tail, EU Matrix is not a competitor at all** — it
   forfeits the category by design. This is not a measured win; it is a structural one,
   and it confirms the competitive brief (EU Matrix = backward influence snapshot, not a
   forward predictor).

**Quantified weakness (from EU Matrix's own data).** Even within its backward snapshot,
EU Matrix declines to predict — returns *undetermined* — most on exactly the groups whose
behavior decides contested votes:

| group | % undetermined |
|---|---:|
| Non-attached | 19.2 |
| ECR | 19.0 |
| Greens/EFA | 14.8 |
| Renew | 11.8 |
| The Left | 11.0 |
| S&D | 7.8 |
| EPP | 4.4 |
| Patriots | 0.1 |
| ESN | 0.0 |

The disciplined poles (ESN, Patriots, EPP) are ~certain; the **pivotal centrist-to-left
and non-mainstream groups** — the ones that swing contested outcomes — are where EU Matrix
is least sure. Its model is weakest exactly where forecasting value lives. (Mean
undetermined 11.6%.)

## MEPanalytics — the benchmark that matters, still open

MEPanalytics is the real threat (forward ML, 80% claimed accuracy, 2.9M votes). It is
**gated ("early access")**, so its per-file predictions are not publicly queryable. We
therefore **could not benchmark it here.** This is the one head-to-head that would truly
validate "we win the tail," and it requires either trial access or their published
predictions. Until then, the claim that Praevisa beats MEPanalytics on contested votes is
**a hypothesis, not a result** — stated honestly.

## Verdict

- vs **EU Matrix**: forfeit on the forward contested tail (structural); weakest on the
  pivotal groups in-sample. A real, citable competitive finding.
- vs **naive baseline**: Praevisa wins (Stage A, committee signal ~4× lower error on
  contested files) — but n=10, one snapshot, not yet prospective.
- vs **MEPanalytics**: **unmeasured.** The decisive benchmark. Get access and grade their
  contested-subset predictions against Praevisa + the baseline; that number is the spine
  of any anti-MEPanalytics pitch and does not yet exist.

**Honest bottom line:** we can show EU Matrix structurally abandons the contested tail and
that Praevisa beats the naive baseline there — but the head-to-head against the actual
threat is still to be run. Do not claim "we beat MEPanalytics on contested votes" until it
is graded.
