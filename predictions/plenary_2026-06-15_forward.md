# Plenary forward ledger — 2026-06-15/2026-06-18 (Strasbourg)

Cut 2026-06-10 at engine rev `f859218` from the draft agenda of 2026-05-26 ([OJ](https://www.europarl.europa.eu/doceo/document/OJ-10-2026-06-15-SYN_EN.html)). alpha=1.0. 26 votable items predicted, every one BEFORE the vote.

_committee rail = Stage-A per-group committee->plenary map (ep_flip, shrinkage alpha); prior rail = baseline_A per-group plenary historical mean (party arithmetic). Seat-weighted, abstention-ignored, NI excluded from the tally. ***II items predicted against the Rule-68 absolute-majority threshold._

## Scorecard (graded post-session; rules pre-registered in `praevisa/plenary_forward.py` before the votes)

**25/26 outcome calls correct** — contested subset 3/3, graded through 2026-06-22.

| Rail | Outcome hits | Share MAE |
|---|---|---|
| always-ADOPTED | 25/26 | — |
| prior | 21/22 | 0.152 |
| committee | 4/4 | 0.236 |
| contested subset | 3/3 | 0.308 |

_Skill is claimed only where the committee rail beats both always-ADOPTED and the prior rail._


## Votes of 2026-06-16

| Item | Type | Signal | Prediction | EP yes-share | Flip lever |
|---|---|---|---|---|---|
| A10-0069/2026 Adjustment of customs duties and opening of tariff quotas for the impo | cod1 | prior | ADOPTED → ADOPTED (hit), observed 74% | 68% | EPP is the pivot group (188 seats) |
| A10-0070/2026 Non-application of customs duties on imports of certain goods | cod1 | prior | ADOPTED → ADOPTED (hit), observed 74% | 68% | EPP is the pivot group (188 seats) |
| A10-0161/2025 Strengthening of the position of farmers in the food supply chain | cod1 | committee:report | ADOPTED → ADOPTED (hit), observed 88% | 90% | No single EP group can swing it — decided on the floor |
| A10-0158/2025 Circularity requirements for vehicle design and management of end-of-l | cod1 | prior | ADOPTED → ADOPTED (hit), observed 80% | 68% | EPP is the pivot group (188 seats) |
| — Implementation of the Protocol on the financial consequences of the ex | consent | prior | ADOPTED → ADOPTED (hit), observed 93% | 68% | EPP is the pivot group (188 seats) |
| — Mobilisation of the European Globalisation Adjustment Fund — EGF/2025/ | bud | prior | ADOPTED → ADOPTED (hit), observed 93% | 68% | EPP is the pivot group (188 seats) |
| A10-0145/2026 European political parties and foundations — 2026 report | ini | prior | ADOPTED → ADOPTED (hit), observed 75% | 68% | EPP is the pivot group (188 seats) |
| A10-0142/2026 Countering transnational repression — towards an EU strategy | ini | prior | ADOPTED → ADOPTED (hit), observed 77% | 68% | EPP is the pivot group (188 seats) |
| A10-0148/2026 Role of trade in strengthening the EU's economic security | ini | prior | ADOPTED → ADOPTED (hit), observed 80% | 68% | EPP is the pivot group (188 seats) |
| A10-0147/2026 Reinforcing development cooperation to address irregular population mo | ini | committee-rcv(DEVE) **CONTESTED** | ADOPTED → ADOPTED (hit), observed 59% | 76% | No single EP group can swing it — decided on the floor |

## Votes of 2026-06-17

| Item | Type | Signal | Prediction | EP yes-share | Flip lever |
|---|---|---|---|---|---|
| — Structure and rates of excise duty applied to tobacco and tobacco rela | cns | prior | ADOPTED → REJECTED (**MISS**), observed 29% | 68% | EPP is the pivot group (188 seats) |
| — General arrangements for excise duty applied to tobacco and tobacco re | cns | prior | ADOPTED → ADOPTED (hit), observed 52% | 68% | EPP is the pivot group (188 seats) |
| — EPPO and OLAF: access to VAT information at Union level | cns | prior | ADOPTED → ADOPTED (hit), observed 94% | 68% | EPP is the pivot group (188 seats) |
| A10-0134/2026 EU-Pakistan Agreement: modification of concessions on tariff rate quot | consent | prior | ADOPTED → ADOPTED (hit), observed 96% | 68% | EPP is the pivot group (188 seats) |
| A10-0133/2026 EU-Liberia Voluntary Partnership Agreement (timber): termination | consent | opinion(DEVE) **CONTESTED** | ADOPTED → ADOPTED (hit), observed 94% | 55% | No single EP group can swing it — decided on the floor |
| A10-0146/2026 EU-Liberia Voluntary Partnership Agreement (timber): termination (reso | resolution | opinion(DEVE) **CONTESTED** | ADOPTED → ADOPTED (hit), observed 91% | 55% | No single EP group can swing it — decided on the floor |
| — Hague Convention (1980) on child abduction: accession of Cabo Verde | cns | prior | ADOPTED → ADOPTED (hit) | 68% | EPP is the pivot group (188 seats) |
| — Promoting transnational governance on water in the interests of confli | recommendation | prior | ADOPTED → ADOPTED (hit), observed 80% | 68% | EPP is the pivot group (188 seats) |
| — Plants obtained by certain new genomic techniques and their food and f | cod2 | prior | ADOPTED (predicted 232 seats against < 361 needed to amend/reject) → POSITION STANDS (hit) | 68% | EPP is the pivot group (188 seats) |
| A10-0140/2026 2025 Commission report on Georgia | ini | prior | ADOPTED → ADOPTED (hit), observed 75% | 68% | EPP is the pivot group (188 seats) |
| A10-0143/2026 2025 Commission report on Montenegro | ini | prior | ADOPTED → ADOPTED (hit), observed 83% | 68% | EPP is the pivot group (188 seats) |
| A10-0141/2026 2025 Commission report on Albania | ini | prior | ADOPTED → ADOPTED (hit), observed 82% | 68% | EPP is the pivot group (188 seats) |
| A10-0106/2026 2025 Commission report on Türkiye | ini | prior | ADOPTED → ADOPTED (hit), observed 78% | 68% | EPP is the pivot group (188 seats) |

## Votes of 2026-06-18

| Item | Type | Signal | Prediction | EP yes-share | Flip lever |
|---|---|---|---|---|---|
| — Implementation of the Urban Wastewater Treatment Directive and risks t | resolution | prior | ADOPTED → ADOPTED (hit), observed 55% | 68% | EPP is the pivot group (188 seats) |
| — Political repression and humanitarian situation in Cuba | resolution | prior | ADOPTED → ADOPTED (hit), observed 59% | 68% | EPP is the pivot group (188 seats) |
| — Recruitment of children by organised crime | resolution | prior | ADOPTED → ADOPTED (hit) | 68% | EPP is the pivot group (188 seats) |

## Not predicted in this ledger

- Rule 150 human-rights resolutions (Thursday): topics not yet defined on the draft OJ.
- Digital Omnibus on AI (A10-0073/2026): debate only on this OJ — no vote slot listed.
- Possible Rule 170 additions: the final agenda may add votes after this ledger is cut.
