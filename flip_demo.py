# Praevisa — Flip Analysis demo
"""Run the flip-analysis layer on a few illustrative files.

Flip analysis inverts the prediction: instead of a P(adopt) number, it returns
the cheapest, named route to reverse the modal outcome — the targeting plan a
public-affairs team actually buys.
"""

from praevisa import PolicyProposal, PolicyType, PredictionEngine, analyse_flip


SCENARIOS = [
    # 1. CONTESTED — scrapes over the QMV gate, ~9 swing governments in play.
    #    This is where flip analysis earns its keep: a crisp, winnable target list.
    PolicyProposal(
        title="Single Market Enforcement Powers - New Competences",
        policy_type=PolicyType.OLP,
        position=(1.5, 0.0, 1.0),
        salience=(1.0, 0.6, 1.0),
        rapporteur_group="EPP",
    ),
    # 2. BLOWOUT — structurally decided; the tool should say "don't spend here".
    PolicyProposal(
        title="Biocidal Products Reg - Data Protection Extension",
        policy_type=PolicyType.OLP,
        position=(1.5, 0.5, 3.0),
        salience=(0.6, 0.4, 0.9),
        rapporteur_group="S&D",
    ),
    # 3. UNANIMITY — one defector blocks it; no blocking-minority math applies.
    PolicyProposal(
        title="Minimum Corporate Tax Rate Harmonisation",
        policy_type=PolicyType.UNANIMITY,
        position=(-3.0, 0.0, 5.0),
        salience=(1.5, 0.4, 1.1),
    ),
]


def main() -> None:
    print("Praevisa — Flip Analysis (targeting, not forecasting)")
    print("=" * 70)
    engine = PredictionEngine(n_runs=300, base_seed=42)
    for policy in SCENARIOS:
        analysis = analyse_flip(policy, engine)
        print()
        print(analysis.report())
        print("-" * 70)


if __name__ == "__main__":
    main()
