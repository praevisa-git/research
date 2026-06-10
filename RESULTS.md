# §9.6 Baseline Engine — Results

These are the real, artifact-backed numbers for the §9.6 baselines. They **replace**
the prior figures (group MSE 0.1004 / 0.1508), which had no surviving artifact behind
them. Every number here regenerates from committed code + data with one command.

Methodology is frozen in [METHODOLOGY.md](METHODOLOGY.md); all four flagged decisions
were resolved explicitly before any computation (Decisions 1–4 there).

> **2026-06-10 — RE-FROZEN at 18 files (was 22).** An audit found the original selection
> admitted **3 Rule-71 mandate votes** (`2024/0027`/174880, `2023/0404`/174881,
> `2025/0097`/193315 — procedural "decision to enter interinstitutional negotiations", not a
> vote on the legislative text) plus a **duplicated procedure** (`2025/0322` appeared as both
> its pre-trilogue text vote 182460 and its post-trilogue agreement 184191; the duplicate
> 184191 was removed, 182460 kept). All numbers below are the re-frozen 18-file figures. The
> headline effect: **baseline_A no longer edges const_mean — it falls marginally behind it**
> (0.1796 vs 0.1768), which *strengthens* the §9.6 conclusion that a backward per-group mean
> carries no signal beyond the pooled mean. Pre-re-freeze tombstone: 22 files, baseline_A
> 0.1656 / const_mean 0.1759, A noses ahead (+0.0104, p=0.35). See `data/htv_raw/index.json`
> (`revision_2026_06_10`) and METHODOLOGY §2.

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

18 files (re-frozen 2026-06-10; see banner). Filter: `is_main` & `procedure.type==COD` &
`result ∈ {ADOPTED, REJECTED}` & non-empty per-group roll-call & 10th parliamentary term
(`timestamp ≥ 2024-07-16`), **minus** Rule-71 mandate-confirmation votes and a duplicated
procedure (4 removed by hand; the inclusion filter alone does not distinguish a mandate
vote from a substantive first-reading text vote). All 18 are `OLP_FIRST_READING`; all 162
(group × file) cells defined.

EP yes-share = `FOR/(FOR+AGAINST+ABSTENTION)` over all groups (Decision 1).

| EP yes-share | result | reference | id |
|---:|---|---|---|
| 0.060 | REJECTED | 2021/0297(COD) | 190403 |
| 0.177 | REJECTED | 2025/0045(COD) | 182614 |
| 0.251 | REJECTED | 2025/0261(COD) | 189581 |
| 0.367 | REJECTED | 2025/0524(COD) | 181393 |
| 0.607 | ADOPTED | 2025/0132(COD) | 184168 |
| 0.651 | ADOPTED | 2025/0322(COD) | 182460 |
| 0.682 | ADOPTED | 2025/0260(COD) | 189313 |
| 0.704 | ADOPTED | 2025/0090(COD) | 180954 |
| 0.727 | ADOPTED | 2023/0455(COD) | 179790 |
| 0.767 | ADOPTED | 2024/0017(COD) | 192436 |
| 0.808 | ADOPTED | 2025/0207(COD) | 190027 |
| 0.833 | ADOPTED | 2025/0129(COD) | 178147 |
| 0.852 | ADOPTED | 2025/0108(COD) | 180979 |
| 0.881 | ADOPTED | 2025/0251(COD) | 182479 |
| 0.922 | ADOPTED | 2025/0022(COD) | 178405 |
| 0.943 | ADOPTED | 2025/0039(COD) | 178285 |
| 0.955 | ADOPTED | 2024/0318(COD) | 184110 |
| 0.993 | ADOPTED | 2025/0023(COD) | 178406 |

_Removed in the 2026-06-10 re-freeze: 174881 (2023/0404), 193315 (2025/0097), 174880
(2024/0027) — Rule-71 mandate votes; 184191 (2025/0322) — duplicate of the procedure's
text vote 182460._

## Headline metrics (leave-one-out, one fold per file)

