"""Pre-registration tests for the 2026-07 signal-policy revision (H1/H2/H3).

These pin the hypotheses stated in ERROR_ANALYSIS_2026-06_ledger.md BEFORE the July
ledger is cut: H1 signal-rail eligibility (responsible committee + final vote on the
floor text + procedure-reference match, everything else demoted with disclosure),
H2 predictor abstention handling, H3 consent prior + no vector reuse. Fixtures are
faithful copies of the real corpus records that motivated the revision — above all
the DEVE Liberia record whose polarity inversion sank the June signal rail.
"""

import json
import unittest
from pathlib import Path

from praevisa import ep_flip, stage0_feasibility as s0

REPO = Path(__file__).resolve().parent.parent

# The record that caused the June failure: DEVE (opinion committee; responsible was
# INTA) voting on adoption of an AMENDED DRAFT OPINION under the accompanying
# M-procedure — subject line says only "FINAL VOTE BY ROLL CALL".
LIBERIA_DEVE = {
    "committee": "DEVE",
    "procedure": "",
    "rapporteur": "Marit Maij (S&D)",
    "title": ("Termination of the Voluntary Partnership Agreement between the "
              "European Union and the Republic of Liberia on Forest Law Enforcement "
              "Governance and Trade in timber products to the European Union "
              "(2025/0259M(NLE)) - Adoption of the draft opinion"),
    "subject": "FINAL VOTE BY ROLL CALL",
    "tally": {"+": 13, "-": 9, "0": 3},
}

# A clean responsible-committee report vote (the AGRI June winner, abridged).
AGRI_REPORT = {
    "committee": "AGRI",
    "procedure": "2024/0319(COD)",
    "rapporteur": "Céline Imart (PPE)",
    "title": "Strengthening of the position of farmers in the food supply chain",
    "subject": "Final vote",
}


class TestH1Eligibility(unittest.TestCase):
    def test_responsible_final_vote_with_matching_reference_is_eligible(self):
        ok, why = s0.signal_rail_eligible(AGRI_REPORT, "AGRI", "2024/0319(COD)")
        self.assertTrue(ok)
        self.assertEqual(why, "report")

    def test_opinion_flag_demotes(self):
        ok, why = s0.signal_rail_eligible(LIBERIA_DEVE, "DEVE", None,
                                          opinion_flagged=True)
        self.assertFalse(ok)
        self.assertEqual(why, "opinion(DEVE)")

    def test_liberia_record_demotes_even_without_the_flag(self):
        # "Adoption of the draft opinion" lives in the TITLE; the subject line alone
        # classifies as a report-stage final vote. The rule must still catch it.
        ok, why = s0.signal_rail_eligible(LIBERIA_DEVE, "INTA", None)
        self.assertFalse(ok)
        self.assertEqual(why, "opinion(DEVE)")

    def test_committee_mismatch_demotes(self):
        rec = dict(AGRI_REPORT, committee="ENVI")
        ok, why = s0.signal_rail_eligible(rec, "AGRI", "2024/0319(COD)")
        self.assertFalse(ok)
        self.assertIn("committee mismatch", why)
        self.assertIn("ENVI", why)

    def test_joint_committee_admits_either(self):
        rec = dict(AGRI_REPORT, committee="IMCO")
        ok, _ = s0.signal_rail_eligible(rec, "ENVI/IMCO", "2024/0319(COD)")
        self.assertTrue(ok)

    def test_mandate_vote_demotes(self):
        rec = dict(AGRI_REPORT, subject="Vote on the decision to enter into "
                                        "interinstitutional negotiations")
        ok, why = s0.signal_rail_eligible(rec, "AGRI", "2024/0319(COD)")
        self.assertFalse(ok)
        self.assertIn("not a final vote on the floor text", why)
        self.assertIn("mandate", why)

    def test_provisional_agreement_vote_is_eligible(self):
        # the post-trilogue text IS the object the floor votes on
        rec = dict(AGRI_REPORT, subject="Vote on the provisional agreement resulting "
                                        "from interinstitutional negotiations")
        ok, why = s0.signal_rail_eligible(rec, "AGRI", "2024/0319(COD)")
        self.assertTrue(ok)
        self.assertEqual(why, "provisional")

    def test_m_suffix_procedure_mismatch_demotes(self):
        # base procedure on the item vs M-suffixed accompanying procedure in the
        # record: reference mismatch disqualifies (H1c), even from the responsible
        # committee with a clean final-vote subject.
        rec = dict(AGRI_REPORT, procedure="",
                   title="Some agreement (2025/0259M(NLE)) - final text")
        ok, why = s0.signal_rail_eligible(rec, "AGRI", "2025/0259(NLE)")
        self.assertFalse(ok)
        self.assertIn("procedure mismatch", why)
        self.assertIn("2025/0259M(NLE)", why)

    def test_unknown_reference_on_either_side_passes_vacuously(self):
        rec = dict(AGRI_REPORT, procedure="", title="No reference here")
        ok, _ = s0.signal_rail_eligible(rec, "AGRI", "2024/0319(COD)")
        self.assertTrue(ok)
        ok, _ = s0.signal_rail_eligible(AGRI_REPORT, "AGRI", None)
        self.assertTrue(ok)

    def test_no_responsible_committee_demotes(self):
        ok, why = s0.signal_rail_eligible(AGRI_REPORT, None, None)
        self.assertFalse(ok)
        self.assertIn("committee mismatch", why)


