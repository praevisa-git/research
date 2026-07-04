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
import unittest.mock
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

    def test_second_and_third_reading_floor_objects_demote_any_record(self):
        # A first-reading report record is a DIFFERENT text than the Council
        # position (***II) or the conciliation joint text (***III).
        for item_type, word in (("cod2", "second"), ("cod3", "third")):
            with self.subTest(item_type=item_type):
                ok, why = s0.signal_rail_eligible(AGRI_REPORT, "AGRI",
                                                  "2024/0319(COD)",
                                                  item_type=item_type)
                self.assertFalse(ok)
                self.assertIn("stage mismatch", why)
                self.assertIn(word, why)

    def test_first_reading_item_type_unaffected(self):
        ok, _ = s0.signal_rail_eligible(AGRI_REPORT, "AGRI", "2024/0319(COD)",
                                        item_type="cod1")
        self.assertTrue(ok)


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


class TestH3ConsentPrior(unittest.TestCase):
    def test_consent_vector_loads_from_committed_artifact(self):
        from praevisa import prior_v2
        vec = prior_v2.consent_vector()
        self.assertIsNotNone(vec, "consent_per_group missing from prior_v2.json")
        for g in ("EPP", "S&D", "Renew", "ECR", "Greens", "Left", "PfE", "ESN", "NI"):
            self.assertIn(g, vec)
            self.assertTrue(0.0 < vec[g] < 1.0)   # Jeffreys: never 0, never 1
        # verified expectation: the centrist majority is near-consensus on consents
        for g in ("EPP", "S&D", "Renew"):
            self.assertGreater(vec[g], 0.9)

    def test_pre_h3_artifact_returns_none(self):
        from praevisa import prior_v2
        self.assertIsNone(prior_v2.consent_vector({"types": {}}))

    def test_prior_rail_outcome_follows_type_base_rate_when_it_says_fail(self):
        # Term-10 DEA objections: 0/12 adopted -> p_adopt 0.038. The prior-rail
        # outcome call must follow the type base rate, not the topic-blind
        # seat-math vector, so `outcome` and `p_adopt` never contradict.
        from praevisa import prior_v2
        tp = prior_v2.for_ledger_type("objection-dea")
        self.assertEqual(tp["htv_type"], "DEA")
        self.assertLess(tp["p_adopt"], 0.5)
        # untabulated Term-10 types stay unmapped-with-note rather than faked
        self.assertIsNone(prior_v2.for_ledger_type("imm"))
        self.assertIsNone(prior_v2.for_ledger_type("rso"))
        self.assertIsNone(prior_v2.for_ledger_type("objection-rps"))


# The two June Liberia manifest entries, frozen verbatim as a fixture (the June
# ledger itself is never regenerated). Both located the same DEVE opinion record.
JUNE_LIBERIA_MANIFEST = [
    dict(day="2026-06-17", a10="A10-0133/2026", type="consent", committee="INTA",
         rapporteur="Karin Karlsbro",
         title="EU-Liberia Voluntary Partnership Agreement (timber): termination",
         corpus=("DEVE", "Termination of the Voluntary Partnership", None),
         opinion_signal=True),
    dict(day="2026-06-17", a10="A10-0146/2026", type="resolution", committee="INTA",
         rapporteur="Karin Karlsbro",
         title="EU-Liberia Voluntary Partnership Agreement (timber): termination "
               "(resolution)",
         corpus=("DEVE", "Termination of the Voluntary Partnership", None),
         opinion_signal=True),
]


