# Competitive Brief — EU Matrix (eumatrix.eu)

**Prepared for:** Praevisa · **Date:** 2026-05-31 · **Basis:** direct scrape of the public site + its open `/api` (API-Platform/Hydra) backend.

---

## 1. What they are
EU Matrix is a commercial **EU political-foresight platform** — positioning every EU actor (MEPs, EP political groups, national parties, governments, commissioners, stakeholders) on a per-policy 2D map and predicting how they will vote. Politico-nominated ("a data-driven crystal ball"). Freemium: 2 free demo quizzes, ~304 behind login.

## 2. Product surface (scraped)
- **306 "quizzes"** — each a policy dimension (e.g. *2035 CO2 Car Targets, Abortion policy, Wealth taxation, Water pollution*), grouped under taxa (Transport, Industry, EU Affairs…).
- Each quiz renders a chart: **X = policy support score, Y = influence/clout**, with custom axis labels (e.g. *EU integration ↔ Euroscepticism*).
- Adjacent modules off the same engine: **winning-majority**, **group coalitions**, **group cohesion**, **MEP loyalty**, **amendment success**, **government stability & popularity**.

## 3. Methodology (reverse-engineered)
**Pipeline:** for each quiz, ~13 input datasets split by `axisType` —
- `axisType=x` → "Initial support score" computed per actor tier (country, government, group, MEP, party, commissioner, stakeholder).
- `axisType=y` → "Overall influence (July 2024)" per tier + Country Population.
- Calibrated against tagged **real EP roll-call votes** (`quiz_rcvs`).

**Output (precomputed caches, dated 2024-07-24):**
| Layer | Rows | Signal |
|---|---:|---|
| Parties | 1,222,349 | predicted voteValue (+/0/−) |
| Governments | 135,999 | governmentPosition, oppositionPosition, **coalitionTension**, **nationalTension**, calc/manual vote |
| MEPs | 76,229 | vote + **proxy** flag + before/after revision |
| Groups | 45,333 | predicted voteValue |

Tells: MEP votes are **imputed** (`proxy`, `beforeChangesVoteValue`); votes have an automated value + **manual analyst override** (`calculatedVoteValue` vs `manualVoteValue`). It predicts, doesn't just archive.

## 4. Their core IP — and where it breaks
The **government coalition/opposition tension decomposition** is their differentiator. But aggregating all 135,999 public records by country:
- Coalition tension is wildly uneven: **LT 73, BG 56, IT 55, FI 55** vs **5 governments at exactly 0.0** (CY, EE, GR, HU, MT — unitary/single-party → the model has no coalition input and tension collapses to zero).
- `governmentPosition` clusters mildly negative for most (−6 to −16).

**Weakness:** the model degenerates where coalition structure is thin, and the whole approach is **backward-looking** (anchored on historical RCVs from one July-2024 snapshot).

## 5. Party-family voting (120k-row sample of the 1.2M party cache)
| Family | %For | %Abst | %Against | %Undet |
|---|---:|---:|---:|---:|
| EPP | 41.8 | 3.3 | 50.6 | 4.4 |
| S&D | 52.5 | 1.4 | 38.3 | 7.8 |
| Renew | 44.7 | 1.2 | 42.3 | 11.8 |
| Greens/EFA | 50.7 | 2.5 | 31.9 | 14.8 |
| The Left | 53.4 | 3.7 | 31.9 | 11.0 |
| ECR | 37.5 | 9.0 | 34.6 | 19.0 |
| Patriots | 45.0 | 13.9 | 41.0 | 0.1 |
| ESN | 38.2 | 16.5 | 45.3 | 0.0 |
| Non-attached | 43.2 | 11.7 | 25.8 | 19.2 |

*(+/− are quiz-relative, so the comparative signal is **cohesion/uncertainty**, not absolute direction.)* Read: model **uncertainty (%Undet) concentrates on the right and fringe** — ECR 19%, Non-attached 19%, Greens 15%, Renew 12% — while Patriots/ESN show ~0% undetermined but high abstention. EU Matrix is **least confident exactly on the contested, non-mainstream votes** — the subset where predictive value actually lives.

## 6. Praevisa positioning
| | EU Matrix | Praevisa |
|---|---|---|
| Signal | Historical RCVs + influence weighting + coalition tension | **CHES-grounded** party positioning |
| Time orientation | Backward (July-2024 snapshot) | Forward |
| Strongest where | Multi-party coalition governments | Contested/fringe votes, thin-coalition states |
| Failure mode | 0-tension for unitary govts; high %Undet on fringe | (target the gap) |

**Wedges:**
1. **Forward vs backward.** They calibrate on past RCVs; lead with predictive, pre-vote CHES positioning.
2. **Own the contested tail.** Their %Undet spikes on ECR/fringe/non-attached — the exact subset where 91% of votes aren't foregone. This is your edge ([[ep-vote-predictability]]).
3. **Cover their dead zone.** CHES differentiates the 5 governments their tension model zeroes out.

## 7. Security/competitive note
EU Matrix's **entire `/api` is readable without authentication** — 70 resources, all quizzes, RCVs, and the full 1.2M-row vote caches are queryable with no key (the paywall only hides the quiz→vote *mapping* in the UI, not the underlying data). This is both a competitive-intel source and, for them, a material data-exposure issue.

---
*Deliverables: `eumatrix_quizzes.csv` (306), `eumatrix_gov_tension_model.csv` (27 govts), `eumatrix_party_family_votes.csv` (9 families).*
