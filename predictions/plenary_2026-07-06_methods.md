# How to read these predictions — methods and pre-registered grading

*Companion to `plenary_2026-07-06_forward.json` / `.md`. Committed to git BEFORE the
ledger is generated and before the part-session opens on 6 July 2026; this commit is
the pre-registration proof. The ledger commit follows separately.*

---

## 1. What this is

One prediction for **every votable item** on the European Parliament's FINAL DRAFT
AGENDA (PDOJ 790.507, revision of 3 July 2026) for 6–9 July 2026 — no exceptions, no
cherry-picking. Items we do *not* predict (votes the PDOJ schedules for September,
oral questions without a tabled motion, procedural votes, possible late additions) are
listed by name in the ledger's `not_predicted` block before the session, not
discovered afterwards.

After the session we grade every line against the official results and publish the
scorecard, including the misses. Nothing in the ledger is edited after its commit; an
item pulled from the final agenda is marked "not voted" and excluded, never
re-predicted.

## 2. How a prediction is made (plain language)

For each political group we estimate the share of its members who will vote *for*. We
then weight by seats and add up. If the predicted "for" seats exceed the "against"
seats, we predict ADOPTED. There is no discretionary override; the same code produces
every line.

The estimate for each group comes from one of two **rails**, stamped on every item:

- **`prior` (the baseline)** — no item-specific committee evidence is used. Each group
  gets its *historical average* yes-rate from the frozen 18-file test set (baseline_A,
  unchanged since §9.6) — except **consent-type items**, whose per-group vector is the
  Term-10 consent prior (H3 below). Prior-rail items also carry a type-conditional
  `p_adopt` (prior v2, committed artifact `results/prior_v2.json`, re-frozen at HTV
  export 2026-06-20 before this ledger was generated).
- **`committee-rcv(...)` / `committee:...`** — a committee roll-call record passed the
  H1 eligibility gate (below), so each group's committee yes-rate (H2 denominator)
  feeds its plenary forecast through the Stage-A identity map (α = 1.0, unchanged,
  committed in `results/calibration.json`).

**The headline percentage is a predicted seat share, not a probability.** `p_adopt` is
the probability; the two are separate fields doing separate jobs.

## 3. The signal-policy revision bound to this ledger (H1/H2/H3)

**H1/H2/H3 are pre-registered hypotheses from `ERROR_ANALYSIS_2026-06_ledger.md`;
this ledger is their first forward test.** They were motivated by the June Liberia
polarity inversion and are stated here as binding rules for this ledger — they are
hypotheses under test, not validated claims.

**H1 — signal-rail eligibility** (`stage0_feasibility.signal_rail_eligible`). A
committee record may feed the signal rail ONLY if all of:

- (a) the record's committee is the item's **responsible** committee (a joint
  responsibility like "DEVE/ENVI" admits either); opinion-committee records never
  qualify;
- (b) the record is a **final vote on the report/text object that goes to the floor**
  (the corpus subject taxonomy's report or provisional stage; mandate votes are
  procedural and never qualify). At second/third reading the floor object is the
  Council position / conciliation joint text, so a committee record on the
  first-reading report never qualifies for a `cod2`/`cod3` item;
- (c) the record's procedure reference matches the item's where both are known; a
  mismatch (e.g. base procedure vs an M-suffixed accompanying procedure)
  disqualifies.

Any record failing the gate **demotes the item to the prior rail with disclosure**:
the `signal` field reads `"prior (signal demoted: <reason>)"` and `committee_tally`
is kept. The information that a committee vote existed is never silently dropped.

**H2 — predictor abstention handling** (`ep_flip.predictor_group_rates`). In the
predictor path only, abstentions leave the denominator (rate = FOR/(FOR+AGAINST)); a
group whose committee members only abstained contributes no committee signal and
falls back to its prior-rail value. The measurement basis is untouched: Decision 1
(abstentions in the denominator) stands wherever historical rates are *measured*,
and `results/baseline_eval.json` reproduces byte-identically under the revision
(regression-tested).

**H3 — consent typing + no vector reuse.**

1. Consent-type items on the prior rail use a **Term-10 consent per-group prior**:
   pooled per-group ballots over all 61 Term-10 NLE main votes (committed raw extract
   `data/htv_consent/nle_by_group.json`, HTV export 2026-06-20), Jeffreys-smoothed,
   Decision-1 denominator. Reproduce with
   `uv run python -m praevisa.prior_v2` (network-free from the committed extract).
2. **No vector reuse across floor objects**: one committee record may feed at most
   ONE agenda item — the one whose procedure reference matches per H1(c); with no
   reference to disambiguate, ALL sharing items ride the prior rail.

**Corpus tripwire** (also binding): a record where the rapporteur's own group voted
majority-against on an adoption vote (the Maij pattern) is polarity-unreliable and is
excluded from the signal rail even from the responsible committee, with the demotion
disclosed (`praevisa/corpus_health.py::polarity_tripwire`; flags published in
`results/corpus_health.json`).

**Prior-rail outcome for types that usually fail**: when an item's type prior says
`p_adopt < 0.5` (Term-10 DEA objections: 0/12 adopted), the outcome call follows the
type base rate (REJECTED) rather than the topic-blind seat-math vector, so `outcome`
and `p_adopt` cannot contradict each other on the prior rail. Ledger types without a
tabulated Term-10 base (IMM, RSO, RPS — under 5 mains each) carry no `p_adopt` and
say so in a note.

