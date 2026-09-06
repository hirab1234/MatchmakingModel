"""
Integration Tests: Matchmaking Pipeline

Tests the complete flow:
    Backend Input → MatchMakingAiModel → Processing → AiMatchMakingModel → Response

Scenarios tested:
- Good match scenario
- Bad match scenario (rejected)
- Multiple candidates ranking
- Edge cases (incomplete data, empty preferences)
- Error handling
"""

import pytest

from matchmaking.config import MatchmakingConfig
from matchmaking.processing.normalizer import Normalizer
from matchmaking.schemas import (
    AgeRange,
    CompatibilityLevel,
    EducationLevel,
    Gender,
    Location,
    MaritalStatus,
    MatchStatus,
    MatchmakingRequest,
    MatchmakingResponse,
    PartnerPreferences,
    UserProfile,
)
from matchmaking.services.matchmaking_service import MatchmakingService
from matchmaking.tests.fixtures.test_data import (
    make_ahmed_preferences,
    make_candidate_rejected,
    make_candidate_sara,
    make_candidate_zain,
    make_empty_preferences,
    make_fatima_preferences,
    make_incomplete_profile,
    make_strict_preferences,
    make_user_ahmed,
    make_user_fatima,
)


class TestServiceInitialization:
    def test_service_creation(self):
        config = MatchmakingConfig(ai_enabled=False)
        service = MatchmakingService(config)
        assert service.config.ai_enabled is False

    def test_service_default_config(self):
        config = MatchmakingConfig(ai_enabled=False)
        service = MatchmakingService(config)
        assert service.config is not None


class TestSingleCandidatePipeline:
    """Integration: single candidate evaluation end-to-end."""

    def _get_service(self):
        config = MatchmakingConfig(ai_enabled=False)
        return MatchmakingService(config)

    def test_good_match(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="integ_001",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidate=make_candidate_zain(),
        )
        response = service.process(request)
        assert response.success is True
        assert response.result is not None
        assert response.result.candidate_id == "candidate_zain"
        # Zain should match many of Fatima's preferences
        assert response.result.match_score > 40
        assert response.result.confidence_score > 0

    def test_rejected_candidate(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="integ_002",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidate=make_candidate_rejected(),
        )
        response = service.process(request)
        assert response.success is True
        assert response.result is not None
        assert response.result.match_status == MatchStatus.REJECTED
        assert response.result.is_match is False
        assert len(response.result.deal_breakers_violated) > 0

    def test_response_has_all_fields(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="integ_003",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidate=make_candidate_zain(),
        )
        response = service.process(request)
        assert response.success is True
        result = response.result
        assert result.match_score >= 0
        assert result.match_score <= 100
        assert result.compatibility_level is not None
        assert isinstance(result.matched_preferences, list)
        assert isinstance(result.partial_matches, list)
        assert isinstance(result.mismatched_preferences, list)
        assert isinstance(result.deal_breakers_violated, list)
        assert isinstance(result.match_reasons, list)
        assert isinstance(result.concerns, list)
        assert isinstance(result.recommendations, list)
        assert result.confidence_score >= 0
        assert result.confidence_score <= 100

    def test_model_version_in_response(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="integ_004",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidate=make_candidate_zain(),
        )
        response = service.process(request)
        assert response.model_version == "1.0.0"


class TestMultipleCandidatesPipeline:
    """Integration: multiple candidates evaluation and ranking."""

    def _get_service(self):
        config = MatchmakingConfig(ai_enabled=False)
        return MatchmakingService(config)

    def test_multiple_candidates_ranked(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="integ_multi_001",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidates=[
                make_candidate_zain(),
                make_candidate_sara(),
                make_candidate_rejected(),
            ],
        )
        response = service.process(request)
        assert response.success is True
        assert response.results is not None
        assert len(response.results) == 3

        # Results should be sorted by score descending
        scores = [r.match_score for r in response.results]
        assert scores == sorted(scores, reverse=True)

        # Zain should be first (best match for Fatima)
        assert response.results[0].candidate_id == "candidate_zain"

    def test_rejected_candidate_in_batch(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="integ_multi_002",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidates=[
                make_candidate_rejected(),
            ],
        )
        response = service.process(request)
        assert response.success is True
        assert len(response.results) == 1
        assert response.results[0].match_status == MatchStatus.REJECTED


class TestEdgeCases:
    """Integration: edge cases and error handling."""

    def _get_service(self):
        config = MatchmakingConfig(ai_enabled=False)
        return MatchmakingService(config)

    def test_empty_preferences(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="edge_001",
            user=make_user_fatima(),
            partner_preferences=make_empty_preferences(),
            candidate=make_candidate_zain(),
        )
        response = service.process(request)
        assert response.success is True
        assert response.result is not None

    def test_incomplete_candidate_data(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="edge_002",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidate=make_incomplete_profile(),
        )
        response = service.process(request)
        assert response.success is True
        assert response.result is not None
        # Confidence should be lower due to incomplete data
        assert response.result.confidence_score < 90

    def test_identical_profiles(self):
        service = self._get_service()
        user = make_user_fatima()
        request = MatchmakingRequest(
            request_id="edge_003",
            user=user,
            partner_preferences=PartnerPreferences(
                gender=Gender.MALE,
                age_range=AgeRange(min=25, max=35),
            ),
            candidate=UserProfile(
                user_id="clone",
                gender=Gender.MALE,
                age=30,
            ),
        )
        response = service.process(request)
        assert response.success is True

    def test_direct_service_call(self):
        """Test that the service can be called directly without HTTP."""
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="direct_001",
            user=make_user_ahmed(),
            partner_preferences=make_ahmed_preferences(),
            candidate=make_candidate_sara(),
        )
        response = service.process(request)
        assert isinstance(response, MatchmakingResponse)


class TestDeterminism:
    """Integration: verify deterministic behavior."""

    def _get_service(self):
        config = MatchmakingConfig(ai_enabled=False)
        return MatchmakingService(config)

    def test_same_input_same_output(self):
        service = self._get_service()
        request = MatchmakingRequest(
            request_id="det_001",
            user=make_user_fatima(),
            partner_preferences=make_fatima_preferences(),
            candidate=make_candidate_zain(),
        )
        response1 = service.process(request)
        response2 = service.process(request)
        assert response1.result.match_score == response2.result.match_score
        assert response1.result.is_match == response2.result.is_match
        assert response1.result.confidence_score == response2.result.confidence_score
