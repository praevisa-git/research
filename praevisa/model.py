"""Mesa model orchestrating Parliament and Council on a single proposal."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import mesa
import networkx as nx

from .agents import MEP, CouncilRepresentative
from .data import (
    EP_GROUPS,
    EP_TOTAL_SEATS,
    EU_TOTAL_POPULATION_MILLIONS,
    MEMBER_STATES,
    PoliticalGroup,
)
from .policy import PolicyProposal, PolicyType


# Council QMV thresholds (Lisbon Treaty, Art. 16(4) TEU).
QMV_STATE_THRESHOLD = 0.55       # ≥55% of member states (≥15 of 27)
QMV_POPULATION_THRESHOLD = 0.65  # ≥65% of EU population


@dataclass
class ParliamentResult:
    yes: int
    no: int
    abstain: int
    by_group: dict[str, dict[str, int]]
    passed: bool

    @property
    def turnout(self) -> int:
        return self.yes + self.no + self.abstain

    @property
    def yes_share(self) -> float:
        return self.yes / self.turnout if self.turnout else 0.0


@dataclass
class CouncilResult:
    yes_states: list[str]
    no_states: list[str]
    yes_population_share: float
    yes_state_share: float
    passed: bool


@dataclass
class SimulationOutcome:
    parliament: ParliamentResult
    council: CouncilResult
    adopted: bool


class PraevisaModel(mesa.Model):
    """One stochastic realisation of the EU legislative pipeline.

    The model runs a single Parliament vote and a single Council vote on the
    given proposal; outer Monte Carlo loops handle the procedural cycles
    (committee, plenary, trilogue, second reading) by perturbing salience and
    re-running. Keeping the per-step model thin makes batches fast.
    """

    def __init__(
        self,
        policy: PolicyProposal,
        group_dispersion: float = 1.5,
        rng: int | None = None,
    ) -> None:
        super().__init__(rng=rng)
        self.policy = policy
        self.group_dispersion = group_dispersion
        self.influence_graph = nx.Graph()
        self._build_parliament()
        self._build_council()

    def _build_parliament(self) -> None:
        for group in EP_GROUPS:
            for _ in range(group.seats):
                ideal = tuple(
                    coord + self.random.gauss(0.0, self.group_dispersion)
                    for coord in group.position
                )
                MEP(self, group, ideal)

        # Sparse influence graph: dense within group, sparse cross-group.
        meps = list(self.agents_by_type[MEP])
        for mep in meps:
            self.influence_graph.add_node(mep.unique_id, group=mep.group.code)
        by_group: dict[str, list[MEP]] = defaultdict(list)
        for mep in meps:
            by_group[mep.group.code].append(mep)
        for group_code, members in by_group.items():
            for mep in members:
                # ~6 within-group ties — enough for opinion clustering without
                # blowing up edge count on a 720-node graph.
                peers = self.random.sample(members, k=min(6, len(members) - 1))
                for peer in peers:
                    if peer is not mep:
                        self.influence_graph.add_edge(mep.unique_id, peer.unique_id)
        # A handful of cross-group bridges per MEP (rapporteurs, shadow rapporteurs).
        for mep in meps:
            if self.random.random() < 0.05:
                other = self.random.choice(meps)
                if other is not mep:
                    self.influence_graph.add_edge(mep.unique_id, other.unique_id)

    def _build_council(self) -> None:
        for state in MEMBER_STATES:
            CouncilRepresentative(self, state)

    # -- voting ----------------------------------------------------------------

    def _group_line(self, group: PoliticalGroup) -> bool | None:
        """Decide each group's official line as the sincere majority of its MEPs."""
        if group.code == "NI":
            return None
        prob = self.policy.support_probability(group.position)
        # Slight stochastic wobble so the line itself can flip in close cases.
        return self.random.random() < prob

    def run_parliament_vote(self) -> ParliamentResult:
        lines = {g.code: self._group_line(g) for g in EP_GROUPS}
        by_group: dict[str, dict[str, int]] = {
            g.code: {"yes": 0, "no": 0, "abstain": 0} for g in EP_GROUPS
        }
        yes = no = abstain = 0
        for mep in self.agents_by_type[MEP]:
            # Small absentee rate — historical EP turnout ≈ 90–95%.
            if self.random.random() < 0.07:
                abstain += 1
                by_group[mep.group.code]["abstain"] += 1
                continue
            line = lines[mep.group.code]
            voted_yes = mep.cast_vote(self.policy, line)
            if voted_yes:
                yes += 1
                by_group[mep.group.code]["yes"] += 1
            else:
                no += 1
                by_group[mep.group.code]["no"] += 1

        # EP usually votes by simple majority of votes cast (Rule 178).
        # Some files require absolute majority of component members (361/720);
        # we approximate with simple majority of cast votes here.
        passed = yes > no
        return ParliamentResult(
            yes=yes, no=no, abstain=abstain, by_group=by_group, passed=passed
        )

    def run_council_vote(self) -> CouncilResult:
        yes_states: list[str] = []
        no_states: list[str] = []
        yes_pop = 0.0
        for rep in self.agents_by_type[CouncilRepresentative]:
            if rep.cast_vote(self.policy):
                yes_states.append(rep.state.code)
                yes_pop += rep.state.population_millions
            else:
                no_states.append(rep.state.code)

        state_share = len(yes_states) / len(MEMBER_STATES)
        pop_share = yes_pop / EU_TOTAL_POPULATION_MILLIONS

        if self.policy.policy_type == PolicyType.UNANIMITY:
            passed = len(no_states) == 0
        else:
            passed = (
                state_share >= QMV_STATE_THRESHOLD
                and pop_share >= QMV_POPULATION_THRESHOLD
            )
        return CouncilResult(
            yes_states=yes_states,
            no_states=no_states,
            yes_population_share=pop_share,
            yes_state_share=state_share,
            passed=passed,
        )

    def simulate(self) -> SimulationOutcome:
        ep = self.run_parliament_vote()
        council = self.run_council_vote()
        # OLP requires both chambers to agree. Consultation procedures only
        # require Council; EP opinion is non-binding but politically sticky,
        # so we treat strong EP opposition (<40% yes) as a soft block.
        if self.policy.policy_type == PolicyType.OLP:
            adopted = ep.passed and council.passed
        else:
            adopted = council.passed and ep.yes_share >= 0.40
        return SimulationOutcome(parliament=ep, council=council, adopted=adopted)