| predictor | MSE macro | MSE micro | EP yes-share SSE | EP yes-share RMSE |
|---|---:|---:|---:|---:|
| **baseline_A** (LOO group mean) | **0.1796** | 0.1796 | **1.5112** | 0.2898 |
| const_mean (LOO pooled mean) | 0.1768 | 0.1768 | 1.5030 | 0.2890 |
| const_0.95 | 0.2697 | 0.2697 | 2.6927 | 0.3868 |
| baseline_C (0.95/0.05 centrist-trio) | 0.3648 | 0.3648 | 1.6307 | 0.3010 |

- **MSE macro** = mean of per-group MSE (groups weighted equally); **micro** = mean over
  all cells (cells weighted equally). They are equal here because the design is balanced
  (every group has exactly 18 defined cells) — this is a property of the data, not a bug.
- **Per-group Brier** is, by construction, identical to per-group MSE on the [0,1]
  yes-rate (METHODOLOGY §5); it is recorded under both names in the JSON.

## Per-group MSE (= per-group Brier)

| group | baseline_A | baseline_C | const_0.95 | const_mean |
|---|---:|---:|---:|---:|
| EPP | 0.1629 | 0.1724 | 0.1724 | 0.1757 |
| S&D | 0.1881 | 0.2198 | 0.2198 | 0.1840 |
| PfE | 0.2048 | 0.3640 | 0.4076 | 0.2138 |
| ECR | 0.1964 | 0.5382 | 0.2637 | 0.1828 |
| Renew | 0.1868 | 0.2109 | 0.2109 | 0.1861 |
| Greens | 0.1938 | 0.6071 | 0.2310 | 0.1841 |
| Left | 0.2274 | 0.4281 | 0.3838 | 0.2184 |
| ESN | 0.1941 | 0.4412 | 0.3193 | 0.1793 |
| NI | 0.0621 | 0.3015 | 0.2186 | 0.0671 |

(baseline_C and const_0.95 are identical on EPP, S&D, Renew — both predict 0.95 there.)

## Reading the numbers

- **Baseline A does NOT beat const_mean** (0.1796 vs 0.1768 macro). On the re-frozen set the
  per-group refinement is marginally *worse* than the single pooled mean — group identity
  carries no established signal beyond the pooled mean here. (On the contaminated 22-file set
  A noses ahead by 0.0104; that edge was an artifact of 3 near-consensus mandate votes — see
  banner.) A still clearly beats both 0.95/0.05 schemes.
- **The 0.95/0.05 schemes are poor baselines.** Both const_0.95 and the centrist-trio
  Baseline C are clearly beaten by the mean-based predictors.
- **Baseline C's error is localised, not diffuse.** The centrist-trio rule assigns 0.05
  to the pro-EU left flanks, which in fact back many OLP first-reading files: Greens MSE
  **0.6071**, ECR **0.5382**, Left **0.4281**, ESN **0.4412**. This is the documented cost
  of the frozen Decision-2 partition, surfaced rather than hidden.

## Robustness / significance

The headline gaps are thin on 18 files, so we test them: cluster bootstrap over
files (10,000 resamples, seed 0), LOO predictions held fixed (METHODOLOGY §5b,
Decisions 5–6). Reproduce: `uv run python -m praevisa.baseline_robustness`
([`results/baseline_robustness.json`](results/baseline_robustness.json)).

MSE_micro with 95% bootstrap CI:

| predictor | MSE_micro | 95% CI |
|---|---:|---|
| baseline_A | 0.1796 | [0.1364, 0.2281] |
| const_mean | 0.1768 | [0.1479, 0.2111] |
| const_0.95 | 0.2697 | [0.1827, 0.3644] |
| baseline_C | 0.3648 | [0.3001, 0.4292] |

Paired vs baseline_A (per-file cell loss; positive mean_diff = rival worse than A):