class TestH3NoVectorReuse(unittest.TestCase):
    def test_june_liberia_replay_both_items_prior_rail(self):
        # Replay the June configuration through the new rail assignment: the DEVE
        # record is an opinion on the M-procedure, so BOTH floor objects must land
        # on the prior rail (test only — no June artifact is touched).
        from praevisa import plenary_forward as pf
        rails = pf._assign_rails(JUNE_LIBERIA_MANIFEST, committee_index={})
        for rail in rails:
            with self.subTest(why=rail["why"]):
                self.assertIsNotNone(rail["rec"], "DEVE record not found in corpus")
                self.assertFalse(rail["eligible"])
                self.assertEqual(rail["why"], "opinion(DEVE)")

    def test_one_record_two_items_reference_match_keeps_exactly_one(self):
        from praevisa import plenary_forward as pf
        rec = dict(AGRI_REPORT)
        index = {"2024/0319(COD)": rec}
        manifest = [
            dict(day="d", a10="A10-1", type="cod1", committee="AGRI", rapporteur="r",
                 procedure="2024/0319(COD)", title="Farmers — the report"),
            dict(day="d", a10="A10-2", type="resolution", committee="AGRI",
                 rapporteur="r", procedure="2024/0319(COD)",
                 title="Farmers — accompanying resolution"),
        ]
        # both reference-match the record -> ambiguous -> neither may take it
        rails = pf._assign_rails(manifest, index)
        self.assertEqual([r["eligible"] for r in rails], [False, False])
        for r in rails:
            self.assertIn("vector reuse", r["why"])
        # only the first carries the matching reference (the accompanying
        # resolution reaches the same record via the corpus locator, referenceless)
        # -> the reference-matched item keeps the signal, the other demotes
        manifest[1]["procedure"] = None
        manifest[1]["corpus"] = ("AGRI", "Farmers", None)
        with unittest.mock.patch.object(pf, "_find_record", return_value=rec):
            rails = pf._assign_rails(manifest, index)
        self.assertTrue(rails[0]["eligible"])
        self.assertFalse(rails[1]["eligible"])
        self.assertIn("vector reuse", rails[1]["why"])
        self.assertIn("A10-1", rails[1]["why"])

    def test_single_item_single_record_unaffected(self):
        from praevisa import plenary_forward as pf
        index = {"2024/0319(COD)": dict(AGRI_REPORT)}
        manifest = [dict(day="d", a10="A10-1", type="cod1", committee="AGRI",
                         rapporteur="r", procedure="2024/0319(COD)", title="Farmers")]
        rails = pf._assign_rails(manifest, index)
        self.assertTrue(rails[0]["eligible"])
        self.assertEqual(rails[0]["why"], "report")


def _liberia_record_from_corpus():
    data = json.loads((REPO / "committee_corpus_DEVE.json").read_text())
    for r in data["records"]:
        if ("Liberia" in (r.get("title") or "")
                and "Voluntary Partnership" in (r.get("title") or "")):
            return r
    raise AssertionError("Liberia record missing from committed DEVE corpus")


class TestPolarityTripwire(unittest.TestCase):
    def test_liberia_deve_record_flags(self):
        from praevisa import corpus_health
        rec = _liberia_record_from_corpus()
        self.assertEqual(corpus_health._rapporteur_group(rec), "S&D")
        self.assertTrue(corpus_health.polarity_tripwire(rec))

    def test_rapporteur_group_carrying_the_vote_does_not_flag(self):
        from praevisa import corpus_health
        rec = dict(AGRI_REPORT, votes=[
            {"group": "PPE", "choice": "+"}, {"group": "PPE", "choice": "+"},
            {"group": "S&D", "choice": "-"},
        ])
        self.assertFalse(corpus_health.polarity_tripwire(rec))   # PPE carried it

    def test_non_adoption_vote_does_not_flag(self):
        from praevisa import corpus_health
        rec = dict(AGRI_REPORT, subject="Amendment 200",
                   title="Farmers something", rapporteur="Céline Imart (PPE)",
                   votes=[{"group": "PPE", "choice": "-"}])
        self.assertFalse(corpus_health.polarity_tripwire(rec))

    def test_unparseable_rapporteur_does_not_flag(self):
        from praevisa import corpus_health
        rec = dict(AGRI_REPORT, rapporteur="No Suffix Here",
                   votes=[{"group": "PPE", "choice": "-"}])
        self.assertFalse(corpus_health.polarity_tripwire(rec))

    def test_tripped_responsible_committee_record_demotes_in_rail_assignment(self):
        from praevisa import plenary_forward as pf
        rec = dict(AGRI_REPORT, rapporteur="Céline Imart (PPE)", votes=[
            {"group": "PPE", "choice": "-"}, {"group": "PPE", "choice": "-"},
            {"group": "S&D", "choice": "+"},
        ])
        index = {"2024/0319(COD)": rec}
        manifest = [dict(day="d", a10="A10-1", type="cod1", committee="AGRI",
                         rapporteur="r", procedure="2024/0319(COD)", title="Farmers")]
        rails = pf._assign_rails(manifest, index)
        self.assertFalse(rails[0]["eligible"])
        self.assertIn("polarity tripwire", rails[0]["why"])

    def test_flags_emitted_by_audit(self):
        from praevisa import corpus_health
        rec = _liberia_record_from_corpus()
        _, _, flags = corpus_health.audit({"DEVE": [rec]})
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["committee"], "DEVE")
        self.assertIn("Maij", flags[0]["rapporteur"])


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
