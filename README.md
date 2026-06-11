# Praevisa — research

An auditable research track record for predicting European Parliament votes.

The working hypothesis: committee-stage roll-call votes carry a forward signal for the
subsequent plenary vote on the same file — and most of the value sits in the small
*contested* subset, since uncontested EP plenary votes are largely predictable from party
arithmetic alone. This repo holds the data, code, baselines, and a pre-committed forward
prediction ledger so that every claim can be checked against committed artifacts.

## Key artifacts

| Artifact | What it is |
|---|---|
| [RESULTS.md](RESULTS.md) | §9.6 baseline numbers on the frozen 18-file test set, regenerable with one command |
| [METHODOLOGY.md](METHODOLOGY.md) | Frozen methodology; all flagged decisions resolved before computation |
| [FINDINGS_2026-06-08.md](FINDINGS_2026-06-08.md) | Technical briefing — what is validated, what is unproven, what is open |
| [predictions/plenary_2026-06-15_forward.md](predictions/plenary_2026-06-15_forward.md) | Forward ledger: 26 votable items of the 2026-06-15/18 Strasbourg session, all predicted before the votes |
| [predictions/plenary_2026-06-15_methods.md](predictions/plenary_2026-06-15_methods.md) | Pre-registered grading rules for that ledger |
| [results/stage_b_report.md](results/stage_b_report.md) | Stage B prospective scoreboard (commit timestamps prove predictions preceded votes) |
| [results/stress_set.json](results/stress_set.json) | Stress tests on the ledger: fragility Monte Carlo, grading-collision scan, jackknives |
| [docs/index.html](docs/index.html) | Dashboard view of the above |

## Integrity stance

This is a track record, not a results showcase, so the rules are mechanical:

- **Predictions are committed before the votes exist.** The git commit timestamp is the
  proof; grading uses only plenary votes dated strictly after the commit.
- **Grading is append-only and pre-registered.** The grading rules for the current ledger
  were committed before the session — in code (`praevisa/plenary_forward.py`, the code is
  the registration) and in plain language (`predictions/plenary_2026-06-15_methods.md`).
- **Withdrawn claims stay public.** On 2026-06-10 an audit found that the retrospective
  contested committee→plenary result (p = 0.039, n = 8) had been graded partly against
  Rule-71 mandate votes — a resolver bug. Corrected (and after the §9.6 base re-freeze),
  it is n = 4 and not significant; the
  claim was withdrawn the same day. The original text remains in place with a correction
  banner (the project's tombstone rule), and the §9.6 test set was re-frozen at 18 files.

As of 2026-06-11 the prospective contested track record stands at zero graded predictions.
That is the honest state of the evidence; the forward ledger exists to change it.

## Reproduce

The baseline numbers regenerate network-free from the committed test set:

```sh
uv run python -m praevisa.baseline_eval
```

Tests:

```sh
uv run --with pytest python -m pytest tests/
```
