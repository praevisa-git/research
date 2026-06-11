"""Pre-registration tests for the plenary forward ledger's grading rules.

These pin the PAIRING and SCORING behavior before the session, so the grade run
after the votes is mechanical: if any of this changes post-session, the diff shows it.
No network: rows are fixtures shaped like the HowTheyVote bulk CSV.
"""

import unittest

from praevisa import plenary_forward as pf


def _row(**kw):
    base = {
        "id": "1", "timestamp": "2026-06-17 12:45:00", "display_title": "",
        "procedure_title": "", "procedure_reference": "", "description": "",
        "is_main": "True", "result": "ADOPTED",
        "count_for": "400", "count_against": "200", "count_abstention": "50",
    }
    base.update(kw)
    return base


class TestTokens(unittest.TestCase):
    def test_accents_and_stopwords(self):
        t = pf._tokens("Türkiye — the 2025 Commission report")
        self.assertIn("turkiye", t)
        self.assertNotIn("the", t)
        self.assertNotIn("2025", t)        # boilerplate year is stopworded
        self.assertNotIn("commission", t)  # boilerplate institution is stopworded


class TestMatchRow(unittest.TestCase):
    def test_procedure_reference_beats_title(self):
        item = {"a10": "X", "title": "Anything at all", "procedure": "2024/0319(COD)"}
        rows = [
            _row(id="9", procedure_reference="2024/0319(COD)",
                 display_title="totally different words"),
            _row(id="8", display_title="Anything at all"),
        ]
        row, how = pf._match_row(item, rows, {})
        self.assertEqual(row["id"], "9")
        self.assertEqual(how, "procedure")

    def test_title_containment_threshold(self):
        item = {"a10": None, "title": "Political repression and humanitarian "
                                      "situation in Cuba", "procedure": None}
        good = _row(id="5", display_title="Resolution on the political repression "
                                          "and the humanitarian situation in Cuba")
        rows = [good, _row(id="6", display_title="Something about fisheries")]
        row, how = pf._match_row(item, rows, {})
        self.assertEqual(row["id"], "5")
        self.assertTrue(how.startswith("title:"))

    def test_no_match_below_threshold(self):
        item = {"a10": None, "title": "Recruitment of children by organised crime",
                "procedure": None}
        rows = [_row(id="7", display_title="EU-Pakistan tariff rate quotas")]
        row, how = pf._match_row(item, rows, {})
        self.assertIsNone(row)
        self.assertIn("no title match", how)

    def test_vote_id_override_wins(self):
        item = {"a10": "A10-0001/2026", "title": "x", "procedure": "2024/0319(COD)"}
        rows = [_row(id="9", procedure_reference="2024/0319(COD)"), _row(id="3")]
        row, how = pf._match_row(item, rows, {"A10-0001/2026": {"vote_id": "3"}})
        self.assertEqual(row["id"], "3")
        self.assertEqual(how, "override:vote_id")


class TestScoring(unittest.TestCase):
    def test_observed_share_ignores_abstentions(self):
        self.assertAlmostEqual(pf._observed_share(_row(count_for="300",
                                                       count_against="100",
                                                       count_abstention="999")), 0.75)

    def test_scorecard_always_adopted_counts_observed(self):
        ledger = {"items": [
            {"title": "a", "signal": "prior", "contested": None, "outcome": "ADOPTED",
             "graded": {"observed_result": "ADOPTED", "outcome_hit": True,
                        "share_abs_err": 0.10, "graded_at": "2026-06-19"}},
            {"title": "b", "signal": "committee:report", "contested": True,
             "outcome": "ADOPTED",
             "graded": {"observed_result": "REJECTED", "outcome_hit": False,
                        "share_abs_err": 0.30, "graded_at": "2026-06-19"}},
            {"title": "c", "a10": None, "signal": "prior", "contested": None,
             "outcome": "ADOPTED"},  # pending
        ]}
        sc = pf._scorecard(ledger)
        self.assertEqual(sc["n_graded"], 2)
        self.assertEqual(sc["n_pending"], 1)
        # naive baseline hits exactly the observed-ADOPTED count, on the same items
        self.assertEqual(sc["by_rail"]["always-ADOPTED"]["outcome_hits"], 1)
        self.assertEqual(sc["by_rail"]["always-ADOPTED"]["n"], 2)
        self.assertEqual(sc["by_rail"]["prior"],
                         {"n": 1, "outcome_hits": 1, "share_mae": 0.10, "brier": None})
        self.assertEqual(sc["by_rail"]["committee"],
                         {"n": 1, "outcome_hits": 0, "share_mae": 0.30, "brier": None})
        self.assertEqual(sc["contested"]["n"], 1)
        self.assertEqual(sc["contested"]["outcome_hits"], 0)


class TestSecondReading(unittest.TestCase):
    def test_threshold_not_simple_majority(self):
        # 55% yes-share would pass a simple majority but here ~45% of 720 ≈ 324
        # seats against < 361 -> position stands either way; push opposition past
        # 361 and the call must flip.
        entry = {"per_group": {g: 0.30 for g in pf.GROUPS}}
        out = pf._second_reading(dict(entry, outcome="x"))
        self.assertEqual(out["outcome"], "CONTESTED-2ND-READING")
        entry = {"per_group": {g: 0.60 for g in pf.GROUPS}}
        out = pf._second_reading(dict(entry, outcome="x"))
        self.assertEqual(out["outcome"], "ADOPTED")
        self.assertEqual(out["second_reading"]["threshold"], 361)


if __name__ == "__main__":
    unittest.main()
