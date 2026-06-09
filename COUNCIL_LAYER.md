# Design — Council Layer (cross-institutional signal) + feasibility-spike verdict

**Status:** feasibility spike done · **Date:** 2026-06-09 · **Gate:** Council voting-data
access (currently BLOCKED on access engineering — data exists, endpoints not directly
pullable). Re-run the kill-switch any time: `uv run python -m praevisa.council_feasibility`.

## Why this layer
The committee→plenary signal (Stage A) forecasts the **European Parliament** side of the
ordinary legislative procedure. But a COD file becomes law only when **Parliament and the
Council of member states agree**. The Council is the half of the co-legislature where
Praevisa has *nothing* built and where — per the competitive read — much of the
hypothesised commercial value lives: lobbyists need to know which **governments** are
movable, not only which EP groups. Today the repo's only "Council" content is a *proxy*
(`validate_pivots.py` uses HowTheyVote `by_country` — MEPs grouped by country of election
— and `eumatrix_gov_tension_model.json` is a competitor's estimate). Neither is a real
Council vote. This layer is about replacing the proxy with the real thing.

## Feasibility-spike verdict (the kill-switch result)

**Conditional GO. Data exists and is correctly keyed; access is the binding constraint.**

| question | finding |
|---|---|
| Does real per-member-state Council voting data exist? | **Yes.** The Council publishes "Votes on legislative acts" as open data — country × {in favour / against / abstained / didn't participate}, with act type, **policy area**, **voting rule (QMV / unanimity)**, date. |
| Coverage / freshness? | **2009‑12 → present**, dataset **modified 2025‑03‑10** (actively maintained) per data.europa.eu metadata. |
| Can it be JOINED to our data? | **Yes — directly.** Each Council vote is tagged with the **inter‑institutional file number**, which *is* the `YYYY/NNNN(COD)` id we already key committee + plenary votes on. The probe shows **55 procedures** on our side (39 with committee data, 21 in the EP test set) as the immediate join target. |
| Is it pullable right now? | **No — access gate.** `www.consilium` is bot‑checked (HTTP 403, JS "browser check"); the documented bulk‑RDF‑zip http→https redirect 404s; the SPARQL endpoint 404s; the 2022 DiploHack sample repo is archived. This is an **access‑engineering** problem, not a missing‑data problem. |

So the layer is **not blocked on whether the data exists or pairs** — those are answered
**yes**. It is blocked on getting a working pull. Cheapest paths first:
1. **SPARQL** via the current/correct endpoint (the official metadata still lists
   `data.consilium.europa.eu/sparql`), possibly needing browser‑style headers / a session;
2. the **data.europa.eu** portal's own distribution download proxy;
3. **VoteWatch Europe** Council RCV set (EUI Cadmus, 2009–2022) as a **static historical
   backtest fallback** — real Council votes, but ends Feb 2022 (no current term).

The kill‑switch is encoded in `praevisa/council_feasibility.py`: `probe` reports access +
the pairing ceiling; `pair <file>` intersects a pulled Council file with our procedures and
counts pairable triples against an n≥5 bar. The moment an endpoint works, `pair` turns the
"55 candidates" into a real triple count with one command.

## Data source & fields (once access is solved)
Council "Votes on legislative acts" open dataset (RDF bulk + SPARQL). Per‑observation:
country; vote ∈ {for, against, abstain, didn't participate}; act type; policy area; voting
procedure & **rule (QMV / unanimity)**; Council doc number; **inter‑institutional doc
number** (the join key); session; act number & date; publication status.

## What's worth modelling (and what isn't)
- **Final adoption votes are mostly consensus** — like EP final plenary votes, most Council
  acts pass by QMV with few formal "against". Predicting "adopted" is ~free. The value is
  the **contested** Council moments: formal *against* / *abstention* by big states, and the
  earlier **"general approach" / negotiating‑mandate** position (the Council analogue of the
  committee report — a genuine *pre‑final* signal).
- **Trilogue itself is closed‑door** — no roll‑call exists, so it cannot be modelled
  directly. The tractable signals bracket it: Council general‑approach position *before*,
  formal adoption vote *after*.

## The deliverables this layer would add (mirrors the committee layer)
1. **Cross‑institutional pairing** — for files with committee + EP plenary + Council votes,
   test whether a member state's Council position predicts/constrains the EP outcome (and
   whether EP contestation predicts Council splits). The triple is the unit of evidence.
2. **Council flip analysis** — reuse the population‑weighted pivot logic already validated
   in `validate_pivots.py` (`Council pivot` heuristic) but on **real** government votes, not
   the `by_country` proxy: name the **blocking‑minority** states that flip a QMV outcome.
   This is the lobbyist's literal target on the Council side.
3. **QMV arithmetic** — unlike the EP's simple majority, Council QMV is 55% of states **and**
   65% of population; the flip math must encode both thresholds (data carries the voting
   rule per act).

## Open risks
- **Access engineering is the gate** (see verdict). Until a pull works, everything below is
  paper. Budget this as the first real task, time‑boxed; if all three access paths fail,
  fall back to the VoteWatch static set and scope the layer to a historical backtest only.
- **Consensus ceiling** — if, once pulled, the contested‑Council subset is tiny (few formal
  against/abstain on COD files that also reached our EP set), the predictive surface is thin
  and the honest move may be to ship Council **flip analysis** (deterministic QMV arithmetic
  on stated positions) rather than a probabilistic predictor. Decide after `pair` runs.
- **General‑approach data** may live in documents/PDFs (like committee mandates), not the
  clean votes dataset — a second sourcing problem for the genuinely *pre‑vote* signal.
