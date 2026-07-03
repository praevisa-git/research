# Error analysis — June 2026 forward ledger, committee signal rail

*Post-mortem of the graded 2026-06-15 ledger (`predictions/plenary_2026-06-15_forward.json`,
graded 26/26, commit `c2b6267`). This document motivates a pre-registered revision of the
signal-rail eligibility rules (H1/H2/H3 below), to be tested forward on the July 6–9
ledger. Nothing in the June ledger is modified, re-graded, or recomputed; it is frozen
history and stands exactly as committed.*

---

## 1. The clean split

Four graded items rode the committee signal rail. Per-group MSE (lower is better),
signal vs the flat prior on the same item, from
`predictions/plenary_2026-06-15_forward.json`:

| Item | Rail stamp | Signal source | MSE signal | MSE prior | Signal wins? |
|---|---|---|---|---|---|
| Farmers in the food supply chain (A10-0161/2025, cod1) | `committee:report` | AGRI — responsible committee, final vote on the report | **0.0181** | 0.1348 | yes |
| Development cooperation / irregular movements (A10-0147/2026, ini) | `committee-rcv(DEVE)` | DEVE — responsible committee, final vote on the report | **0.1028** | 0.1745 | yes |
| EU–Liberia VPA termination — consent (A10-0133/2026) | `opinion(DEVE)` | DEVE — opinion committee (responsible: INTA) | 0.3547 | **0.0756** | no — catastrophic |
| EU–Liberia VPA termination — resolution (A10-0146/2026) | `opinion(DEVE)` | DEVE — opinion committee (responsible: INTA) | 0.5731 | **0.0782** | no — catastrophic |

Responsible-committee final-vote signals beat the prior 2/2. Opinion-committee signals
lost 2/2 — and both losses are the *same* DEVE record counted twice, so this is n=2 vs
n=1 record. Small numbers; the split is a hypothesis generator, not a validated result.

## 2. The Liberia failure mechanism, in three layers

**(a) Wrong vote object.** The DEVE record that fed both Liberia predictions was a
FINAL VOTE BY ROLL CALL on *adoption of an amended draft opinion* under the accompanying
M-procedure **2025/0259M(NLE)** — not on the consent question the floor voted
(2025/0259(NLE)). The record's own title says "Adoption of the draft opinion";
its rapporteur was Marit Maij (S&D). Her own group voted **against** (S&D 0/5 FOR):
the draft had been amended against the rapporteur's intent in committee, so the
committee's FOR/AGAINST axis was *inverted* relative to the floor question. A committee
vote can be a high-quality signal of *its own question* and still carry the wrong
polarity for a different floor object. Group breakdown of the record
(tally 13–9–3): FOR = EPP 6, ECR 3, PfE 3, ESN 1; AGAINST = S&D 5, Left 2, Greens 2;
ABSTAIN = Renew 3.

**(b) Abstention → opposition.** Renew's committee members abstained 3/3. Under the
Decision-1 denominator (abstentions count in the denominator), Renew's committee
yes-rate is 0/3 = 0.0, which the identity map forwarded as "Renew votes 0% FOR on the
floor." Observed Renew on both floor votes: 1.0. An abstention on an opinion draft is
not an opposition signal; the predictor turned three abstentions into a hard NO.

**(c) One vector, two objects.** The single DEVE per-group vector was reused for both
floor items. Observed outcomes: the **consent** passed near-consensus, **608–38**
(observed per-group ≈ 1.0 everywhere except Left 0.36); the **resolution** passed
542–52–70 with a right-side defection (observed FOR-rates: PfE 0.51, ECR 0.42,
ESN 0.08). Two floor objects with near-opposite observed cleavages cannot both be
predicted by the same committee vector; reusing it guaranteed at least one large miss.

**INTA had zero Liberia records in the corpus** (verified: no VPA/Liberia record in
`committee_corpus_INTA.json`). The opinion channel was a *silent fallback*, not a
modeling choice — the engine took the only committee vote it could find, without a rule
saying whether it was eligible.

## 3. This is a known failure class

Three incidents now share one mechanism — **vote-object identity/polarity failure**,
where a committee or plenary record matched the *topic* but not the *question*:

1. **Mandate-vote leak** (withdrawn 2026-06-10): Stage A graded committee signals
   against Rule-71 mandate votes instead of final plenary votes; the headline p=0.039
   was withdrawn.
2. **June-Prediction tobacco polarity**: a grading collision where topic-matched vote
   rows carried a different question than the predicted one (vote_id overrides were the
   fix).
3. **Liberia** (this ledger): an amended-draft-opinion vote on an M-procedure fed
   consent and resolution predictions with inverted polarity.

Topic match ≠ object match. The corpus can be perfectly scraped and still poison a
prediction if the *question voted* differs from the *question predicted*.

## 4. POST-HOC DIAGNOSTIC — not ledger performance, not publishable as such

> **⚠️ Everything in this box is a counterfactual computed after the outcomes were
> known. It is NOT the June ledger's performance, must never appear in README,
> RESULTS.md headline tables, or the dashboard, and is recorded here only to size the
> hypothesis.**
>
> Had the opinion-demotion rule (H1 below) been in force when the June ledger was cut,
> both Liberia items would have ridden the prior rail. The four-item signal-rail mean
> per-group MSE would have been **0.069** (= mean of 0.0181, 0.1028, and the two prior
> values 0.0756, 0.0782), against **0.116** for the flat prior on the same four items —
> instead of the **0.262** actually recorded. This number was computed with full
> hindsight. It validates nothing; the forward test on the July ledger is what counts.

## 5. Pre-registered hypotheses (forward test: July 6–9 ledger)

The following are **hypotheses**, not validated claims. They are stated here, committed
before the July methods file and ledger, and get their first forward test on the July
6–9 part-session ledger. The evidence above is n=2 vs n=1; no significance is claimed.

- **H1 — signal-rail eligibility.** A committee record may feed the signal rail only if
  (a) it comes from the item's *responsible* committee, (b) it is a *final vote on the
  report/text that goes to the floor*, and (c) its procedure reference matches the
  item's procedure where both are known (an M-suffixed accompanying procedure does not
  match its base procedure). Anything else — including every `opinion_signal` record —
  demotes the item to the prior rail, with the demotion disclosed in the item's
  `signal` field and the committee tally kept for transparency.
- **H2 — abstentions in the predictor.** In the *predictor* path only, abstentions
  leave the denominator; a group whose committee members only abstained contributes no
  committee signal and falls back to its prior-rail value. The *measurement* basis
  (Decision 1, abstentions in the denominator) is unchanged wherever historical rates
  are measured.
- **H3 — vote-object typing for consents + no vector reuse.** Consent-type items on the
  prior rail get a Term-10 consent-vote type prior (Jeffreys-smoothed, same pattern as
  `prior_v2`). One committee record may feed at most ONE floor object — the one whose
  object matches under H1(c); accompanying items go prior rail. Under these rules, both
  June Liberia items would have been prior rail (opinion source + M-procedure
  reference mismatch).
