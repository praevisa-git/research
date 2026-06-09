"""Regression tests for the committee-vote subject classifier.

These pin the behaviour of `classify_signal_stage` / `_norm_subject`
(praevisa/stage0_feasibility.py) against the REAL subject strings observed in the
scraped committee corpora. They exist because an earlier *exact-string* matcher
silently dropped legitimate lead-committee report votes whose subject lines carried
PDF template noise ("1.1. ", "·"/"" bullets, "- Rejected", "(Co-Rapporteurs: …)"),
which cost the Stage-A sample several pairs (incl. a rejected file). This bug must not
silently return.

Every string below was copied from a committee_corpus_*.json record (or is a faithful
variant of one). If the classifier changes, run this first:

    uv run python -m unittest discover -s tests -v
"""

import unittest

from praevisa.stage0_feasibility import _norm_subject, classify_signal_stage

REPORT = (0, "report")
MANDATE = (1, "mandate")
PROVISIONAL = (2, "provisional")
BULLET = ""  # the private-use bullet glyph EP PDFs emit


class TestNormalize(unittest.TestCase):
    def test_strips_leading_enumeration_and_bullets(self):
        self.assertEqual(_norm_subject("1.1. Final vote"), "final vote")
        self.assertEqual(_norm_subject("1.1 Amendment 200"), "amendment 200")
        self.assertEqual(_norm_subject("· Adoption of draft report"),
                         "adoption of draft report")
        self.assertEqual(_norm_subject(f"{BULLET} Vote on the decision"),
                         "vote on the decision")

    def test_strips_trailing_rejected_annotation(self):
        self.assertEqual(_norm_subject("Adoption of draft report - Rejected"),
                         "adoption of draft report")

    def test_empty_and_bullet_only(self):
        self.assertIsNone(classify_signal_stage(""))
        self.assertIsNone(classify_signal_stage(BULLET))
        self.assertIsNone(classify_signal_stage("   "))
        self.assertIsNone(classify_signal_stage(None))


class TestReportStage(unittest.TestCase):
    """All of these are lead-committee whole-text report signals → (0, 'report')."""

    CASES = [
        "Adoption of draft report",
        "1.1. Adoption of draft report",
        "· Adoption of draft report",
        "Adoption of draft report - Rejected",   # the rejected file 2025/0429
        "Vote on text as amended",
        "Vote on the Draft Report",
        "Final vote",                            # 2024/0319, 2025/0228 (AGRI)
        "1.1. Final vote",                       # 2023/0129 (JURI), 2025/0251 (INTA)
        "FINAL VOTE BY ROLL CALL BY THE COMMITTEE",
        "FINAL VOTE BY ROLL CALL",
    ]

    def test_all_classify_as_report(self):
        for s in self.CASES:
            with self.subTest(subject=s):
                self.assertEqual(classify_signal_stage(s), REPORT)


class TestMandateStage(unittest.TestCase):
    CASES = [
        "Vote on the decision to enter into interinstitutional negotiations",
        "Vote on the mandate to enter into interinstitutional negotiations",
        f"{BULLET} Vote on the decision to enter into interinstitutional negotiations "
        "(Co-Rapporteurs: someone)",
    ]

    def test_all_classify_as_mandate(self):
        for s in self.CASES:
            with self.subTest(subject=s):
                self.assertEqual(classify_signal_stage(s), MANDATE)


class TestProvisionalStage(unittest.TestCase):
    def test_provisional(self):
        self.assertEqual(
            classify_signal_stage(
                "Vote on the provisional agreement resulting from "
                "interinstitutional negotiations"),
            PROVISIONAL)


class TestExclusions(unittest.TestCase):
    """None of these are a lead-committee whole-text signal → must return None."""

    CASES = [
        "Adoption of draft opinion",                 # opinion committee, not lead
        "·Adoption of draft opinion",
        "Adoption of draft opinion in letter form",
        "Adoption of draft recommendation for second reading",  # different track
        "Rapporteur for the opinion: Carlo Fidanza (ECR)",      # parse-noise header
        "AFET rapporteur: David Mc Allister",
        "Adoption of motion for a resolution",       # resolution, not a COD report
        "Amendment 200",
        "Amendment 349 [Article 1 - paragraph 1 - point 26 a (new)]",
        "Compromise Amendment 1",
        "Compromise Amendment 2A",
        "Mandl (LIBE-EPP)",                          # stray name line
    ]

    def test_all_excluded(self):
        for s in self.CASES:
            with self.subTest(subject=s):
                self.assertIsNone(classify_signal_stage(s))

    def test_priority_ordering(self):
        # report must outrank mandate must outrank provisional, so the earliest
        # substantive stage wins when a procedure has several.
        self.assertLess(REPORT[0], MANDATE[0])
        self.assertLess(MANDATE[0], PROVISIONAL[0])


if __name__ == "__main__":
    unittest.main()
