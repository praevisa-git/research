# Design — Committee Layer (rapporteur–shadow model)

**Status:** design only · **Date:** 2026-06-01 · **Gate:** committee-vote data sourcing
(see feasibility table in `COMPETITIVE_BRIEF.md` discussion). Build only after a
validation set of real committee roll-calls is assembled.

## Why a separate model (not scaled-down plenary)
Committee outcomes are decided by the **rapporteur + one shadow rapporteur per group**
(~7 people) negotiating compromise amendments — not by 88 members voting independently.
Academic evidence (Steinecke 2022; Obholzer & Wiesenthal 2024) confirms shadows are the
effective policy leaders. So modelling the ~7 negotiators is *smaller and less noisy*
than plenary, and inverts the small-N problem instead of suffering it.

## New data objects
- `Committee` — code (ENVI/ECON/IMCO/…), membership (subset of the 720 MEPs, ≈ D'Hondt
  proportional to group sizes), per-group committee seat counts.
- `CommitteeAssignment` (per file) — responsible committee, rapporteur (MEP + group),
  shadow rapporteurs (one MEP per group). Public: EP committee pages / OEIL procedure file.

## Two-stage mechanics
**Stage 1 — Negotiation → committee report position.**
The report's position in 3-D space is a weighted bargain:
```
report_pos = w_rap · rapporteur_group_pos
           + Σ_g  w_g · shadow_g_pos          (g over the other groups)
```
- `w_rap` = agenda-setter premium (rapporteur drafts; calibrate vs Steinecke's
  rapporteur-vs-shadow success rates).
- `w_g`   = group's committee seat share × salience on the file's dimensions.
Output: predicted report position **and** which shadow "asks" (compromise amendments)
are incorporated — i.e. how far each shadow pulled the text toward their group.

**Stage 2 — Committee roll-call.**
Run the existing spatial vote over committee membership, but the decisive levers are the
shadows: if a shadow's group defects, that group's committee delegation moves with it
(group-line cohesion is stronger in committee than on the floor). Output: predicted
committee FOR/AGAINST and the mandate/trilogue decision.

## Flip analysis at committee — the killer deliverable
Pivotal actors collapse from 720 MEPs / 27 governments to **~7 named individuals**:
- **Pivot shadow** = the shadow whose group's committee votes flip the report majority,
  weighted by committee seat share and proximity-to-flip (reuse `movable mass` +
  capability gate from `flip.py::_ep_pivot_path`, applied to committee seats).
- **Rapporteur lever** = move the agenda-setter → moves the whole draft.
- **Text levers** = compromise amendments, already represented as position shifts
  (reuse the sweep in `flip.py::_text_paths`).
Example output:
> "This file's content hinges on the Renew shadow (MEP X) on ENVI. Renew holds 11/88
>  committee seats and sits at econ +2.1 vs the draft's +0.5. A compromise amendment
>  moving econ +1.5 buys Renew and carries the report — without it, the mandate fails
>  committee and never reaches trilogue."

That is the lobbyist's literal job, on named people, weeks before plenary — the layer
neither MEPanalytics (plenary-only) nor EU Matrix (plenary RCVs) produces.

## Engine changes
1. `data.py` — add `Committee`, `CommitteeAssignment`, committee memberships, rapporteur/
   shadow registry (hand-maintained; this is the same living-data moat as the coalition map).
2. `committee.py` — new `CommitteeModel` (Stage 1 bargain + Stage 2 vote), analogous to
   `PraevisaModel`.
3. `flip.py` — add `_committee_path`: name the pivot shadow + the buying amendment.
4. Calibrate `w_rap` / cohesion against the Obholzer–Wiesenthal RCV set and validate
   pivot-shadow identification the way `validate_pivots.py` validated Council/EP pivots.

## Open risks
- **Data assembly** is the binding constraint (fragmented; per-meeting scrape + academic
  sets; current term needs its own collection).
- **Compromise dynamics** aren't pure spatial voting — the bargain weights are the model's
  real uncertainty; validate `w_rap` empirically before trusting Stage 1.
- **Shadow registry upkeep** — assignments change per file; this is ongoing curation
  labour (and therefore part of the moat).