| rival | mean_diff | 95% CI | win-frac | Wilcoxon p | gap real? |
|---|---:|---|---:|---:|---|
| baseline_C | +0.1852 | [+0.1274, +0.2452] | 1.000 | 0.0001 | **yes** |
| const_0.95 | +0.0901 | [+0.0341, +0.1449] | 0.999 | 0.0090 | **yes** |
| const_mean | −0.0028 | [−0.0238, +0.0167] | 0.406 | 1.0000 | **no** |

**Verdict.** baseline_A decisively beats both 0.95/0.05 constants (CI excludes 0,
p < 0.01). And **baseline_A is statistically indistinguishable from const_mean** — on the
re-frozen set it sits *marginally behind* the pooled mean (mean_diff −0.0028, CI spans 0,
Wilcoxon p = 1.0); the per-group signal beyond the pooled mean is not just unestablished but
faintly negative. On the aggregate EP yes-share, **none** of the rivals is significantly
separable from A (const_0.95 p = 0.17, baseline_C p = 0.37, const_mean p = 0.52). Treat
baseline_A and const_mean as a tied floor — A does not even nose ahead; a real model must
clear that band. (Caveat: this bootstraps test-set sampling only, with LOO predictions held
fixed — Decision 6.)

## Part 1 — Contested-subset check

The §5b verdict (baseline_A tied with — actually marginally behind — const_mean over all
18 files) raised the obvious question: maybe the per-group signal is real but only shows up on the
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
| full | 18 | 0.1796 | 0.1768 | −0.0028 | [−0.024, +0.017] | 1.000 | no |
| dispersion bottom-half (routine) | 9 | 0.1594 | 0.1568 | −0.0026 | [−0.030, +0.021] | 0.820 | no |
| dispersion top-half (UPPER BOUND) | 9 | 0.1998 | 0.1968 | −0.0030 | [−0.036, +0.026] | 0.820 | no |
| dispersion top-third (UPPER BOUND) | 6 | 0.2322 | 0.2145 | −0.0176 | [−0.057, +0.017] | 0.438 | no |
| boundary closest-to-0.5 | 9 | 0.1832 | 0.1820 | −0.0012 | [−0.040, +0.034] | 0.910 | no |
| REJECTED only | 4 | 0.3426 | 0.2749 | **−0.0677** | [−0.089, −0.046] | n<6 | **A worse** |

**Verdict — the contested subset does NOT rescue Baseline A; it indicts it (more so after
the re-freeze).**

- On **no** contested lens does A beat const_mean — after re-freezing A is in fact
  *marginally worse* on every lens (all mean_diffs negative), and no CI excludes 0 in A's
  favour. The §5b "A behind the floor" result holds under stratification.
- Even on the **mechanically-favorable** dispersion lens A is behind, and on the
  most-dispersed *third* the gap is −0.0176 (p = 0.44): where A should win by construction,
  it loses (within sampling error) at n = 6.
- On the **REJECTED** files — the genuinely contested, lost votes — A is **worse than
  the pooled mean** (mean_diff −0.0677, bootstrap CI entirely below 0). The reason is
  diagnostic: A predicts each group's historical mean (EPP/S&D/Renew ≈ 0.85 yes), but
  on a file the Parliament *rejected* even the centrist trio voted low, so the
  stable-group-yes-rate assumption inverts. baseline_C (0.95 for the trio) is
  catastrophic there (0.49). n = 4, so this is a signal not a test — but it points the
  same way as everything else.

**Implication for the product.** A backward per-group-mean baseline carries no
established forecasting signal beyond the pooled mean on this set — after the re-freeze it is
marginally *behind* the pooled mean even before stratifying, and stays behind (or clearly
reverses, on REJECTED) on every contested cut where forecasting value is supposed to live. This is consistent with the broader thesis: the value is not in
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

