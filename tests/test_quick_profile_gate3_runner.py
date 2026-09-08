import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/run_quick_profile_gate3_consented_human_review.py"
SPEC = importlib.util.spec_from_file_location("qp_gate3_runner", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MOD)


def valid_consent(pid="P001"):
    return {
        "status": "COLLECTED", "anonymousParticipantId": pid, "adultConfirmed": True,
        "photoUseConsentInternalDraftReviewOnly": True, "heightWeightUseConsent": True,
        "characterLikenessConsentInternalOnly": True, "characterGenerationAndInternalReviewConsent": True,
        "understandsNotGate8Evidence": True, "understandsNotProductQualityApproval": True,
        "retentionOrDeletionChoice": "DELETE_AFTER_REVIEW", "deletionAfterReviewIfChosen": True,
        "retentionUnderstood": True, "deletionUnderstood": True, "accessControlAcknowledged": True,
        "signatureOrEquivalent": True, "countsAsGate8ParticipantEvidence": "DENY",
        "nameContactSeparatedFromPipeline": True,
    }


class RunnerPolicyTests(unittest.TestCase):
    def test_valid_consent_passes(self):
        self.assertEqual(MOD.consent_ok(valid_consent(), "P001"), [])

    def test_missing_adult_confirmation_abstains(self):
        consent = valid_consent(); consent["adultConfirmed"] = False
        self.assertIn("CONSENT_FALSE_adultConfirmed", MOD.consent_ok(consent, "P001"))

    def test_missing_signature_abstains(self):
        consent = valid_consent(); consent["signatureOrEquivalent"] = False
        self.assertIn("CONSENT_FALSE_signatureOrEquivalent", MOD.consent_ok(consent, "P001"))

    def test_gate8_evidence_must_be_denied(self):
        consent = valid_consent(); consent["countsAsGate8ParticipantEvidence"] = "ALLOW"
        self.assertIn("GATE8_EVIDENCE_DENY_MISSING", MOD.consent_ok(consent, "P001"))

    def test_filter_flag_abstains(self):
        entry = {"eligibilityFlags": ["AR_OR_BEAUTY_FILTER_SUSPECTED"], "filterBeautyCorrection": "DISCOURAGED_SOFT_WARN"}
        self.assertEqual(MOD.operator_filter_reasons(entry), ["OPERATOR_FILTER_OR_BEAUTY_FLAG"])

    def test_filter_free_passes(self):
        entry = {"eligibilityFlags": ["FILTER_FREE_REPLACEMENT"], "filterBeautyCorrection": "FILTER_FREE"}
        self.assertEqual(MOD.operator_filter_reasons(entry), [])

    def test_clean_operator_entry_passes(self):
        entry = {"eligibilityFlags": ["CLEAN_FRONTAL_CANDIDATE"], "filterBeautyCorrection": "NONE_OBSERVED"}
        self.assertEqual(MOD.operator_filter_reasons(entry), [])

    def test_blind_assignment_is_deterministic(self):
        self.assertEqual(MOD.blind_assignment("P001"), MOD.blind_assignment("P001"))
        self.assertEqual(set(MOD.blind_assignment("P001").values()), {"NATURAL", "POLISHED"})

    def test_review_template_never_auto_passes(self):
        template = MOD.human_review_template("P001", MOD.blind_assignment("P001"))
        self.assertEqual(template["automaticPass"], "DENY")
        self.assertEqual(template["countsAsGate8ParticipantEvidence"], "DENY")
        self.assertFalse(template["selfEvaluation"]["completed"])

    def test_expected_hashes_are_full_length(self):
        self.assertTrue(all(len(value) == 64 for value in MOD.EXPECTED.values()))

    def test_runner_participant_slots_are_exact(self):
        self.assertEqual(MOD.PARTICIPANTS, ("P001", "P002", "P003"))

    def test_schema_is_versioned(self):
        self.assertTrue(MOD.RUNNER_SCHEMA.endswith("_V1"))


if __name__ == "__main__":
    unittest.main()
