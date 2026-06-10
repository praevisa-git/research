# How to read these predictions — methods and pre-registered grading

*Companion to `plenary_2026-06-15_forward.json` / `.md`. Committed to git before the
part-session opens on 15 June 2026; the commit timestamp is the proof of forwardness.*

---

## 1. What this is

One prediction for **every votable item** on the European Parliament's published draft
agenda for 15–18 June 2026 — 26 items, no exceptions, no cherry-picking. Items we do
*not* predict (texts not yet tabled, possible late agenda additions) are listed by name
in the ledger before the session, not discovered afterwards.

After the session we grade every line against the official results and publish the
scorecard, including the misses. Nothing in the ledger is edited after this commit; an
item pulled from the final agenda is marked "not voted" and excluded, never re-predicted.

## 2. How a prediction is made (plain language)

For each political group we estimate the share of its members who will vote *for*. We
then weight by seats and add up. If the predicted "for" seats exceed the "against" seats,
we predict ADOPTED. That's the whole model — there is no discretionary override, and the
same code produces every line.

The estimate for each group comes from one of two **rails**, stamped on every item:

- **`prior` (the baseline)** — we know nothing item-specific, so each group gets its
  *historical average* yes-rate, measured on a frozen test set of 18 plenary roll-call
  votes from this parliamentary term (14 adopted, 4 rejected; frozen before this
  exercise and used unchanged). This is deliberately topic-blind: every prior-rail item
  shows the same 68% because the input is identical by construction.
- **`committee` / `opinion`** — a recorded committee roll-call exists for the file, so
  each group's committee yes-rate is used as its plenary forecast. `opinion(...)` marks
  the weaker case where the recorded vote comes from an opinion-giving committee rather
  than the lead committee.

**The headline percentage is a predicted seat share, not a probability.** "68%" means
"we expect about 68% of votes cast to be in favour", not "68% chance of adoption".

## 3. The math (exact)

Per group *g* with *s_g* seats, the predicted yes-rate is

> ŷ_g = α·c_g + (1 − α)·p_g

where *c_g* is the group's committee yes-rate (when a committee record exists, else the
term drops out), *p_g* is the group's prior (its mean yes-rate over the 18-file test
set), and **α = 1.0** — the identity map. A shrinkage calibration (α < 1) was tested and
*rejected*: it lowered per-group error slightly but flipped predicted rejections, so by
the pre-set decision rule (outcome accuracy on contested files beats cosmetic error
reduction) the identity stands. The α in force is committed in `results/calibration.json`.

Chamber tally, abstentions ignored, Non-attached (NI, 33 seats) excluded because they
have no group line to model:

> YES = Σ_{g≠NI} s_g·ŷ_g  NO = Σ_{g≠NI} s_g·(1 − ŷ_g)
> predicted share = YES / (YES + NO)  outcome = ADOPTED iff YES > NO

**Second reading (***II, here: NGT plants).** Plenary cannot "adopt" a Council position
— it can only amend or reject it, and that takes an **absolute majority of members
(361 of 720)**, not a majority of votes cast. So the prediction is a threshold test:
predicted seats against = Σ_g s_g·(1 − ŷ_g) over all groups; if that falls short of 361
the Council position stands and the act is deemed adopted.

**The flip lever ("EPP is the pivot group").** With margin *M* = |YES − NO|, reversing
the outcome requires ⌈M/2⌉ members to cross sides (each crosser swings 2 seats). A group
is *capable* if its own predicted losing-side seats cover that number; among capable
groups the pivot is the one with the most *movable mass*, m_g = s_g·(1 − 2·|ŷ_g − 0.5|),
which is zero for a fully locked group and maximal at 50/50. If no group passes both
gates, the item is stamped "not movable by one group". On prior-rail items this
statement is structural — EPP is the only bloc large enough to reverse a typical
majority alone — and identical across items; it becomes item-specific information only
on the committee rail.

## 4. The baseline to beat — read this before the scorecard

**A coin with ADOPTED printed on both sides gets roughly nine out of ten EP final votes
right.** Adoption is the overwhelming norm; raw outcome accuracy is therefore *not*
evidence of skill, including ours. To keep ourselves honest, the scorecard will always
show three columns:

| | what it shows |
|---|---|
| **always-ADOPTED** | the naive rule, graded on exactly the same items |
| **prior rail** | party arithmetic only — our published baseline |
| **committee rail** | the only place we claim added information |

We claim skill **only** where the committee rail beats the other two columns — in
practice, on the contested items (this session: the DEVE development-cooperation report
at a predicted 76%, and the two Liberia VPA votes at a predicted 55% with a clean
right-versus-left split). Everything else is coverage, published so the denominator of
the track record is the full agenda rather than a flattering subset.

## 5. Pre-registered grading rules (fixed now, before the votes)

1. **Sources.** Outcomes: the official plenary minutes. Vote shares and per-group rates:
   the published roll-call records (via HowTheyVote / EP open data). Items decided by
   show of hands have no roll call — they are graded on outcome only, and counted.
2. **Outcome score.** Hit = predicted ADOPTED/REJECTED matches the official result. For
   the second-reading item: hit = correct side of the 361 threshold (position stands vs
   amended/rejected).
3. **Share error** (roll-call items only): |predicted share − observed share|, with the
   observed share computed by the same convention, for / (for + against).
4. **Per-group error** (committee-rail items with a roll call): mean squared error
   between ŷ_g and the group's observed yes-rate, the same metric used throughout the
   repo's backtests.
5. **Subsets reported separately:** contested vs routine; committee rail vs prior rail
   vs always-ADOPTED; never pooled into a single headline number.
6. **No retroactive edits.** The ledger is append-only from the pre-session commit.
   Withdrawn or postponed items are marked, not deleted. If the final agenda adds votes
   after this commit, they may be predicted in a *separate, later-timestamped* ledger
   entry — clearly marked — or not at all; they are never backfilled into this one.

## 6. Known limitations, stated up front

- The prior rail is topic-blind by design; its identical rows carry no item-specific
  information, and we say so in the signal column.
- The `opinion(DEVE)` signal on the two Liberia items is from an opinion committee, not
  the lead committee — historically weaker, disclosed as such.
- Committee→plenary transfer is a tested but not statistically established signal at
  current sample sizes (an earlier significance claim was withdrawn after an audit found
  a stage-pairing leak; see the repo history — we keep the audit trail public on
  purpose).
- Small numbers: one session proves nothing. The track record is the accumulation of
  sessions, every one committed before the votes.
