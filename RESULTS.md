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

## Part 1 — Contested-subset check

The §5b verdict (baseline_A tied with const_mean over all 22 files) raised the
obvious question: maybe the per-group signal is real but only shows up on the
*contested* files, drowned out by the easy near-unanimous ones. We test that by
**stratified re-evaluation**: LOO predictions are held fixed (Decision 6) and the
evaluation sample is restricted to contested subsets defined three ways.
Reproduce: `uv run python -m praevisa.contested_subset`
([`results/contested_subset.json`](results/contested_subset.json)).

**Contestedness lenses** (all post-hoc — defined from observed yes-rates, so this is
descriptive "where is A more accurate", not a prospective claim):

- **dispersion** — stdev of the 9 group yes-rates on a file. *This lens mechanically
  favors A*: const_mean predicts one scalar for all groups, so its per-file loss
  essentially **is** that dispersion. A "win" here is near-tautological — reported as
  an upper bound, not evidence.
- **boundary** — closeness of the EP yes-share to 0.5 (outcome in doubt). Outcome-
  defined, not mechanically tied to per-group variance.
- **rejected** — the 4 REJECTED files (outcome-defined; n=4, descriptive only).

baseline_A vs the const_mean floor, paired (positive `mean_diff` = const_mean worse
than A; same bootstrap seed 0 / 10k + Wilcoxon as §5b, restricted to the subset):

| subset | n | A MSE | const_mean MSE | mean_diff | 95% CI | wilcox p | A wins? |
|---|---:|---:|---:|---:|---|---:|---|
| full | 22 | 0.1656 | 0.1759 | +0.0104 | [−0.018, +0.036] | 0.354 | no |
| dispersion bottom-half (routine) | 11 | 0.1508 | 0.1552 | +0.0044 | [−0.027, +0.033] | 0.577 | no |
| dispersion top-half (UPPER BOUND) | 11 | 0.1803 | 0.1966 | +0.0163 | [−0.030, +0.058] | 0.465 | no |
| dispersion top-third (UPPER BOUND) | 7 | 0.2138 | 0.2150 | +0.0012 | [−0.062, +0.059] | 1.000 | no |
| boundary closest-to-0.5 | 11 | 0.1644 | 0.1811 | +0.0167 | [−0.034, +0.061] | 0.831 | no |
| REJECTED only | 4 | 0.3489 | 0.2593 | **−0.0896** | [−0.122, −0.057] | n<6 | **A worse** |

> Note: the `0.1508` in the routine row is baseline_A's *actual, computed* loss on that
> subset (0.15081, reproducible from `results/contested_subset.json`). Its collision with
> the retired phantom figure 0.1508 is a coincidence, not a reappearance of it. The
> phantom (group MSE 0.1004 / 0.1508) has no artifact and is dead; the real Baseline A
> group MSE is **0.1656** (§ headline metrics).

**Verdict — the contested subset does NOT rescue Baseline A; it indicts it.**

- On **no** contested lens does A significantly beat const_mean — every CI spans 0,
  every Wilcoxon p ≫ 0.05. The §5b tie holds under stratification.
- Even on the **mechanically-favorable** dispersion lens the gap stays inside the
  noise, and on the most-dispersed *third* it collapses to +0.0012 (p = 1.000): where
  A should win by construction, it doesn't clear sampling error at n = 7.
- On the **REJECTED** files — the genuinely contested, lost votes — A is **worse than
  the pooled mean** (mean_diff −0.0896, bootstrap CI entirely below 0). The reason is
  diagnostic: A predicts each group's historical mean (EPP/S&D/Renew ≈ 0.85 yes), but
  on a file the Parliament *rejected* even the centrist trio voted low, so the
  stable-group-yes-rate assumption inverts. baseline_C (0.95 for the trio) is
  catastrophic there (0.49). n = 4, so this is a signal not a test — but it points the
  same way as everything else.

**Implication for the product.** A backward per-group-mean baseline carries no
established forecasting signal beyond the pooled mean on this set, and what little it
has evaporates (or reverses) exactly on the contested votes where forecasting value
is supposed to live. This is consistent with the broader thesis: the value is not in
"what each group usually does" but in the contested universe (mandates, amendments,
close/lost votes), which a historical-mean baseline cannot reach. A real model must
clear the const_mean floor *on the contested subset*, prospectively — not just nose
ahead of it on the full set. That bar is now explicit.

## Part 2 — Stage A: the committee→plenary signal (first positive result)

§9.6 set the bar: a real model must clear the `const_mean` floor *on the contested
subset*. Stage A tests the first candidate signal — a group's pre-vote **committee**
vote — against that bar. Data feasibility was established first (`stage0_feasibility`,
the procedure→plenary resolver, and a 20-committee scrape → 19 usable pairs, 8
contested). Stage A grades the signal: `uv run python -m praevisa.stage_a`
([`results/stage_a.json`](results/stage_a.json)).

> **2026-06-09 — sample correction (data-quality fix).** The signal selector matched
> committee-vote subjects against an *exact-string* table. Committee roll-calls are
> scraped from PDFs, so real subject lines arrive with template noise (`1.1. `, a `·`
> bullet, a trailing `- Rejected`, an appended `(Co-Rapporteurs: …)`). Exact matching
> silently dropped legitimate **lead-committee report** votes — a parsing bug, not a
> methodology choice. `classify_signal_stage` now normalizes that noise (still
> default-excluding opinions, second-reading, resolutions, single amendments, and
> rapporteur-header noise). This recovered **+6 graded pairs (+2 contested)**, including
> `2025/0429` (LIBE) — a file the committee **rejected** (0.41) and plenary **also
> rejected** — the single most diagnostic contested case type. The numbers below are the
> corrected, larger sample; the pre-fix figures were n=10 / 6 contested. The expansion
> also *added a contested case the signal loses* (`2025/0322`), so this is a faithful
> widening, not a favorable cut.

