# §9.6 Baseline Engine — Frozen Methodology

Status: **FROZEN.** The three silent-divergence risks were flagged and resolved by
explicit decision (see "DECISIONS — RESOLVED" at the foot of this file). No
computation deviates from what is written here; if a deviation becomes necessary
it is re-flagged and re-confirmed before coding, not chosen silently.

This methodology replaces the prior group-MSE figures (0.1004 / 0.1508), which
have no surviving artifact. We are building fresh, not matching them.

---

## 1. Prediction unit

For each roll-call vote (a "file") and each EP political group, the quantity
predicted and graded is the group's **yes-rate**:

```
yes_rate(group, file) = FOR / (FOR + AGAINST + ABSTENTION)
```

- FOR, AGAINST, ABSTENTION come from HowTheyVote `stats.by_group[].stats`.
- `DID_NOT_VOTE` is **excluded** from the denominator (a non-cast ballot is not a
  position). [RESOLVED — DECISION 1.]
- A group with `FOR+AGAINST+ABSTENTION == 0` on a file (everyone DID_NOT_VOTE) is
  **dropped for that file only** — no yes-rate is defined, so it is neither
  predicted nor graded there.

### The "group" set
The unit of prediction is the EP political group as reported by HowTheyVote in
`stats.by_group`. We map HTV group codes to the 9 canonical 10th-term groups
already defined in `praevisa/data.py`:

`EPP, S&D, PfE, ECR, Renew, Greens, Left, ESN, NI`.

NI (Non-attached) is included: it appears in `stats.by_group` and is a real row,
even though it is not a cohesive group. Its yes-rates are expected to be the
noisiest; this is a property of the data, not a modeling choice, and we report
it rather than hide it. The exact HTV→canonical code map is built and printed in
the fetcher step so the mapping is auditable.

---

## 2. Test set selection

Pulled live from HowTheyVote.eu and saved as raw JSON to committed `data/`.

Inclusion filter (all must hold):
- `is_main == true`
- `procedure.type == "COD"` (ordinary legislative procedure, ***I first reading)
- `result ∈ {ADOPTED, REJECTED}`
- a real per-group roll-call exists (`stats.by_group` present and non-empty)
- `timestamp >= 2024-07-16` (10th parliamentary term only) — [RESOLVED — DECISION 4]

**Why the term restriction.** A group's yes-rate is only a stable prediction unit
*within* a parliamentary term. The 9th term (to 2024-04) reports an `ID` group
(Identity & Democracy) that dissolved at the June-2024 election with no clean
successor (members split across PfE, ESN, ECR, NI); the 10th term reports PfE+ESN
instead. Mixing terms would either fabricate a false group continuity or rest each
group's LOO mean on a term-specific subset. We restrict to the 10th term, which
also matches the product's scope. The eligible 10th-term COD pool is ~180 files —
ample for a yes-share-spanning set including rejected files.

Target: **18–25 files**, deliberately spanning a range of EP yes-shares (not all
near-unanimous). Selection within the eligible pool is by spread of EP yes-share,
not cherry-picked by reference. The fetcher reports the final count, the list of
`procedure.reference`s, and each file's actual EP yes-share sorted ascending.

Raw pulled JSON (one file per vote + an index) is written to `data/htv_raw/` and
committed. A fresh clone never needs network access to re-grade.

---

## 3. Baselines

Both baselines predict a per-group yes-rate for every (group, file) cell, then are
graded against the observed yes-rate from §1.

### Baseline A — leave-one-out group mean
For target file *t* and group *g*:

```
pred_A(g, t) = mean over all files f ≠ t of yes_rate(g, f)
```

- Mean is taken over only the files where `yes_rate(g, f)` is defined (§1).
- This is an honest LOO: file *t* never contributes to its own prediction.
- If group *g* has no defined yes-rate on any file other than *t*, the cell is
  undefined and excluded from *t*'s grading (degenerate; logged).

### Baseline C — constant smoothed group-line (0.95 / 0.05)
File-independent. Each group is assigned a fixed predicted yes-rate of either
**0.95** or **0.05**, the same value on every file.

```
pred_C(g, t) = 0.95 if g ∈ MAJORITY_SET else 0.05
```

`MAJORITY_SET = {EPP, S&D, Renew}` — the stable centrist pro-legislation majority.
All other groups (PfE, ECR, Greens, Left, ESN, NI) → 0.05. This is a fixed,
file-independent partition. [RESOLVED — DECISION 2.]