## 4. The math (exact, unchanged from June except where §3 says otherwise)

Per group *g* with *s_g* seats, the predicted yes-rate is

> ŷ_g = α·c_g + (1 − α)·p_g

where *c_g* is the group's committee yes-rate under the H2 denominator (the term
drops out when there is no eligible committee record or the group only abstained),
*p_g* is the group's prior (baseline_A; consent prior for consent-type items), and
**α = 1.0** — the identity map, unchanged (a shrinkage calibration was tested and
rejected by the pre-set decision rule; see `results/calibration.json`).

Chamber tally, abstentions ignored, Non-attached (NI, 33 seats) excluded because they
have no group line to model:

> YES = Σ_{g≠NI} s_g·ŷ_g  NO = Σ_{g≠NI} s_g·(1 − ŷ_g)
> predicted share = YES / (YES + NO)  outcome = ADOPTED iff YES > NO
> (except the p_adopt < 0.5 prior-rail rule in §3)

**Second reading (***II, here: the Regulation 2021/1232 extension).** Plenary cannot
"adopt" a Council position — it can only amend or reject it, and that takes an
**absolute majority of members (361 of 720)**, not a majority of votes cast. The
prediction is the threshold test: predicted seats against = Σ_g s_g·(1 − ŷ_g); if
that falls short of 361 the Council position stands and the act is deemed adopted.

**Third reading (***III, here: air passenger rights).** A conciliation joint text
needs a simple majority of votes cast; it is predicted with the normal seat math and
typed to the COD base rate (the closest tabulated type, disclosed as such).

**The flip lever.** Unchanged from June: with margin *M* = |YES − NO|, reversing the
outcome requires ⌈M/2⌉ members to cross sides. A group is *capable* if its predicted
losing-side seats cover that number; among capable groups the pivot is the one with
the most movable mass, m_g = s_g·(1 − 2·|ŷ_g − 0.5|). On prior-rail items this
statement is structural, not item-specific.

## 5. The baseline to beat — read this before the scorecard

**A coin with ADOPTED printed on both sides gets roughly nine out of ten EP final
votes right.** Raw outcome accuracy is therefore *not* evidence of skill, including
ours. The scorecard will always show three pre-registered columns, never pooled:

| | what it shows |
|---|---|
| **always-ADOPTED** | the naive rule, graded on exactly the same items |
| **prior rail** | party arithmetic + type priors only — our published baseline |
| **committee rail** | the only place we claim added information |

We claim skill **only** where the committee rail beats the other two columns.
Demoted items (`"prior (signal demoted: …)"`) are graded on the **prior** rail —
that is the point of the demotion — with their committee tallies kept visible so the
counterfactual can be audited after grading.

## 6. Pre-registered grading rules (fixed now, before the votes; copied unchanged from the June methods file)

1. **Sources.** Outcomes: the official plenary minutes. Vote shares and per-group
   rates: the published roll-call records (via HowTheyVote / EP open data). Items
   decided by show of hands have no roll call — they are graded on outcome only, and
   counted.
2. **Outcome score.** Hit = predicted ADOPTED/REJECTED matches the official result.
   For the second-reading item: hit = correct side of the 361 threshold (position
   stands vs amended/rejected).
3. **Share error** (roll-call items only): |predicted share − observed share|, with
   the observed share computed by the same convention, for / (for + against).
4. **Per-group error** (committee-rail items with a roll call): mean squared error
   between ŷ_g and the group's observed yes-rate, the same metric used throughout
   the repo's backtests.
5. **Subsets reported separately:** contested vs routine; committee rail vs prior
   rail vs always-ADOPTED; never pooled into a single headline number.
6. **No retroactive edits.** The ledger is append-only from the pre-session commit.
   Withdrawn or postponed items are marked, not deleted. If the final agenda adds
   votes after this commit, they may be predicted in a *separate, later-timestamped*
   ledger entry — clearly marked — or not at all; they are never backfilled.
7. **Brier.** Items carrying `p_adopt` are additionally Brier-scored,
   (p_adopt − observed)², observed = 1 iff ADOPTED — unchanged prior-v2 hook.

Grading opens **2026-07-10**, the day after the part-session closes
(`GRADE_OPENS` in `praevisa/plenary_forward.py`); the code refuses earlier runs. The
leak spot-check (`praevisa.leak_spotcheck`) runs again on/after 07-10 before grading,
as in June.

## 7. Known limitations, stated up front

- The prior rail is topic-blind by design (consent items excepted, where the type
  prior is still item-blind within the type); we say so in the signal column.
- Committee→plenary transfer is a tested but not statistically established signal at
  current sample sizes (an earlier significance claim was withdrawn after an audit
  found a stage-pairing leak; the audit trail is public in the repo history).
- H1/H2/H3 rest on a June evidence base of n=2 responsible-committee wins vs n=1
  opinion-committee record counted twice. This ledger is their first forward test —
  they may fail it.
- Two ECON corpus records matching July items (2025/2134(INI), 2024/2117(INI),
  2025/2211(INI)) and one TRAN record (Morocco aviation) were NOT wired to the
  signal rail because their scraped title/rapporteur metadata contradicts the PDOJ
  (attribution untrusted); this is disclosed per item in the manifest notes. A
  corpus-quality fix is future work, not a mid-ledger patch.
- Small numbers: one session proves nothing. The track record is the accumulation of
  sessions, every one committed before the votes.