Method: time-split, pseudo-prospective. For each pair, predict the plenary per-group
yes-rate with three predictors — `const_mean` and `baseline_A` (the §9.6 floors, fit
only on §9.6 base files dated *before* the target), and `committee` (the committee's
per-group yes-rate on that file, cast before plenary). Per-group MSE, paired bootstrap
CI + Wilcoxon as §5b. Negative `mean_diff` = committee BETTER.

| subset | n | committee MSE | floor MSE | mean_diff | 95% CI | wilcox p |
|---|---:|---:|---:|---:|---|---:|
| all pairs vs const_mean | 13 | 0.0687 | 0.1617 | −0.0930 | [−0.157, −0.031] | **0.027** |
| all pairs vs baseline_A | 13 | 0.0687 | 0.1625 | −0.0937 | [−0.165, −0.022] | 0.057 |
| contested vs const_mean | 8 | 0.0683 | 0.1985 | −0.1302 | [−0.215, −0.036] | **0.039** |
| contested vs baseline_A | 8 | 0.0683 | 0.2082 | −0.1399 | [−0.233, −0.029] | **0.039** |

**The committee signal clears the §9.6 bar on the contested cut — now significant.**
On the **contested subset** (the only cut §9.6 says counts) the committee signal beats
*both* floors with Wilcoxon **p = 0.039** and a CI that excludes 0 — the first time the
contested result crosses the 0.05 threshold rather than only pointing the right way
(the pre-fix figure was p = 0.062 at n = 6). It wins on 6 of 8 contested files, by a
large margin (committee ~0.07 vs floor ~0.20), and crucially wins on the **rejected**
file `2025/0429` (committee 0.067 vs floor 0.209) — exactly where §9.6 showed the
historical baselines fail worst.

**Honest mixed reading — one cut softened.** The expansion added two report-stage files
that `baseline_A` predicts well, so **all-pairs vs baseline_A dropped from p = 0.020 to
p = 0.057** (CI still excludes 0, but it no longer clears the strict 0.05 "wins" bar).
All-pairs vs const_mean stays significant (p = 0.027). The methodology de-emphasizes the
all-pairs cut on purpose (§1, §9.6: judge on contested), so the headline is the
contested result; the all-pairs softening is reported, not hidden.

Adversarial split (does it survive without the near-tautological post-trilogue stage?):
the **report-adoption** stage remains the cleanest signal — committee MSE 0.060 vs floor
0.170 across 8 report files, and **0.052 vs 0.219 on the 5 contested report files** —
while the provisional-agreement stage is messier. So the effect is not an artifact of
"same text, same people"; the substantive committee vote is the better predictor.

**Honest limits (why this is a first signal, not a verdict):**
- n = 13 pairs (8 contested) from a single rolling-window snapshot; p = 0.039 sits just
  inside 0.05 and would not survive a multiple-comparison correction across the cuts.
- The contested files are **clustered, not independent**: the LIBE files share a
  committee and the ECON pair 2025/0825 + /0826 are twins (near-identical) — the
  *effective* independent contested n is closer to ~3–4 than 8, so the Wilcoxon p
  overstates how much independent evidence there is. This is the single biggest caveat.
- Pseudo-prospective (historical, time-split), **not** pre-committed. Stage B (true
  blinded pre-commitment, report-stage focus, more files) is required to confirm.
- This buys ~weeks of lead time on files that have reached committee; it does **not**
  forecast far ahead, the Council dimension, or trilogue outcomes.

Still: this is the first evidence in the project that a pre-vote signal beats the
§9.6 floor where it matters. The wedge is no longer purely hypothetical.

## Provenance

- Raw per-vote JSON + pull index: [`data/htv_raw/`](data/htv_raw/) (committed).
- Baselines + loaders: [`praevisa/baselines.py`](praevisa/baselines.py).
- LOO harness + metrics: [`praevisa/baseline_eval.py`](praevisa/baseline_eval.py).
- Robustness harness: [`praevisa/baseline_robustness.py`](praevisa/baseline_robustness.py).
- Contested-subset check: [`praevisa/contested_subset.py`](praevisa/contested_subset.py).
- Procedure→plenary resolver: [`praevisa/resolve_plenary.py`](praevisa/resolve_plenary.py).
- Stage-0 feasibility gate: [`praevisa/stage0_feasibility.py`](praevisa/stage0_feasibility.py).
- Stage A backtest: [`praevisa/stage_a.py`](praevisa/stage_a.py).
- Committee corpora: `committee_corpus_*.json` (accumulating; `committee_scrape.py`).
- Machine-readable results: [`results/baseline_eval.json`](results/baseline_eval.json),
  [`results/baseline_robustness.json`](results/baseline_robustness.json),
  [`results/contested_subset.json`](results/contested_subset.json),
  [`results/stage0_feasibility.json`](results/stage0_feasibility.json),
  [`results/stage_a.json`](results/stage_a.json).
