"""
Unit Tests: Compatibility Engine

Tests the full evaluation pipeline:
- High compatibility scenario
- Low compatibility scenario
- Rejected candidate (hard constraint failure)
- Deal breaker scenario
- Incomplete data handling
- Confidence calculation
"""

from matchmaking.config import MatchmakingConfig
from matchmaking.processing.compatibility_engine import CompatibilityEngine
from matchmaking.schemas import (
    CompatibilityLevel,
    EducationLevel,
    Gender,
    Location,
    MaritalStatus,
    MatchStatus,
    PartnerPreferences,
    UserProfile,
)


class TestFullEvaluation:
    def _make_engine(self):
        return CompatibilityEngine(MatchmakingConfig())

    def test_high_compatibility(self):
        engine = self._make_engine()
        user = UserProfile(user_id="u1", gender=Gender.FEMALE, age=30, religion="Islam")
        candidate = UserProfile(
            user_id="c1",
            gender=Gender.MALE,
            age=32,
            religion="Islam",
            sect="Sunni",
            marital_status=MaritalStatus.NEVER_MARRIED,
            education=EducationLevel.MASTERS,
            location=Location(city="Islamabad", country="Pakistan"),
            interests=["Travel", "Reading"],
            personality_traits=["Calm", "Analytical"],
        )
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            age_range={"min": 28, max: 38},
            religion=["Islam"],
            sect=["Sunni"],
            marital_status=[MaritalStatus.NEVER_MARRIED],
            education=[EducationLevel.MASTERS],
            location=["Islamabad"],
            interests=["Travel", "Reading"],
        )
        result = engine.evaluate(user, candidate, prefs)
        assert result.match_score >= 60
        assert result.hard_constraints_passed is True
        assert len(result.deal_breakers_violated) == 0

    def test_rejected_candidate(self):
        engine = self._make_engine()
        user = UserProfile(user_id="u1", gender=Gender.FEMALE)
        candidate = UserProfile(
            user_id="c1",
            gender=Gender.MALE,
            religion="Christianity",
        )
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            religion=["Islam"],
        )
        result = engine.evaluate(user, candidate, prefs)
        assert result.match_status == MatchStatus.REJECTED
        assert result.hard_constraints_passed is False
        assert result.is_match is False

    def test_deal_breaker_rejection(self):
        engine = self._make_engine()
        user = UserProfile(user_id="u1", gender=Gender.FEMALE)
        candidate = UserProfile(
            user_id="c1",
            gender=Gender.MALE,
            religion="Islam",
            smoking=True,
        )
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            religion=["Islam"],
            deal_breakers=["smoking"],
        )
        result = engine.evaluate(user, candidate, prefs)
        assert result.match_status == MatchStatus.REJECTED
        assert len(result.deal_breakers_violated) > 0

    def test_incomplete_data(self):
        engine = self._make_engine()
        user = UserProfile(user_id="u1")
        candidate = UserProfile(user_id="c1", gender=Gender.MALE)
        prefs = PartnerPreferences(gender=Gender.MALE)
        result = engine.evaluate(user, candidate, prefs)
        assert result.data_completeness < 100
        assert result.confidence_score < 100


class TestCompatibilityLevel:
    def test_very_high(self):
        engine = CompatibilityEngine(
            MatchmakingConfig(high_compatibility_threshold=85)
        )
        # This tests the level determination logic
        level = engine._determine_compatibility_level(90)
        assert level == CompatibilityLevel.VERY_HIGH

    def test_high(self):
        engine = CompatibilityEngine(MatchmakingConfig())
        level = engine._determine_compatibility_level(80)
        assert level == CompatibilityLevel.HIGH

    def test_medium(self):
        engine = CompatibilityEngine(MatchmakingConfig())
        level = engine._determine_compatibility_level(65)
        assert level == CompatibilityLevel.MEDIUM

    def test_low(self):
        engine = CompatibilityEngine(MatchmakingConfig())
        level = engine._determine_compatibility_level(45)
        assert level == CompatibilityLevel.LOW

    def test_none(self):
        engine = CompatibilityEngine(MatchmakingConfig())
        level = engine._determine_compatibility_level(0)
        assert level == CompatibilityLevel.NONE
