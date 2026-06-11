"""Prior v2 — type-conditional base rates and the Brier grading hook.

Pins the smoothing math, the manifest-type coverage, the committed artifact's
invariants, and that pre-v2 ledger items (no p_adopt) grade exactly as before.
"""

import unittest

from praevisa import plenary_forward as pf, prior_v2


class TestJeffreys(unittest.TestCase):
    def test_never_zero_never_one(self):
        self.assertGreater(prior_v2.jeffreys(0, 12), 0.0)
        self.assertLess(prior_v2.jeffreys(12, 12), 1.0)

    def test_values(self):
        self.assertAlmostEqual(prior_v2.jeffreys(10, 10), 10.5 / 11)
        self.assertAlmostEqual(prior_v2.jeffreys(0, 12), 0.5 / 13)


class TestTypeMap(unittest.TestCase):
    def test_every_manifest_type_mapped_except_cod2(self):
        manifest_types = {m["type"] for m in pf.MANIFEST}
        unmapped = manifest_types - set(prior_v2.LEDGER_TYPE_MAP) - {"cod2"}
        self.assertEqual(unmapped, set(),
                         f"ledger types without a v2 prior mapping: {unmapped}")

    def test_cod2_deliberately_unmapped(self):
        # ***II is a Rule-68 threshold call, not an adopt/reject prediction.
        self.assertNotIn("cod2", prior_v2.LEDGER_TYPE_MAP)


class TestArtifact(unittest.TestCase):
    """Invariants of the committed results/prior_v2.json."""

    @classmethod
    def setUpClass(cls):
        cls.art = prior_v2.load()

    def test_all_types_meet_min_n_and_valid_p(self):
        for t, s in self.art["types"].items():
            with self.subTest(type=t):
                self.assertGreaterEqual(s["n"], self.art["min_n"])
                self.assertTrue(0.0 < s["p_adopt"] < 1.0)
                self.assertAlmostEqual(
                    s["p_adopt"], prior_v2.jeffreys(s["n_adopted"], s["n"]), places=4)

    def test_lookup_consent_is_nle_high_p(self):
        tp = prior_v2.for_ledger_type("consent", self.art)
        self.assertEqual(tp["htv_type"], "NLE")
        self.assertGreater(tp["p_adopt"], 0.9)
        self.assertIsNotNone(tp["share_adopted"])

    def test_lookup_unknown_type_is_none(self):
        self.assertIsNone(prior_v2.for_ledger_type("cod2", self.art))
        self.assertIsNone(prior_v2.for_ledger_type("nonsense", self.art))


class TestBrierHook(unittest.TestCase):
    def test_brier_values(self):
        self.assertAlmostEqual(pf._brier({"p_adopt": 0.9}, "ADOPTED"), 0.01)
        self.assertAlmostEqual(pf._brier({"p_adopt": 0.9}, "REJECTED"), 0.81)

    def test_pre_v2_items_unscored(self):
        # The committed 2026-06-15 ledger has no p_adopt: grading must not change.
        self.assertIsNone(pf._brier({}, "ADOPTED"))
        self.assertIsNone(pf._brier({"p_adopt": None}, "ADOPTED"))

    def test_scorecard_aggregates_brier_only_when_present(self):
        graded = {"observed_result": "ADOPTED", "outcome_hit": True,
                  "graded_at": "2026-06-19"}
        ledger = {"items": [
            {"signal": "prior", "outcome": "ADOPTED", "contested": None,
             "graded": {**graded, "brier": 0.04}},
            {"signal": "prior", "outcome": "ADOPTED", "contested": None,
             "graded": dict(graded)},   # pre-v2 item: no brier field
        ]}
        sc = pf._scorecard(ledger)
        self.assertAlmostEqual(sc["by_rail"]["prior"]["brier"], 0.04)
        self.assertIsNone(sc["by_rail"]["committee"]["brier"])


if __name__ == "__main__":
    unittest.main()
