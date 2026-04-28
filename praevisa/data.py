"""EU institutional data for the 10th European Parliament (2024-2029).

Positions are on a [-10, +10] scale across three dimensions:
  - econ:    economic left (-) vs right (+)
  - gal_tan: green/alternative/libertarian (-) vs traditional/authoritarian/nationalist (+)
  - eu:      eurosceptic (-) vs pro-integration (+)

Group seats and member-state populations are static institutional data.
Ideological positions are derived from CHES 2024 (Jolly et al.) by
`praevisa.ches`: EP group positions are seats-weighted aggregates of the
parties affiliated to each group; member-state positions are weighted
aggregates over the current governing coalition.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ches


@dataclass(frozen=True)
class PoliticalGroup:
    code: str
    name: str
    seats: int
    position: tuple[float, float, float]
    cohesion: float


@dataclass(frozen=True)
class MemberStateInfo:
    code: str
    name: str
    population_millions: float
    position: tuple[float, float, float]


# Static seat counts and cohesion priors. Cohesion estimates come from
# Hix/Noury/Roland and successor work — refresh once roll-call data for
# the 10th term accumulates.
_GROUPS_STATIC: tuple[tuple[str, str, int, float], ...] = (
    ("EPP",    "European People's Party",             188, 0.91),
    ("S&D",    "Socialists and Democrats",            136, 0.93),
    ("PfE",    "Patriots for Europe",                  84, 0.78),
    ("ECR",    "European Conservatives & Reformists",  78, 0.85),
    ("Renew",  "Renew Europe",                         77, 0.88),
    ("Greens", "Greens / European Free Alliance",      53, 0.95),
    ("Left",   "The Left",                             46, 0.88),
    ("ESN",    "Europe of Sovereign Nations",          25, 0.72),
    ("NI",     "Non-attached",                         33, 0.30),
)

_STATES_STATIC: tuple[tuple[str, str, float], ...] = (
    ("DE", "Germany",       84.4),
    ("FR", "France",        68.4),
    ("IT", "Italy",         59.0),
    ("ES", "Spain",         48.6),
    ("PL", "Poland",        36.8),
    ("RO", "Romania",       19.0),
    ("NL", "Netherlands",   17.9),
    ("BE", "Belgium",       11.7),
    ("CZ", "Czechia",       10.9),
    ("SE", "Sweden",        10.6),
    ("PT", "Portugal",      10.6),
    ("EL", "Greece",        10.4),
    ("HU", "Hungary",        9.6),
    ("AT", "Austria",        9.2),
    ("BG", "Bulgaria",       6.4),
    ("DK", "Denmark",        5.9),
    ("FI", "Finland",        5.6),
    ("SK", "Slovakia",       5.4),
    ("IE", "Ireland",        5.3),
    ("HR", "Croatia",        3.8),
    ("LT", "Lithuania",      2.9),
    ("SI", "Slovenia",       2.1),
    ("LV", "Latvia",         1.9),
    ("EE", "Estonia",        1.4),
    ("CY", "Cyprus",         0.9),
    ("LU", "Luxembourg",     0.7),
    ("MT", "Malta",          0.6),
)


def _build_groups() -> tuple[PoliticalGroup, ...]:
    positions = ches.compute_ep_group_positions()
    return tuple(
        PoliticalGroup(
            code=code,
            name=name,
            seats=seats,
            position=positions.get(code, (0.0, 0.0, 0.0)),
            cohesion=cohesion,
        )
        for code, name, seats, cohesion in _GROUPS_STATIC
    )


def _build_states() -> tuple[MemberStateInfo, ...]:
    positions = ches.compute_member_state_positions()
    return tuple(
        MemberStateInfo(
            code=code,
            name=name,
            population_millions=pop,
            position=positions.get(code, (0.0, 0.0, 5.0)),
        )
        for code, name, pop in _STATES_STATIC
    )


EP_GROUPS: tuple[PoliticalGroup, ...] = _build_groups()
EP_TOTAL_SEATS = sum(g.seats for g in EP_GROUPS)  # 720

MEMBER_STATES: tuple[MemberStateInfo, ...] = _build_states()
EU_TOTAL_POPULATION_MILLIONS = sum(ms.population_millions for ms in MEMBER_STATES)


def group_by_code(code: str) -> PoliticalGroup:
    for g in EP_GROUPS:
        if g.code == code:
            return g
    raise KeyError(f"Unknown EP group: {code}")


def member_state_by_code(code: str) -> MemberStateInfo:
    for ms in MEMBER_STATES:
        if ms.code == code:
            return ms
    raise KeyError(f"Unknown member state: {code}")
