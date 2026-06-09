"""Smoke/regression tests for the EP flip bridge (committee signal → flip layer).

Pins the sellable artifact's behaviour on two real, known files so a refactor of the
signal or the pivot logic can't silently break the product output. Reads the committed
committee corpora (real data), so these double as an end-to-end check of the bridge.
"""

import unittest

from praevisa import ep_flip


class TestEPFlipBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committee = ep_flip.s0.load_committee_cod()
        cls.prior = ep_flip._baseline_A()

    def _f(self, proc):
        return ep_flip.forecast_for(proc, self.committee, self.prior)

    def test_rejected_file_predicts_rejected_with_named_pivot(self):
        # 2025/0429: committee AND plenary both rejected; Renew is the swing bloc.
        f = self._f("2025/0429(COD)")
        self.assertIsNotNone(f, "no committee signal for the rejected test file")
        self.assertEqual(f["outcome"], "REJECTED")
        self.assertIsNotNone(f["pivot"])
        self.assertEqual(f["pivot"].actors, ["Renew"])

    def test_locked_coalition_file_is_not_one_group_movable(self):
        # 2025/0825: EPP+S&D+Renew locked for → adopted, unflippable by one group.
        f = self._f("2025/0825(COD)")
        self.assertIsNotNone(f)
        self.assertEqual(f["outcome"], "ADOPTED")
        self.assertFalse(f["pivot"].realistic)

    def test_unknown_procedure_returns_none(self):
        self.assertIsNone(self._f("1999/9999(COD)"))

    def test_undefined_group_falls_back_to_prior_not_zero(self):
        # the model must not fabricate 0% for a group absent in committee
        com = {"EPP": 0.9}                      # only one group defined
        pred = ep_flip.predict_plenary_per_group(com, {g: 0.5 for g in ep_flip.GROUPS})
        self.assertEqual(pred["EPP"], 0.9)       # identity for the defined group
        self.assertEqual(pred["S&D"], 0.5)       # prior for the absent group


if __name__ == "__main__":
    unittest.main()
