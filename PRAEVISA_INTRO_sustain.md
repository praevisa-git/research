# Praevisa — AI forecasting for EU legislation

**Prepared for sustAIn.brussels · June 2026**
A Brussels-based AI venture in the sustainable-and-digital innovation ecosystem.

---

## What we do

Praevisa forecasts how EU legislation moves before it is decided. For any file
in the ordinary legislative procedure, the system estimates how each political
group and each national government will vote, whether the file passes, and —
most usefully — **who would have to change their mind to flip the result.**

We cover the two chambers that actually decide a file: the **European Parliament**
and the **Council of the EU**. Most existing tools stop at the Parliament. The
Council, where files die on qualified-majority arithmetic, is where our model is
strongest and where competitors are silent.

## Why it matters for sustainability policy

The Green Deal, CSRD, the Nature Restoration Law, packaging and CO₂ rules — the
files that shape Brussels sustainability work are rarely lost in a landslide.
They turn on a handful of contested votes and a few pivotal national delegations.
Praevisa is built for exactly that contested tail: the small set of votes where
the outcome is genuinely open and where knowing *who to move* is worth more than
a headline probability. Our largest working corpus is the Parliament's
environment committee (ENVI), alongside ECON, IMCO, ITRE and LIBE.

## How it works

- **Data.** Live roll-call records (HowTheyVote.eu), expert party-position data
  (Chapel Hill), committee-stage corpora we scrape ourselves, and Council voting
  weights. A fresh clone reproduces every published number with no network access.
- **Method.** A vote-modelling ensemble at group and government level, today
  layered with expert position data and Council arithmetic. In development: a
  persona-style LLM layer reasoning over individual legislators, run Monte-Carlo
  to express uncertainty rather than a single false-confident score.
- **The differentiator — flip analysis.** Instead of selling a leaderboard, we
  identify the pivotal actors. On Council files, pivotal national delegations
  concentrate ~74% in the seven largest member states, so guidance becomes
  concrete: *"this file does not need the Parliament — it needs Germany plus any
  two of {NL, CZ, SE}."*

## Honest about the evidence

We hold ourselves to a frozen, auditable methodology. Our public baseline
results report real numbers — including the gaps that are thin on a small sample
— with bootstrap confidence intervals and significance tests, not rounded
marketing figures. Where a claim is not yet proven, we say so.

## What we are looking for from the ecosystem

We are an early-stage AI venture and would value sustAIn.brussels' support in:

- **Testing and validation** — an independent technical look at our forecasting
  and flip-targeting models.
- **Partnerships** — connections to Brussels sustainability advocates, think
  tanks and research groups (VUB/ULB) who work the contested files we model.
- **Investment and skills** — guidance on funding routes and on scaling the data
  and ML pipeline responsibly.

## In one line

> Praevisa tells you which EU votes are still in play and who to move to change
> them — a forecasting tool for the contested heart of sustainability policy.

**Contact:** praevisa@gmail.com
