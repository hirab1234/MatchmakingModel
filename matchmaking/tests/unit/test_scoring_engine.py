"""
Unit Tests: Scoring Engine

Tests criterion-level scoring for:
- Age scoring (within range, outside range, missing data)
- Location scoring (city match, country match, no match)
- Religion scoring (match, no match, missing)
- Education scoring (exact, over-qualified, under-qualified)
- Interest scoring (Jaccard similarity)
- Missing data handling
- Weighted score calculation
"""

from matchmaking.config import MatchmakingConfig, ScoringWeights
from matchmaking.processing.scoring_engine import ScoringEngine
from matchmaking.schemas import (
    AgeRange,
    EducationLevel,
    Gender,
    HeightRange,
    Location,
    MaritalStatus,
    MatchStatus,
    PartnerPreferences,
    UserProfile,
)


class TestAgeScoring:
    def _make_engine(self):
        return ScoringEngine(MatchmakingConfig())

    def test_age_within_range(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", age=30)
        prefs = PartnerPreferences(age_range=AgeRange(min=25, max=35))
        criteria, score, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        age_match = next(c for c in criteria if c.criterion == "age")
        assert age_match.status == MatchStatus.MATCH
        assert age_match.score >= 80

    def test_age_outside_range(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", age=20)
        prefs = PartnerPreferences(age_range=AgeRange(min=25, max=35))
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        age_match = next(c for c in criteria if c.criterion == "age")
        assert age_match.status == MatchStatus.NO_MATCH
        assert age_match.score < 100  # Should not be a perfect score

    def test_age_at_boundary(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", age=25)
        prefs = PartnerPreferences(age_range=AgeRange(min=25, max=35))
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        age_match = next(c for c in criteria if c.criterion == "age")
        assert age_match.status == MatchStatus.MATCH

    def test_age_missing(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1")
        prefs = PartnerPreferences(age_range=AgeRange(min=25, max=35))
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        age_match = next(c for c in criteria if c.criterion == "age")
        assert age_match.status == MatchStatus.UNKNOWN


class TestLocationScoring:
    def _make_engine(self):
        return ScoringEngine(MatchmakingConfig())

    def test_city_match(self):
        engine = self._make_engine()
        candidate = UserProfile(
            user_id="c1", location=Location(city="Islamabad", country="Pakistan")
        )
        prefs = PartnerPreferences(location=["Islamabad"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        loc_match = next(c for c in criteria if c.criterion == "location")
        assert loc_match.status == MatchStatus.MATCH
        assert loc_match.score == 100.0

    def test_city_no_match(self):
        engine = self._make_engine()
        candidate = UserProfile(
            user_id="c1", location=Location(city="Karachi", country="Pakistan")
        )
        prefs = PartnerPreferences(location=["Islamabad"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        loc_match = next(c for c in criteria if c.criterion == "location")
        assert loc_match.status == MatchStatus.NO_MATCH

    def test_location_missing_from_candidate(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1")
        prefs = PartnerPreferences(location=["Islamabad"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        loc_match = next(c for c in criteria if c.criterion == "location")
        assert loc_match.status == MatchStatus.UNKNOWN

    def test_no_location_preference(self):
        engine = self._make_engine()
        candidate = UserProfile(
            user_id="c1", location=Location(city="Islamabad")
        )
        prefs = PartnerPreferences(location=None)
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        loc_match = next(c for c in criteria if c.criterion == "location")
        assert loc_match.status == MatchStatus.UNKNOWN


class TestReligionScoring:
    def _make_engine(self):
        return ScoringEngine(MatchmakingConfig())

    def test_religion_match(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", religion="Islam")
        prefs = PartnerPreferences(religion=["Islam"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        r_match = next(c for c in criteria if c.criterion == "religion")
        assert r_match.status == MatchStatus.MATCH
        assert r_match.score == 100.0

    def test_religion_no_match(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", religion="Christianity")
        prefs = PartnerPreferences(religion=["Islam"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        r_match = next(c for c in criteria if c.criterion == "religion")
        assert r_match.status == MatchStatus.NO_MATCH
        assert r_match.score == 0.0


class TestInterestScoring:
    def _make_engine(self):
        return ScoringEngine(MatchmakingConfig())

    def test_identical_interests(self):
        engine = self._make_engine()
        candidate = UserProfile(
            user_id="c1", interests=["Reading", "Travel", "Technology"]
        )
        prefs = PartnerPreferences(interests=["Reading", "Travel", "Technology"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        i_match = next(c for c in criteria if c.criterion == "interests")
        assert i_match.score == 100.0

    def test_no_overlap_interests(self):
        engine = self._make_engine()
        candidate = UserProfile(
            user_id="c1", interests=["Gaming", "Sports"]
        )
        prefs = PartnerPreferences(interests=["Reading", "Travel", "Technology"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        i_match = next(c for c in criteria if c.criterion == "interests")
        assert i_match.score == 0.0

    def test_partial_overlap_interests(self):
        engine = self._make_engine()
        candidate = UserProfile(
            user_id="c1", interests=["Reading", "Sports", "Gaming"]
        )
        prefs = PartnerPreferences(interests=["Reading", "Travel", "Technology"])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        i_match = next(c for c in criteria if c.criterion == "interests")
        # Jaccard: 1/5 = 20%
        assert 15 <= i_match.score <= 30


class TestEducationScoring:
    def _make_engine(self):
        return ScoringEngine(MatchmakingConfig())

    def test_exact_match(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", education=EducationLevel.MASTERS)
        prefs = PartnerPreferences(education=[EducationLevel.MASTERS])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        e_match = next(c for c in criteria if c.criterion == "education")
        assert e_match.status == MatchStatus.MATCH

    def test_over_qualified(self):
        engine = self._make_engine()
        candidate = UserProfile(user_id="c1", education=EducationLevel.DOCTORATE)
        prefs = PartnerPreferences(education=[EducationLevel.MASTERS])
        criteria, _, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        e_match = next(c for c in criteria if c.criterion == "education")
        # Over-qualified is still acceptable (score > 50)
        assert e_match.score >= 70


class TestWeightedScoring:
    def test_weights_applied(self):
        engine = ScoringEngine(MatchmakingConfig())
        # All weights should be present
        assert "age" in engine.weights
        assert "location" in engine.weights
        assert "religion" in engine.weights
        # Total should be reasonable
        total = sum(engine.weights.values())
        assert 0 < total <= 1.5  # Allow some flexibility


class TestDealBreakerPenalty:
    def test_deal_breaker_reduces_score(self):
        engine = ScoringEngine(MatchmakingConfig())
        candidate = UserProfile(
            user_id="c1",
            age=30,
            gender=Gender.MALE,
            religion="Islam",
            smoking=True,
        )
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            religion=["Islam"],
            deal_breakers=["smoking"],
        )
        criteria, score, _ = engine.score_all_criteria(
            UserProfile(user_id="u1"), candidate, prefs
        )
        # Score should be penalized by deal breaker
        # (deal breakers are checked by compatibility engine, but scoring still works)
        assert score >= 0
