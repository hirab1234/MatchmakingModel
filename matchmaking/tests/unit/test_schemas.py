"""
Unit Tests: Schemas

Tests Pydantic schema validation:
- UserProfile validation
- PartnerPreferences validation
- MatchmakingRequest validation
- AgeRange validation
- HeightRange validation
- Response schema validation
"""

import pytest
from datetime import date

from matchmaking.schemas import (
    AgeRange,
    CandidateMatchResult,
    CompatibilityLevel,
    EducationLevel,
    Gender,
    HeightRange,
    Location,
    MaritalStatus,
    MatchmakingRequest,
    MatchmakingResponse,
    MatchStatus,
    PartnerPreferences,
    UserProfile,
)


class TestUserProfile:
    def test_valid_profile(self):
        profile = UserProfile(user_id="u1", gender=Gender.MALE, age=30)
        assert profile.user_id == "u1"
        assert profile.gender == Gender.MALE

    def test_empty_user_id(self):
        # user_id must be non-empty (min_length=1)
        with pytest.raises(Exception):  # Pydantic ValidationError
            UserProfile(user_id="")

    def test_age_from_dob(self):
        profile = UserProfile(
            user_id="u1",
            date_of_birth=date(1990, 1, 1),
        )
        # Age should be computed from DOB
        assert profile.age is not None
        assert profile.age >= 35  # At least 35 years old by 2026

    def test_extra_fields_allowed(self):
        profile = UserProfile(
            user_id="u1",
            custom_field="custom_value",
        )
        assert profile.custom_field == "custom_value"


class TestPartnerPreferences:
    def test_valid_preferences(self):
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            age_range=AgeRange(min=25, max=35),
        )
        assert prefs.gender == Gender.MALE

    def test_empty_preferences(self):
        prefs = PartnerPreferences()
        assert prefs.gender is None
        assert prefs.deal_breakers == []

    def test_age_range_validation(self):
        with pytest.raises(Exception):
            AgeRange(min=25, max=20)  # min > max

    def test_height_range_validation(self):
        with pytest.raises(Exception):
            HeightRange(min_cm=180, max_cm=160)  # min > max


class TestMatchmakingRequest:
    def test_single_candidate(self):
        request = MatchmakingRequest(
            user=UserProfile(user_id="u1"),
            partner_preferences=PartnerPreferences(),
            candidate=UserProfile(user_id="c1"),
        )
        assert request.candidate is not None
        assert request.candidates is None

    def test_multiple_candidates(self):
        request = MatchmakingRequest(
            user=UserProfile(user_id="u1"),
            partner_preferences=PartnerPreferences(),
            candidates=[
                UserProfile(user_id="c1"),
                UserProfile(user_id="c2"),
            ],
        )
        assert request.candidates is not None
        assert len(request.candidates) == 2

    def test_no_candidate_fails(self):
        with pytest.raises(Exception):
            MatchmakingRequest(
                user=UserProfile(user_id="u1"),
                partner_preferences=PartnerPreferences(),
                # Neither candidate nor candidates provided
            )

    def test_auto_generated_request_id(self):
        request = MatchmakingRequest(
            user=UserProfile(user_id="u1"),
            partner_preferences=PartnerPreferences(),
            candidate=UserProfile(user_id="c1"),
        )
        assert request.request_id != ""
        assert len(request.request_id) > 0


class TestMatchmakingResponse:
    def test_success_response(self):
        response = MatchmakingResponse(
            success=True,
            model_version="1.0.0",
            request_id="req_001",
            result=CandidateMatchResult(
                candidate_id="c1",
                is_match=True,
                match_score=85,
                compatibility_level=CompatibilityLevel.HIGH,
                match_status=MatchStatus.MATCH,
                match_reasons=["Religion matches"],
                confidence_score=90,
            ),
        )
        assert response.success is True
        assert response.result.match_score == 85

    def test_error_response(self):
        response = MatchmakingResponse(
            success=False,
            model_version="1.0.0",
            error={"code": "VALIDATION_ERROR", "message": "Invalid input"},
        )
        assert response.success is False
        assert response.result is None
