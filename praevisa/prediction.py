"""Monte Carlo prediction engine wrapped around the Mesa model."""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .data import EP_GROUPS, MEMBER_STATES, EU_TOTAL_POPULATION_MILLIONS
from .model import PraevisaModel
from .policy import PolicyProposal, PolicyType


@dataclass
class Prediction:
    policy: PolicyProposal
    n_runs: int
    adoption_probability: float
    parliament_pass_rate: float
    council_pass_rate: float
    expected_ep_yes_share: float
    ep_yes_share_band_90: tuple[float, float]
    expected_council_yes_states: float
    expected_council_pop_share: float
    group_yes_rates: dict[str, float]      # mean per-group yes share
    state_yes_rates: dict[str, float]      # P(state votes yes)
    swing_states: list[str]                # MS closest to 50/50
    expected_timeline_months: float        # rough OLP timeline estimate

    def report(self) -> str:
        lines = []
        lines.append(f"Praevisa prediction — {self.policy.title}")
        lines.append(f"  Procedure : {self.policy.policy_type.value}")
        lines.append(f"  Runs      : {self.n_runs}")
        lines.append("")
        lines.append(f"  P(adopted)             : {self.adoption_probability:6.1%}")
        lines.append(f"  P(EP passes)           : {self.parliament_pass_rate:6.1%}")
        lines.append(f"  P(Council passes)      : {self.council_pass_rate:6.1%}")
        lines.append("")
        lo, hi = self.ep_yes_share_band_90
        lines.append(
            f"  EP yes share (mean)    : {self.expected_ep_yes_share:6.1%} "
            f"(90% band {lo:.1%}–{hi:.1%})"
        )
        lines.append(
            f"  Council yes (states)   : {self.expected_council_yes_states:5.1f} / 27"
        )
        lines.append(
            f"  Council yes (pop)      : {self.expected_council_pop_share:6.1%}"
        )
        lines.append(
            f"  Expected timeline      : ~{self.expected_timeline_months:4.1f} months to adoption"
        )
        lines.append("")
        lines.append("  Group support (mean yes share within group):")
        for code, rate in sorted(
            self.group_yes_rates.items(), key=lambda kv: -kv[1]
        ):
            bar = "█" * int(round(rate * 20))
            lines.append(f"    {code:7s} {rate:5.1%}  {bar}")
        lines.append("")
        lines.append("  Member-state Yes probability:")
        for code, rate in sorted(
            self.state_yes_rates.items(), key=lambda kv: -kv[1]
        ):
            lines.append(f"    {code}  {rate:5.1%}")
        if self.swing_states:
            lines.append("")
            lines.append("  Pivotal swing states (closest to 50/50):")
            lines.append("    " + ", ".join(self.swing_states))
        return "\n".join(lines)


def _timeline_estimate(policy: PolicyProposal, adoption_prob: float) -> float:
    """Heuristic months-to-adoption.

    Empirical OLP duration averages ~18 months (Hage et al.); UNANIMITY files
    drag longer; deeply contested files (mid-range probabilities) lengthen as
    trilogues iterate. This is a heuristic, not a regression — replace with a
    learned estimator once you have ground-truth durations to fit on.
    """
    base = {
        PolicyType.OLP: 18.0,
        PolicyType.CONSULTATION_QMV: 12.0,
        PolicyType.UNANIMITY: 30.0,
    }[policy.policy_type]
    # Files near the 50/50 line tend to stall in trilogue.
    contention = 1.0 + 0.8 * (1.0 - abs(adoption_prob - 0.5) * 2)
    return base * contention


class PredictionEngine:
    """Run many `PraevisaModel` realisations and aggregate the results."""

    def __init__(self, n_runs: int = 500, base_seed: int | None = 42) -> None:
        self.n_runs = n_runs
        self.base_seed = base_seed

    def predict(self, policy: PolicyProposal) -> Prediction:
        adopted = 0
        ep_passed = 0
        council_passed = 0
        ep_yes_shares: list[float] = []
        council_states: list[int] = []
        council_pops: list[float] = []
        group_yes: dict[str, list[float]] = defaultdict(list)
        state_yes: Counter[str] = Counter()

        for run in range(self.n_runs):
            seed = None if self.base_seed is None else self.base_seed + run
            model = PraevisaModel(policy=policy, rng=seed)
            outcome = model.simulate()

            adopted += outcome.adopted
            ep_passed += outcome.parliament.passed
            council_passed += outcome.council.passed
            ep_yes_shares.append(outcome.parliament.yes_share)
            council_states.append(len(outcome.council.yes_states))
            council_pops.append(outcome.council.yes_population_share)

            for code, tally in outcome.parliament.by_group.items():
                cast = tally["yes"] + tally["no"]
                group_yes[code].append(tally["yes"] / cast if cast else 0.0)
            for code in outcome.council.yes_states:
                state_yes[code] += 1

        n = self.n_runs
        adoption_prob = adopted / n
        ep_yes_shares.sort()

        def quantile(xs: list[float], q: float) -> float:
            if not xs:
                return 0.0
            i = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
            return xs[i]

        state_rates = {ms.code: state_yes[ms.code] / n for ms in MEMBER_STATES}
        swing = sorted(state_rates.items(), key=lambda kv: abs(kv[1] - 0.5))[:5]

        return Prediction(
            policy=policy,
            n_runs=n,
            adoption_probability=adoption_prob,
            parliament_pass_rate=ep_passed / n,
            council_pass_rate=council_passed / n,
            expected_ep_yes_share=statistics.fmean(ep_yes_shares),
            ep_yes_share_band_90=(quantile(ep_yes_shares, 0.05), quantile(ep_yes_shares, 0.95)),
            expected_council_yes_states=statistics.fmean(council_states),
            expected_council_pop_share=statistics.fmean(council_pops),
            group_yes_rates={
                code: statistics.fmean(rates) if rates else 0.0
                for code, rates in group_yes.items()
            },
            state_yes_rates=state_rates,
            swing_states=[code for code, _ in swing],
            expected_timeline_months=_timeline_estimate(policy, adoption_prob),
        )