Baseline C does **not** look at the file's outcome (no oracle). It is a static
"the mainstream coalition votes yes, the flanks vote no" rule, identical for
ADOPTED and REJECTED files. (An outcome-conditioned variant is offered as an
option under DECISION 2 but is, by construction, not a true baseline.)

### Reference constants (not "baselines", sanity floors)
Reported alongside A and C so the baselines have a floor to beat:
- **const-0.95**: predict 0.95 for every group on every file.
- **const-mean**: predict the global pooled yes-rate (one scalar = mean of all
  defined `yes_rate(g,f)` over the whole set) for every cell, LOO-style
  (recomputed excluding *t*).

---

## 4. Leave-one-out (LOO) protocol

- One fold per file. For each target file *t*, every predictor is fit using only
  files ≠ *t*, then predicts the cells of *t*.
- Baseline C and const-0.95 are file-independent, so LOO does not change them;
  they are still evaluated on every held-out *t* for comparability.
- Baseline A and const-mean genuinely refit per fold (mean excluding *t*).
- The grading target is always the observed `yes_rate(g, t)` (§1) — never used in
  fitting that fold.

---

## 5. Metrics

Let cells be the defined (group, file) pairs. `y = observed yes_rate`,
`ŷ = predicted yes_rate ∈ [0,1]`.

**Per-group MSE** (primary): for each group g, over all files where g is defined,
```
MSE(g) = mean_f (ŷ(g,f) − y(g,f))²
```
Reported per group and as the **macro mean across groups** (each group weighted
equally) and the **micro mean across cells** (each cell weighted equally). Both
are stated explicitly to avoid the "which average" ambiguity.

**Per-group Brier**: identical formula to MSE on the [0,1] yes-rate
(`mean (ŷ − y)²`). Because our target is a *rate* in [0,1] rather than a 0/1
label, per-group Brier and per-group MSE are numerically the same quantity; we
report it under both names for traceability and note the identity rather than
inventing a second definition. (A 0/1-label Brier would require collapsing each
group-file to a single binary "did the group vote yes", discarding the rate; we
do not do that — flagged in RESULTS if a binary Brier is wanted instead.)

**Aggregate EP yes-share SSE**: per file, compare the predicted whole-EP yes-share
to the observed whole-EP yes-share, summed-squared over files.
```
observed_share(f) = Σ_g FOR(g,f) / Σ_g (FOR+AGAINST+ABSTENTION)(g,f)
pred_share(f)     = Σ_g w(g) · ŷ(g,f)      (weights w sum to 1)
SSE               = Σ_f (pred_share(f) − observed_share(f))²
```
The weighting `w(g)` is each group's **seat share** (seat count from
`praevisa/data.py` ÷ total seats) — a forecaster knows seats, not turnout.
[RESOLVED — DECISION 3.] Both observed and predicted use the same abstention
denominator from DECISION 1.

---

## 6. Reproducibility

A fresh clone regenerates every number with one documented command (e.g.
`python -m praevisa.baseline_eval` reading committed `data/htv_raw/`), with no
network access required for grading. The fetcher (network-touching) is a separate
command, run once, whose output is committed. RESULTS.md states the exact command
and the resulting numbers.

---

## DECISIONS — RESOLVED

**DECISION 1 — abstention in the denominator.**
Resolved: `FOR / (FOR + AGAINST + ABSTENTION)`, DID_NOT_VOTE excluded.
(Alternatives considered and rejected: `FOR/(FOR+AGAINST)`; include DID_NOT_VOTE.)

**DECISION 2 — Baseline C `MAJORITY_SET` membership.**
Resolved: `MAJORITY_SET = {EPP, S&D, Renew}` (centrist trio); all others → 0.05.
(Rejected: pro-EU mainstream incl. Greens+Left; per-file outcome-conditioned.)

**DECISION 3 — aggregate EP yes-share weights `w(g)`.**
Resolved: weight by each group's **seat share** from `praevisa/data.py`.
(Rejected: weight by actual ballots cast on the file.)

**DECISION 4 — parliamentary term scope.**
Resolved: **10th term only** (`timestamp >= 2024-07-16`). Surfaced after the first
pull returned a term-straddling set (16 ninth-term files carrying the now-defunct
`ID` group). (Rejected: keep mixed set with a per-term group superset; keep mixed
set mapping `ID→PfE`.)
