# Praevisa Engine - EU Legislative Prediction Intelligence
"""Demo entry point. Runs three illustrative proposals through the engine."""

from praevisa import PolicyProposal, PolicyType, PredictionEngine


SCENARIOS = [
    PolicyProposal(
        title="Carbon Border Adjustment Expansion",
        policy_type=PolicyType.OLP,
        # Industrial/integration framing dominates; mild green, mild right.
        position=(0.5, -2.0, 4.5),
        salience=(1.0, 0.8, 1.4),
        rapporteur_group="EPP",
        description="Extends CBAM scope to downstream products and services.",
    ),
    PolicyProposal(
        title="Common EU Defence Procurement Fund",
        policy_type=PolicyType.OLP,
        # Strongly pro-integration, slightly right of centre, security framing.
        position=(1.0, 2.5, 6.0),
        salience=(0.4, 0.8, 1.6),
        rapporteur_group="EPP",
        description="Pools defence procurement budget across member states.",
    ),
    PolicyProposal(
        title="Minimum Corporate Tax Rate Harmonisation",
        policy_type=PolicyType.UNANIMITY,
        # Left-economic, pro-integration, neutral on culture.
        position=(-3.0, 0.0, 5.0),
        salience=(1.5, 0.4, 1.1),
        description="Sets a binding 18% minimum corporate income tax floor.",
    ),
]


def main() -> None:
    print("Praevisa Engine v0.2  -  EU Legislative Prediction Intelligence")
    print("=" * 70)
    engine = PredictionEngine(n_runs=300, base_seed=42)
    for policy in SCENARIOS:
        prediction = engine.predict(policy)
        print()
        print(prediction.report())
        print("-" * 70)


if __name__ == "__main__":
    main()
