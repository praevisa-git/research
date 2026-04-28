"""Mesa agents representing MEPs and Council representatives."""

from __future__ import annotations

import mesa

from .data import MemberStateInfo, PoliticalGroup
from .policy import PolicyProposal


class MEP(mesa.Agent):
    """A single Member of the European Parliament.

    Each MEP has an ideal point drawn from their group's distribution. At vote
    time they pick the group line with probability `cohesion`, otherwise they
    vote sincerely on spatial utility (with a logit perturbation).
    """

    def __init__(
        self,
        model: mesa.Model,
        group: PoliticalGroup,
        ideal_point: tuple[float, float, float],
    ) -> None:
        super().__init__(model)
        self.group = group
        self.ideal_point = ideal_point
        self.vote: bool | None = None

    def sincere_support(self, policy: PolicyProposal) -> float:
        return policy.support_probability(self.ideal_point)

    def cast_vote(self, policy: PolicyProposal, group_line: bool | None) -> bool:
        if group_line is not None and self.random.random() < self.group.cohesion:
            self.vote = group_line
        else:
            self.vote = self.random.random() < self.sincere_support(policy)
        return self.vote


class CouncilRepresentative(mesa.Agent):
    """One vote in the Council of the EU — represents a member state government."""

    def __init__(self, model: mesa.Model, state: MemberStateInfo) -> None:
        super().__init__(model)
        self.state = state
        self.vote: bool | None = None

    def cast_vote(self, policy: PolicyProposal) -> bool:
        # Governments are more disciplined and strategic than individual MEPs;
        # use a sharper temperature so the position drives the outcome.
        prob = policy.support_probability(self.state.position, temperature=2.5)
        self.vote = self.random.random() < prob
        return self.vote
