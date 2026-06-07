# §9.6 Baseline Engine — Results

These are the real, artifact-backed numbers for the §9.6 baselines. They **replace**
the prior figures (group MSE 0.1004 / 0.1508), which had no surviving artifact behind
them. Every number here regenerates from committed code + data with one command.

Methodology is frozen in [METHODOLOGY.md](METHODOLOGY.md); all four flagged decisions
were resolved explicitly before any computation (Decisions 1–4 there).

## Reproduce

Network-free — reads only the committed `data/htv_raw/` test set:

```
uv run python -m praevisa.baseline_eval
```

This regenerates [`results/baseline_eval.json`](results/baseline_eval.json) and prints
the tables below. (The one-time network pull that produced the committed test set is
`uv run python -m praevisa.fetch_testset`; it is provided for provenance and is **not**
needed to reproduce any number. Re-running it against a live HowTheyVote may select a
different set as the database grows — the committed `data/htv_raw/` is the frozen
artifact graded here.)

## Test set

22 files. Filter: `is_main` & `procedure.type==COD` & `result ∈ {ADOPTED, REJECTED}` &
non-empty per-group roll-call & 10th parliamentary term (`timestamp ≥ 2024-07-16`).
Selected from a 123-file eligible COD pool (545 candidates scanned) to span the range
of EP yes-share. All 22 are `OLP_FIRST_READING`; all 198 (group × file) cells defined.

EP yes-share = `FOR/(FOR+AGAINST+ABSTENTION)` over all groups (Decision 1).

| EP yes-share | result | reference | id |
|---:|---|---|---|
| 0.060 | REJECTED | 2021/0297(COD) | 190403 |
| 0.177 | REJECTED | 2025/0045(COD) | 182614 |
| 0.251 | REJECTED | 2025/0261(COD) | 189581 |
| 0.367 | REJECTED | 2025/0524(COD) | 181393 |
| 0.540 | ADOPTED | 2023/0404(COD) | 174881 |
| 0.607 | ADOPTED | 2025/0132(COD) | 184168 |
| 0.637 | ADOPTED | 2025/0097(COD) | 193315 |
| 0.651 | ADOPTED | 2025/0322(COD) | 182460 |
| 0.668 | ADOPTED | 2024/0027(COD) | 174880 |
| 0.682 | ADOPTED | 2025/0260(COD) | 189313 |
| 0.704 | ADOPTED | 2025/0090(COD) | 180954 |
| 0.727 | ADOPTED | 2023/0455(COD) | 179790 |
| 0.741 | ADOPTED | 2025/0322(COD) | 184191 |
| 0.767 | ADOPTED | 2024/0017(COD) | 192436 |
| 0.808 | ADOPTED | 2025/0207(COD) | 190027 |
| 0.833 | ADOPTED | 2025/0129(COD) | 178147 |
| 0.852 | ADOPTED | 2025/0108(COD) | 180979 |
| 0.881 | ADOPTED | 2025/0251(COD) | 182479 |
| 0.922 | ADOPTED | 2025/0022(COD) | 178405 |
| 0.943 | ADOPTED | 2025/0039(COD) | 178285 |
| 0.955 | ADOPTED | 2024/0318(COD) | 184110 |
| 0.993 | ADOPTED | 2025/0023(COD) | 178406 |

## Headline metrics (leave-one-out, one fold per file)

| predictor | MSE macro | MSE micro | EP yes-share SSE | EP yes-share RMSE |
|---|---:|---:|---:|---:|
| **baseline_A** (LOO group mean) | **0.1656** | 0.1656 | **1.5054** | 0.2616 |
| const_mean (LOO pooled mean) | 0.1759 | 0.1759 | 1.5405 | 0.2646 |
| const_0.95 | 0.2827 | 0.2827 | 3.0821 | 0.3743 |
| baseline_C (0.95/0.05 centrist-trio) | 0.3240 | 0.3240 | 1.6879 | 0.2770 |

- **MSE macro** = mean of per-group MSE (groups weighted equally); **micro** = mean over
  all cells (cells weighted equally). They are equal here because the design is balanced
  (every group has exactly 22 defined cells) — this is a property of the data, not a bug.
- **Per-group Brier** is, by construction, identical to per-group MSE on the [0,1]
  yes-rate (METHODOLOGY §5); it is recorded under both names in the JSON.