# Renew's committee members in the Liberia record: 3 abstentions, nothing else.
H2_VOTES = [
    {"group": "PPE", "choice": "+"}, {"group": "PPE", "choice": "+"},
    {"group": "S&D", "choice": "-"},
    {"group": "Renew", "choice": "0"}, {"group": "Renew", "choice": "0"},
    {"group": "Renew", "choice": "0"},
    {"group": "ECR", "choice": "+"}, {"group": "ECR", "choice": "-"},
    {"group": "ECR", "choice": "0"},
]


class TestH2PredictorAbstentions(unittest.TestCase):
    def test_abstention_only_group_contributes_no_signal(self):
        rates = ep_flip.predictor_group_rates(H2_VOTES)
        self.assertIsNone(rates["Renew"])

    def test_abstention_only_group_falls_back_to_prior(self):
        rates = ep_flip.predictor_group_rates(H2_VOTES)
        prior = {g: 0.8 for g in ep_flip.GROUPS}
        pred = ep_flip.predict_plenary_per_group(rates, prior, alpha=1.0)
        self.assertEqual(pred["Renew"], 0.8)   # prior, not a fabricated 0.0
        self.assertEqual(pred["EPP"], 1.0)
        self.assertEqual(pred["S&D"], 0.0)

    def test_abstentions_leave_the_denominator(self):
        rates = ep_flip.predictor_group_rates(H2_VOTES)
        self.assertAlmostEqual(rates["ECR"], 0.5)   # 1+/1- of 2, not 1 of 3

    def test_measurement_basis_unchanged_decision_1(self):
        # The MEASUREMENT path keeps abstentions in the denominator (Decision 1).
        rates = s0._committee_group_rates(H2_VOTES)
        self.assertAlmostEqual(rates["ECR"], 1 / 3)
        self.assertAlmostEqual(rates["Renew"], 0.0)   # 0/3, not None

    def test_baseline_eval_artifact_still_reproduces(self):
        # H2 must not move the §9.6 measurement: recompute the full LOO evaluation
        # from the committed test set and compare against the committed artifact.
        from praevisa import baseline_eval
        from praevisa.baselines import load_testset
        recomputed = baseline_eval.evaluate(load_testset())
        committed = json.loads((REPO / "results" / "baseline_eval.json").read_text())
        self.assertEqual(json.dumps(recomputed, indent=1),
                         json.dumps(committed, indent=1))


class TestRecordProcedureRef(unittest.TestCase):
    def test_field_beats_title(self):
        rec = {"procedure": "2024/0319(COD)", "title": "blah (2025/0259M(NLE))"}
        self.assertEqual(s0.record_procedure_ref(rec), "2024/0319(COD)")

    def test_title_fallback_catches_m_suffix(self):
        self.assertEqual(s0.record_procedure_ref(LIBERIA_DEVE), "2025/0259M(NLE)")

    def test_none_when_absent(self):
        self.assertIsNone(s0.record_procedure_ref({"procedure": "", "title": "x"}))


if __name__ == "__main__":
    unittest.main()