> **2026-06-10 — CORRECTION: the contested significance result is WITHDRAWN.** An audit
> traced every contested pair to its plenary vote's `description` and found the resolver had
> been grading committee signals against **Rule-71 "decision to enter interinstitutional
> negotiations"** votes — a *procedural* vote, not a vote on the text — because HowTheyVote
> tags them `OLP_FIRST_READING / is_main` exactly like a real first-reading vote. Three
> contested files (`2025/0059`, `2025/0825`, `2025/0826`) were graded against mandate votes;
> `2025/0322` was mis-paired to its post-trilogue agreement instead of its pre-trilogue text
> vote. `resolve_first_reading` now excludes mandate votes and matches the plenary text-type
> to the committee stage ([`praevisa/resolve_plenary.py`](praevisa/resolve_plenary.py)). The
> corrected numbers below **supersede** the p = 0.039 figures, which were an artifact of that
> contamination. (Pre-correction tombstone: contested n = 8, p = 0.039 vs both floors.)

Method: time-split, pseudo-prospective. For each pair, predict the plenary per-group
yes-rate with three predictors — `const_mean` and `baseline_A` (the §9.6 floors, fit
only on §9.6 base files dated *before* the target), and `committee` (the committee's
per-group yes-rate on that file, cast before plenary). Per-group MSE, paired bootstrap
CI + Wilcoxon as §5b. Negative `mean_diff` = committee BETTER.

| subset | n | committee MSE | floor MSE | mean_diff | 95% CI | wilcox p |
|---|---:|---:|---:|---:|---|---:|
| all pairs vs const_mean | 7 | 0.0708 | 0.1487 | −0.0778 | [−0.133, −0.011] | 0.109 |
| all pairs vs baseline_A | 7 | 0.0708 | 0.1648 | −0.0940 | [−0.174, −0.008] | 0.109 |
| contested vs const_mean | 4 | 0.0884 | 0.1816 | −0.0933 | [−0.166, +0.026] | — (n<6) |
| contested vs baseline_A | 4 | 0.0884 | 0.2188 | −0.1304 | [−0.232, +0.022] | — (n<6) |

**The committee signal points the right way but is NOT statistically significant.** On the
contested subset the committee beats both floors in *direction* — materially lower MSE,
favourable in ~95 % of bootstrap draws — but the contested CIs include 0, and with n = 4 the
sample is below the Wilcoxon threshold (n ≥ 6), so there is no significance test. On all 7
pairs the bootstrap CI *does* exclude 0 (committee clearly lower error), but the Wilcoxon
p = 0.109 — so even there it fails the strict p < 0.05 "wins" bar. The previously-reported
contested p = 0.039 was an artifact of grading contested committee reports against
near-procedural mandate votes; removing that contamination (and re-freezing the §9.6 base it
is compared against) removes the result.

What survives is a **consistent favourable direction**, not a verdict: across both cuts the
committee signal has materially lower error than the §9.6 floors, and it still wins the most
diagnostic case — the **rejected** file `2025/0429` (committee 0.067 vs floor 0.229).

**Honest limits (why this is at most a weak directional signal):**
- **Not significant on any cut.** Contested n = 4 is below the Wilcoxon threshold; all-pairs
  reaches CI-excludes-0 but Wilcoxon p = 0.11. A favourable *direction* on a tiny, clustered
  sample is encouraging at best, not evidence.
- **The sample shrank with the re-freeze:** removing the 3 mandate votes from the §9.6 base
  left fewer pre-target training files for the time-split, dropping contested pairs 5 → 4
  (`2025/0322` fell out) and all-pairs 9 → 7. The clean base is the right base, but it is smaller.
- The contested files are **clustered, not independent** (shared LIBE committee; the ECON
  twins 2025/0825 + /0826 dropped as mandate-only) — effective independent contested n is ~3.
- Pseudo-prospective (historical, time-split), **not** pre-committed. Stage B (true blinded
  pre-commitment) is the only thing that can establish a real track record — and it currently
  has **0** contested predictions pending.

The wedge remains a hypothesis. Honest status after correction: a pre-vote committee signal
*may* beat the §9.6 floor on contested files, but the project does **not** yet have
statistically significant evidence that it does.

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
