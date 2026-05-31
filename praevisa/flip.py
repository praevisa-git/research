"""Flip analysis — invert a prediction into a targeting plan.

The prediction engine answers "will this file pass?". A public-affairs team
cannot act on a probability; they act on *who* decides it. Flip analysis runs
the engine, then searches for the cheapest, most realistic change that reverses
the modal outcome — and names the actors who carry it:

  * Council levers — the smallest set of governments to win (or peel off) to
    cross / break the QMV double threshold (>=15 states AND >=65% population).
  * EP levers       — the pivot political group closest to flipping its line.
  * Text levers     — the minimal amendment (shift in the proposal's position)
    that moves the majority, i.e. the rapporteur-controllable path.

Council levers are the headline: EU files die in Council, and *which* states
are pivotal is a structural property of the QMV arithmetic — far more stable
across Monte Carlo runs than the headline adoption probability, which is noisy.
That stability is the point: flip analysis sidesteps the run-to-run variance of
a point prediction by reporting structure, not a number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .data import (
    EP_GROUPS,
    EU_TOTAL_POPULATION_MILLIONS,
    MEMBER_STATES,
    member_state_by_code,
)
from .model import QMV_POPULATION_THRESHOLD, QMV_STATE_THRESHOLD
from .policy import PolicyProposal, PolicyType
from .prediction import Prediction, PredictionEngine

# QMV needs >=55% of states; with 27 members that is ceil(0.55 * 27) = 15.
QMV_STATE_COUNT = math.ceil(QMV_STATE_THRESHOLD * len(MEMBER_STATES))
AXES = ("econ", "gal_tan", "eu")


@dataclass
class StateLever:
    """One government as a flip target, with its cost and value."""

    code: str
    name: str
    population_millions: float
    yes_rate: float            # modal P(votes yes) from the engine
    resistance: float          # how far from a coin-flip toward the needed side
    pop_share: float           # share of EU population this state carries

    @property
    def feasibility(self) -> str:
        # A state already near 50/50 is winnable; one deep in its camp is not.
        if self.resistance <= 0.10:
            return "winnable"
        if self.resistance <= 0.25:
            return "hard"
        return "entrenched"


@dataclass
class FlipPath:
    """A concrete, named route that reverses the modal outcome."""

    lever: str                 # "council" | "ep" | "text"
    headline: str
    actors: list[str] = field(default_factory=list)
    detail: list[str] = field(default_factory=list)
    realistic: bool = True     # False ⇒ only entrenched targets exist


@dataclass
class FlipAnalysis:
    policy: PolicyProposal
    prediction: Prediction
    modal_council_pass: bool
    modal_yes_states: list[str]
    modal_pop_share: float
    direction: str             # "to-pass" or "to-block"
    paths: list[FlipPath]

    def report(self) -> str:
        p = self.prediction
        lines: list[str] = []
        lines.append(f"Praevisa flip analysis — {self.policy.title}")
        lines.append(f"  Procedure : {self.policy.policy_type.value}")
        lines.append("")
        gate = "unanimity gate" if self.policy.policy_type == PolicyType.UNANIMITY else "QMV gate"
        lines.append(
            f"  Modal read : Council {len(self.modal_yes_states)}/27 states, "
            f"{self.modal_pop_share:.0%} population "
            f"-> {'PASSES' if self.modal_council_pass else 'FAILS'} the {gate}"
        )
        lines.append(
            f"  Engine     : P(adopt) {p.adoption_probability:.0%} "
            f"(noisy — treat as direction, not a point)"
        )
        lines.append(
            f"  Objective  : reverse the outcome — {self.direction.upper()}"
        )
        lines.append("")
        if not self.paths:
            lines.append("  No realistic flip path found within the search space.")
            return "\n".join(lines)
        decided = self.paths and self.paths[0].lever == "council" and not self.paths[0].realistic
        if decided:
            lines.append(
                "  VERDICT: structurally decided — no realistic Council flip. "
                "Don't spend lobbying here; the only lever is the text."
            )
            lines.append("")
        for i, path in enumerate(self.paths, 1):
            flag = "" if path.realistic else "  (not realistic — entrenched)"
            lines.append(f"  [{path.lever.upper()} PATH {i}] {path.headline}{flag}")
            if path.actors:
                shown = ", ".join(path.actors[:8]) + ("…" if len(path.actors) > 8 else "")
                lines.append(f"      Target: {shown}")
            for d in path.detail:
                lines.append(f"      - {d}")
            lines.append("")
        return "\n".join(lines).rstrip()


def _council_modal(
    policy: PolicyProposal, pred: Prediction
) -> tuple[list[str], float, bool]:
    """Deterministic 'modal' Council tally: each state votes its majority side.

    Unanimity files clear only with all 27; QMV files use the double threshold.
    """
    yes = [ms for ms in MEMBER_STATES if pred.state_yes_rates[ms.code] >= 0.5]
    yes_pop = sum(ms.population_millions for ms in yes)
    pop_share = yes_pop / EU_TOTAL_POPULATION_MILLIONS
    if policy.policy_type == PolicyType.UNANIMITY:
        passes = len(yes) == len(MEMBER_STATES)
    else:
        passes = len(yes) >= QMV_STATE_COUNT and pop_share >= QMV_POPULATION_THRESHOLD
    return [ms.code for ms in yes], pop_share, passes


def _gain_path(pred: Prediction, yes_codes: list[str], pop_share: float) -> FlipPath:
    """Failing file: cheapest set of No-states to win to clear the QMV gate."""
    yes_set = set(yes_codes)
    candidates = []
    for ms in MEMBER_STATES:
        if ms.code in yes_set:
            continue
        rate = pred.state_yes_rates[ms.code]
        resistance = max(0.02, 0.5 - rate)           # distance to win it over
        candidates.append(
            StateLever(
                code=ms.code,
                name=ms.name,
                population_millions=ms.population_millions,
                yes_rate=rate,
                resistance=resistance,
                pop_share=ms.population_millions / EU_TOTAL_POPULATION_MILLIONS,
            )
        )
    # Efficiency = population delivered per unit of persuasion effort.
    candidates.sort(key=lambda lv: lv.pop_share / lv.resistance, reverse=True)

    chosen: list[StateLever] = []
    count = len(yes_codes)
    pop = pop_share
    for lv in candidates:
        if count >= QMV_STATE_COUNT and pop >= QMV_POPULATION_THRESHOLD:
            break
        chosen.append(lv)
        count += 1
        pop += lv.pop_share

    detail = [
        f"{lv.name} ({lv.code}) — {lv.population_millions:.0f}M, "
        f"now {lv.yes_rate:.0%} yes, {lv.feasibility}"
        for lv in chosen
    ]
    detail.append(
        f"=> reaches {count}/27 states and {pop:.0%} population "
        f"(needs {QMV_STATE_COUNT}/27 and {QMV_POPULATION_THRESHOLD:.0%})"
    )
    realistic = bool(chosen) and all(lv.feasibility != "entrenched" for lv in chosen)
    return FlipPath(
        lever="council",
        headline=(
            f"Win {len(chosen)} government(s) to cross the QMV gate"
            if chosen
            else "Already at the gate — no Council gain required"
        ),
        actors=[lv.code for lv in chosen],
        detail=detail,
        realistic=realistic,
    )


def _block_path(pred: Prediction, yes_codes: list[str], pop_share: float) -> FlipPath:
    """Passing file: cheapest blocking minority — peel population below 65%."""
    yes_levers = []
    for code in yes_codes:
        ms = member_state_by_code(code)
        rate = pred.state_yes_rates[code]
        resistance = max(0.02, rate - 0.5)            # distance to flip it to No
        yes_levers.append(
            StateLever(
                code=code,
                name=ms.name,
                population_millions=ms.population_millions,
                yes_rate=rate,
                resistance=resistance,
                pop_share=ms.population_millions / EU_TOTAL_POPULATION_MILLIONS,
            )
        )
    # A blocking minority on population needs to remove enough to drop below 65%.
    pop_to_remove = pop_share - QMV_POPULATION_THRESHOLD
    yes_levers.sort(key=lambda lv: lv.pop_share / lv.resistance, reverse=True)

    chosen: list[StateLever] = []
    removed = 0.0
    count = len(yes_codes)
    for lv in yes_levers:
        # Stop once either threshold is broken.
        if removed > pop_to_remove or count < QMV_STATE_COUNT:
            break
        chosen.append(lv)
        removed += lv.pop_share
        count -= 1

    detail = [
        f"{lv.name} ({lv.code}) — {lv.population_millions:.0f}M, "
        f"now {lv.yes_rate:.0%} yes, {'flippable' if lv.feasibility == 'winnable' else lv.feasibility}"
        for lv in chosen
    ]
    detail.append(
        f"=> drops yes-population to {(pop_share - removed):.0%} "
        f"(a blocking minority forms below {QMV_POPULATION_THRESHOLD:.0%})"
    )
    realistic = bool(chosen) and all(lv.feasibility != "entrenched" for lv in chosen)
    return FlipPath(
        lever="council",
        headline=f"Peel off {len(chosen)} government(s) to build a blocking minority",
        actors=[lv.code for lv in chosen],
        detail=detail,
        realistic=realistic,
    )


def _unanimity_path(
    pred: Prediction, yes_codes: list[str], council_pass: bool
) -> FlipPath:
    """Unanimity files: blocking needs one defector; passing needs every holdout."""
    yes_set = set(yes_codes)
    if council_pass:
        # Already unanimous — to block, win the single most flippable state.
        levers = [
            (code, member_state_by_code(code), pred.state_yes_rates[code])
            for code in yes_codes
        ]
        code, ms, rate = min(levers, key=lambda t: t[2] - 0.5)
        return FlipPath(
            lever="council",
            headline="One defector kills it — unanimity has no blocking-minority math",
            actors=[code],
            detail=[
                f"Easiest hold-out: {ms.name} ({code}) at {rate:.0%} yes",
                "Any single 'no' vote sinks a unanimity file — find the weakest link",
            ],
            realistic=(rate - 0.5) <= 0.25,
        )
    # Failing — every No state must be converted; unanimity is the hard gate.
    holdouts = [
        (ms, pred.state_yes_rates[ms.code])
        for ms in MEMBER_STATES
        if ms.code not in yes_set
    ]
    holdouts.sort(key=lambda t: t[1])  # hardest first
    detail = [
        f"{ms.name} ({ms.code}) — {rate:.0%} yes, "
        f"{'winnable' if rate >= 0.40 else 'entrenched'}"
        for ms, rate in holdouts
    ]
    detail.append(f"=> all {len(holdouts)} hold-outs must flip; one refusal blocks it")
    return FlipPath(
        lever="council",
        headline=f"Unanimity: win every one of {len(holdouts)} hold-out government(s)",
        actors=[ms.code for ms, _ in holdouts],
        detail=detail,
        realistic=all(rate >= 0.40 for _, rate in holdouts),
    )


def _ep_pivot_path(pred: Prediction) -> FlipPath | None:
    """Name the EP group whose line is closest to flipping, weighted by seats."""
    sized = [
        (g, pred.group_yes_rates.get(g.code, 0.0))
        for g in EP_GROUPS
        if g.code != "NI" and g.seats >= 40
    ]
    if not sized:
        return None
    # Pivot = sizable group nearest its internal 50/50.
    pivot, rate = min(sized, key=lambda gr: abs(gr[1] - 0.5))
    swing_seats = int(round(pivot.seats * abs(rate - 0.5) * 2))
    direction = "for" if rate >= 0.5 else "against"
    return FlipPath(
        lever="ep",
        headline=f"{pivot.code} is the pivot group ({pivot.seats} seats)",
        actors=[pivot.code],
        detail=[
            f"Currently leans {direction} at {rate:.0%} internal yes — "
            f"the closest large group to flipping its line",
            f"Swinging its whip moves roughly {swing_seats} seats; "
            f"groups already at 0%/100% are locked and not worth lobbying",
        ],
    )


def _text_paths(
    engine: PredictionEngine,
    policy: PolicyProposal,
    baseline_pass: bool,
    grid: tuple[float, ...] = (-3.0, -1.5, 1.5, 3.0),
) -> list[FlipPath]:
    """Smallest single-axis amendment that flips the adoption direction."""
    paths: list[FlipPath] = []
    for axis_idx, axis in enumerate(AXES):
        best: tuple[float, float] | None = None  # (abs delta, signed delta)
        best_prob = None
        for delta in sorted(grid, key=abs):
            pos = list(policy.position)
            pos[axis_idx] += delta
            moved = PolicyProposal(
                title=policy.title,
                policy_type=policy.policy_type,
                position=tuple(pos),
                salience=policy.salience,
                rapporteur_group=policy.rapporteur_group,
                description=policy.description,
            )
            prob = engine.predict(moved).adoption_probability
            flips = (prob >= 0.5) != baseline_pass
            if flips and (best is None or abs(delta) < best[0]):
                best = (abs(delta), delta)
                best_prob = prob
        if best is not None:
            sign = "+" if best[1] > 0 else ""
            paths.append(
                FlipPath(
                    lever="text",
                    headline=f"Amend the {axis} content by {sign}{best[1]:.1f}",
                    detail=[
                        f"Shifting the proposal {sign}{best[1]:.1f} on {axis} "
                        f"moves P(adopt) across 0.5 (to {best_prob:.0%})",
                        "Rapporteur-controllable — no government lobbying required",
                    ],
                )
            )
    return paths


def analyse_flip(
    policy: PolicyProposal,
    engine: PredictionEngine | None = None,
) -> FlipAnalysis:
    """Run the engine and build the cheapest outcome-reversing plan."""
    engine = engine or PredictionEngine(n_runs=300, base_seed=42)
    pred = engine.predict(policy)
    yes_codes, pop_share, council_pass = _council_modal(policy, pred)

    paths: list[FlipPath] = []
    direction = "to-block" if council_pass else "to-pass"
    if policy.policy_type == PolicyType.UNANIMITY:
        paths.append(_unanimity_path(pred, yes_codes, council_pass))
    elif council_pass:
        paths.append(_block_path(pred, yes_codes, pop_share))
    else:
        paths.append(_gain_path(pred, yes_codes, pop_share))

    ep = _ep_pivot_path(pred)
    if ep is not None:
        paths.append(ep)

    paths.extend(_text_paths(engine, policy, baseline_pass=council_pass))

    return FlipAnalysis(
        policy=policy,
        prediction=pred,
        modal_council_pass=council_pass,
        modal_yes_states=yes_codes,
        modal_pop_share=pop_share,
        direction=direction,
        paths=paths,
    )
