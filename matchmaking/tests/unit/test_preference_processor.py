"""
Unit Tests: Preference Processor

Tests preference classification and checking for:
- Hard constraint classification
- Soft preference classification
- Deal breaker classification
- Hard constraint checking
- Deal breaker checking
"""

from matchmaking.processing.preference_processor import PreferenceProcessor
from matchmaking.schemas import (
    EducationLevel,
    Gender,
    MaritalStatus,
    PartnerPreferences,
    UserProfile,
)


class TestClassification:
    def test_classify_preferences(self):
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            religion=["Islam"],
            sect=["Sunni"],
            marital_status=[MaritalStatus.NEVER_MARRIED],
            age_range={"min": 25, "max": 35},
            interests=["Travel", "Reading"],
            deal_breakers=["smoking"],
        )
        classification = PreferenceProcessor.classify_preferences(prefs)

        # Hard constraints: gender, religion, sect, marital_status = 4
        assert len(classification.hard_constraints) == 4
        # Soft preferences: age_range, interests = 2
        assert len(classification.soft_preferences) >= 2
        # Deal breakers: smoking = 1
        assert len(classification.deal_breakers) == 1

    def test_empty_preferences(self):
        prefs = PartnerPreferences()
        classification = PreferenceProcessor.classify_preferences(prefs)
        assert len(classification.hard_constraints) == 0
        assert len(classification.deal_breakers) == 0
        # Soft preferences with empty values should be filtered out

    def test_hard_constraint_fields(self):
        prefs = PartnerPreferences(
            gender=Gender.FEMALE,
            religion=["Islam"],
            education=[EducationLevel.MASTERS],  # soft preference
        )
        classification = PreferenceProcessor.classify_preferences(prefs)
        hard_names = [c.name for c in classification.hard_constraints]
        assert "gender" in hard_names
        assert "religion" in hard_names
        assert "education" not in hard_names  # This is soft


class TestHardConstraintCheck:
    def test_all_hard_constraints_pass(self):
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            religion=["Islam"],
        )
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(
            user_id="c1",
            gender=Gender.MALE,
            religion="Islam",
        )
        failed = PreferenceProcessor.check_hard_constraints(
            candidate, classification, UserProfile(user_id="u1")
        )
        assert len(failed) == 0, f"Expected 0 failed constraints but got: {failed}"

    def test_gender_fails(self):
        prefs = PartnerPreferences(gender=Gender.MALE)
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(user_id="c1", gender=Gender.FEMALE)
        failed = PreferenceProcessor.check_hard_constraints(
            candidate, classification, UserProfile(user_id="u1")
        )
        assert len(failed) == 1
        assert "gender" in failed[0]

    def test_religion_fails(self):
        prefs = PartnerPreferences(religion=["Islam"])
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(user_id="c1", religion="Christianity")
        failed = PreferenceProcessor.check_hard_constraints(
            candidate, classification, UserProfile(user_id="u1")
        )
        assert len(failed) == 1

    def test_missing_candidate_religion_fails(self):
        prefs = PartnerPreferences(religion=["Islam"])
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(user_id="c1")  # No religion
        failed = PreferenceProcessor.check_hard_constraints(
            candidate, classification, UserProfile(user_id="u1")
        )
        assert len(failed) == 1


class TestDealBreakerCheck:
    def test_smoking_deal_breaker(self):
        prefs = PartnerPreferences(deal_breakers=["smoking"])
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(user_id="c1", smoking=True)
        violated = PreferenceProcessor.check_deal_breakers(candidate, classification)
        assert "smoking" in violated

    def test_no_deal_breaker_violated(self):
        prefs = PartnerPreferences(deal_breakers=["smoking"])
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(user_id="c1", smoking=False)
        violated = PreferenceProcessor.check_deal_breakers(candidate, classification)
        assert len(violated) == 0

    def test_multiple_deal_breakers(self):
        prefs = PartnerPreferences(deal_breakers=["smoking", "drinking"])
        classification = PreferenceProcessor.classify_preferences(prefs)
        candidate = UserProfile(user_id="c1", smoking=True, drinking=True)
        violated = PreferenceProcessor.check_deal_breakers(candidate, classification)
        assert len(violated) == 2
