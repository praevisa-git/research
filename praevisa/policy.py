"""Representation of an EU policy proposal in the prediction engine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class PolicyType(str, Enum):
    """Decision rule that applies to the file in Council.

    The ordinary legislative procedure (OLP) uses QMV in Council and simple/
    absolute majority in Parliament. A handful of files (CFSP, taxation, own
    resources, treaty change, accession) require unanimity in Council.
    """

    OLP = "ordinary_legislative_procedure"  # QMV + EP co-decision
    CONSULTATION_QMV = "consultation_qmv"   # QMV in Council, EP consulted
    UNANIMITY = "unanimity"                 # All 27 must agree


@dataclass
class PolicyProposal:
    """A Commission proposal in a 3-D ideological space.

    `position` is the proposal's location relative to the status quo (origin).
    A larger absolute value on a dimension means a bigger move from current
    policy. `salience` weights how much each dimension matters for the file
    (e.g. an environmental file has high salience on gal_tan, low elsewhere).
    """

    title: str
    policy_type: PolicyType
    position: tuple[float, float, float]
    salience: tuple[float, float, float] = (1.0, 1.0, 1.0)
    rapporteur_group: str | None = None
    description: str = ""

    def utility_for(self, ideal_point: tuple[float, float, float]) -> float:
        """Spatial utility: -salience-weighted squared distance from ideal point.

        Status quo (origin) has utility = -||ideal||² (weighted).
        An agent supports the proposal when utility(proposal) > utility(SQ).
        """
        return -sum(
            s * (p - i) ** 2
            for s, p, i in zip(self.salience, self.position, ideal_point)
        )

    def status_quo_utility(self, ideal_point: tuple[float, float, float]) -> float:
        return -sum(s * i ** 2 for s, i in zip(self.salience, ideal_point))

    def net_support(self, ideal_point: tuple[float, float, float]) -> float:
        """Positive ⇒ agent prefers proposal to status quo."""
        return self.utility_for(ideal_point) - self.status_quo_utility(ideal_point)

    def support_probability(
        self, ideal_point: tuple[float, float, float], temperature: float = 4.0
    ) -> float:
        """Logit transform of net support, used as the sincere-vote probability."""
        return 1.0 / (1.0 + math.exp(-self.net_support(ideal_point) / temperature))
