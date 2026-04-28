"""Sensitivity sweep for 2025/0408(COD) — Biocidal Products data protection."""

from praevisa import PolicyProposal, PolicyType, PredictionEngine

BASE = dict(
    title="Biocidal Products Reg - Data Protection Extension",
    policy_type=PolicyType.OLP,
    position=(1.5, 0.5, 3.0),
    salience=(0.6, 0.4, 0.9),
    rapporteur_group="S&D",
)

AXES = ["econ", "gal_tan", "eu"]
DELTAS = [-3.0, -1.5, 0.0, 1.5, 3.0]
SAL_MULT = [0.5, 1.0, 2.0]

engine = PredictionEngine(n_runs=200, base_seed=42)


def with_position(axis_idx: int, delta: float) -> PolicyProposal:
    pos = list(BASE["position"])
    pos[axis_idx] = BASE["position"][axis_idx] + delta
    return PolicyProposal(**{**BASE, "position": tuple(pos)})


def with_salience(axis_idx: int, mult: float) -> PolicyProposal:
    sal = list(BASE["salience"])
    sal[axis_idx] = BASE["salience"][axis_idx] * mult
    return PolicyProposal(**{**BASE, "salience": tuple(sal)})


def main() -> None:
    print("Sensitivity sweep — 2025/0408(COD)")
    print("=" * 70)
    base_pred = engine.predict(PolicyProposal(**BASE))
    print(
        f"Baseline: P(adopt)={base_pred.adoption_probability:.1%}  "
        f"EP yes={base_pred.expected_ep_yes_share:.1%}  "
        f"Council states={base_pred.expected_council_yes_states:.1f}/27"
    )
    print()

    print("Position shifts (each axis ±delta from baseline):")
    print(f"  {'axis':<8} {'delta':>6}  {'P(adopt)':>9} {'EP yes':>8} {'Council':>9}")
    for axis_idx, axis in enumerate(AXES):
        for d in DELTAS:
            p = engine.predict(with_position(axis_idx, d))
            print(
                f"  {axis:<8} {d:+6.1f}  "
                f"{p.adoption_probability:>9.1%} "
                f"{p.expected_ep_yes_share:>8.1%} "
                f"{p.expected_council_yes_states:>5.1f}/27"
            )
        print()

    print("Salience multipliers (per axis):")
    print(f"  {'axis':<8} {'mult':>5}  {'P(adopt)':>9} {'EP yes':>8} {'Council':>9}")
    for axis_idx, axis in enumerate(AXES):
        for m in SAL_MULT:
            p = engine.predict(with_salience(axis_idx, m))
            print(
                f"  {axis:<8} {m:>5.1f}  "
                f"{p.adoption_probability:>9.1%} "
                f"{p.expected_ep_yes_share:>8.1%} "
                f"{p.expected_council_yes_states:>5.1f}/27"
            )
        print()


if __name__ == "__main__":
    main()