## Per-group MSE (= per-group Brier)

| group | baseline_A | baseline_C | const_0.95 | const_mean |
|---|---:|---:|---:|---:|
| EPP | 0.1338 | 0.1432 | 0.1432 | 0.1622 |
| S&D | 0.1583 | 0.1818 | 0.1818 | 0.1691 |
| PfE | 0.1924 | 0.2991 | 0.4757 | 0.2259 |
| ECR | 0.2000 | 0.4624 | 0.3196 | 0.1895 |
| Renew | 0.1604 | 0.1729 | 0.1729 | 0.1801 |
| Greens | 0.1629 | 0.6180 | 0.1946 | 0.1661 |
| Left | 0.1981 | 0.3822 | 0.3838 | 0.1965 |
| ESN | 0.2073 | 0.3985 | 0.3843 | 0.2028 |
| NI | 0.0771 | 0.2581 | 0.2880 | 0.0912 |

(baseline_C and const_0.95 are identical on EPP, S&D, Renew — both predict 0.95 there.)

## Reading the numbers

- **Baseline A wins on every metric.** It is the per-group refinement of const_mean and
  edges it out (0.1656 vs 0.1759 macro), confirming that group identity carries signal
  beyond the pooled mean — but not a large amount, on this set.
- **The 0.95/0.05 schemes are poor baselines.** Both const_0.95 and the centrist-trio
  Baseline C are clearly beaten by the mean-based predictors.
- **Baseline C's error is localised, not diffuse.** The centrist-trio rule assigns 0.05
  to the pro-EU left flanks, which in fact back many OLP first-reading files: Greens MSE
  **0.6180**, ECR **0.4624**, Left **0.3822**, ESN **0.3985**. This is the documented cost
  of the frozen Decision-2 partition, surfaced rather than hidden.

## Robustness / significance

The headline gaps are thin on 22 files, so we test them: cluster bootstrap over
files (10,000 resamples, seed 0), LOO predictions held fixed (METHODOLOGY §5b,
Decisions 5–6). Reproduce: `uv run python -m praevisa.baseline_robustness`
([`results/baseline_robustness.json`](results/baseline_robustness.json)).

MSE_micro with 95% bootstrap CI:

| predictor | MSE_micro | 95% CI |
|---|---:|---|
| baseline_A | 0.1656 | [0.1268, 0.2085] |
| const_mean | 0.1759 | [0.1531, 0.2012] |
| const_0.95 | 0.2827 | [0.2079, 0.3610] |
| baseline_C | 0.3240 | [0.2607, 0.3885] |

Paired vs baseline_A (per-file cell loss; positive mean_diff = rival worse than A):

| rival | mean_diff | 95% CI | win-frac | Wilcoxon p | gap real? |
|---|---:|---|---:|---:|---|
| baseline_C | +0.1584 | [+0.1064, +0.2097] | 1.000 | 0.0000 | **yes** |
| const_0.95 | +0.1171 | [+0.0603, +0.1731] | 1.000 | 0.0009 | **yes** |
| const_mean | +0.0104 | [−0.0177, +0.0357] | 0.778 | 0.3535 | **no** |

**Verdict.** baseline_A decisively beats both 0.95/0.05 constants (CI excludes 0,
p < 0.001). But **baseline_A is statistically indistinguishable from const_mean** on
this set — the per-group signal beyond the pooled mean is not established at n = 22
(mean_diff +0.0104, CI spans 0, Wilcoxon p = 0.35). On the aggregate EP yes-share,
only const_0.95 is significantly worse than A; const_mean and baseline_C are not
separable from A. Treat baseline_A and const_mean as a tied floor; a real model must
clear that band, not just nose ahead of it. (Caveat: this bootstraps test-set
sampling only, with LOO predictions held fixed — Decision 6.)

## Provenance

- Raw per-vote JSON + pull index: [`data/htv_raw/`](data/htv_raw/) (committed).
- Baselines + loaders: [`praevisa/baselines.py`](praevisa/baselines.py).
- LOO harness + metrics: [`praevisa/baseline_eval.py`](praevisa/baseline_eval.py).
- Robustness harness: [`praevisa/baseline_robustness.py`](praevisa/baseline_robustness.py).
- Machine-readable results: [`results/baseline_eval.json`](results/baseline_eval.json),
  [`results/baseline_robustness.json`](results/baseline_robustness.json).
