# Competitive Brief — Praevisa vs MEPanalytics & EU Matrix

**Prepared for:** Praevisa · **Updated:** 2026-06-01 · **Scope:** the two direct EU
legislative-intelligence competitors. EU Matrix basis: direct scrape of the public
site + open `/api`. MEPanalytics basis: public site + web research (the product is at
"early access", so traction/pricing are not yet observable).

---

## 1. The competitive landscape in one line
The market has two poles of the same product, and Praevisa is being squeezed between
them: **EU Matrix** is a free, backward-looking influence map; **MEPanalytics** is a
data-rich, forward-looking ML vote predictor — i.e. Praevisa's own method, already
shipped. Head-on, Praevisa loses on data depth to one and on price to the other.

| | **EU Matrix** (eumatrix.eu) | **MEPanalytics** (mepanalytics.eu) |
|---|---|---|
| What it is | Backward-looking influence map; per-policy 2D actor positioning | Forward-looking ML vote predictor for advocates |
| Method | Influence weighting + coalition tension, calibrated on past RCVs (July-2024 snapshot) | Proprietary ML + Monte Carlo + scenario analysis |
| Headline | "Data-driven crystal ball"; 306 policy quizzes | **80% accuracy**; 720 MEPs, **2.9M votes, 10+ yrs history** |
| Level | MEP / group / government / commissioner / stakeholder | MEP-level plenary |
| Business model | Freemium; **entire `/api` readable with no auth** (data is effectively free) | Gated, "Get Early Access" — newer, pre-scale |
| Target customer | Mixed: foresight, journalists, public affairs | Pure public affairs — "the logical tool for advocates in Brussels" |
| Time orientation | Backward (one snapshot) | Forward |

## 2. What this does to Praevisa's original wedges
Praevisa's first pitch — "forward, vs EU Matrix's backward" — **is now occupied by
MEPanalytics**, which already does forward, MEP-level, Monte Carlo prediction with 10
years of proprietary roll-call training data that public CHES cannot match. So:
- vs **MEPanalytics**: Praevisa loses the EP-level accuracy race (less data).
- vs **EU Matrix**: Praevisa loses on price (their data is free).

Competing as a vote-predictor means entering a two-sided squeeze from a weaker position.

## 3. The two gaps both competitors leave — and they are Praevisa's validated strengths
1. **Neither models the Council.** Both are EP/MEP-only. EU files die in Council on QMV
   arithmetic. Praevisa's flip analysis is *validated* there (pivotal national
   delegations concentrate 74% in the 7 largest states; blocking-minority math). Open
   ground: neither rival can say "you don't need the Parliament — you need Germany plus
   any two of {NL, CZ, SE}."
2. **An accuracy number decides nothing — and 80% is below the naive baseline.** 91% of
   EP final votes are adopted and ~100% predictable from party arithmetic ([[ep-vote-predictability]]).
   An 80% MEP-level accuracy claim is *worse* than the trivial baseline on the routine
   mass and silent on the contested 2–4% where value actually lives. Both rivals sell a
   score/leaderboard; **Praevisa's flip analysis sells the intervention** (who to move),
   which sidesteps the accuracy race entirely.

## 4. EU Matrix — detail (from the open API)
- 306 policy "quizzes"; precomputed caches dated 2024-07-24. Layers: Parties (1.22M
  rows, predicted voteValue), Governments (136k rows, coalition/national tension),
  MEPs (76k, imputed `proxy` votes + manual analyst overrides), Groups (45k).
- Core IP = government coalition/opposition tension decomposition, but it **degenerates
  where coalition structure is thin** (5 unitary governments score exactly 0.0 tension:
  CY, EE, GR, HU, MT) and is anchored to a single backward snapshot.
- Model is *least confident on the contested, non-mainstream votes* (%Undet spikes on
  ECR 19%, Non-attached 19%, Greens 15%) — exactly the subset where value lives.
- **Security note:** the entire `/api` (70 resources, 1.2M vote rows) is queryable with
  no key; the paywall only hides the quiz→vote mapping in the UI. Competitive-intel
  source for us; material data exposure for them.

## 5. MEPanalytics — detail (public)
- AI political-intelligence platform: legislative tracking proposal→plenary, MEP-level
  vote prediction, Brussels PA knowledge base (MEPs, votes, speeches, procedures),
  parliamentary calendar.
- Proprietary ML + Monte Carlo + scenario analysis; claims 80% accuracy; 720 MEPs,
  2.9M+ votes, 10+ years history.
- Positioned squarely at public-affairs advocates. Pricing not public; "Get Early
  Access" implies a gated subscription, pre-scale.
- **The threat:** it is Praevisa's exact technical thesis with a far deeper data moat.
  **The risk to monitor:** nothing stops a funded, data-rich rival from adding Council —
  which is Praevisa's entire moat.

## 6. Profitability verdict
- **As a standalone vote-predictor: low.** Third into a two-sided squeeze (data-rich
  forward incumbent + free influence map), with a weaker data position than one and a
  worse price than the other.
- **As a Council-side flip-targeting tool for the contested tail: conditionally viable
  and genuinely defensible** — the one thing *neither* competitor does, where the engine
  is validated, wrapped in judgment rather than a leaderboard number. Narrow (5–15 PA
  retainers, ~€100–300k ARR), but real.

## 7. Strategy
Don't fight MEPanalytics on MEP-level accuracy or EU Matrix on coverage/price. **Own
the Council and the flip** — sell "who decides this file and how to move them," the
deliverable both rivals structurally cannot produce. Monitor MEPanalytics directly for
any move into Council-side modelling; that is the single biggest risk to this position.

---
*Deliverables: `eumatrix_quizzes.csv` (306), `eumatrix_gov_tension_model.csv` (27 govts),
`eumatrix_party_family_votes.csv` (9 families). Flip analysis: `praevisa/flip.py`,
validated in `validate_pivots.py`.*
