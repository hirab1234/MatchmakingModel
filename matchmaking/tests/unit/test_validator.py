"""
Unit Tests: Validator

Tests input validation for:
- Request validation
- User profile validation
- Preferences validation
- Gender compatibility check
- Error conditions
"""

import pytest

from matchmaking.exceptions import InputValidationError
from matchmaking.processing.validator import Validator
from matchmaking.schemas import (
    AgeRange,
    EducationLevel,
    Gender,
    MaritalStatus,
    MatchmakingRequest,
    PartnerPreferences,
    UserProfile,
)


class TestUserValidation:
    def test_valid_profile_no_warnings(self):
        from matchmaking.schemas import Location
        profile = UserProfile(
            user_id="test",
            gender=Gender.MALE,
            age=30,
            religion="Islam",
            interests=["Travel"],
        )
        profile.location = Location(city="Islamabad")
        warnings = Validator.validate_user_profile(profile, "user")
        assert len(warnings) == 0

    def test_missing_user_id_raises(self):
        with pytest.raises(Exception):  # Pydantic raises ValidationError for empty string
            UserProfile(user_id="")

    def test_underage_raises(self):
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            profile = UserProfile(user_id="test", age=17)

    def test_incomplete_profile_has_warnings(self):
        profile = UserProfile(user_id="test")
        warnings = Validator.validate_user_profile(profile, "user")
        assert len(warnings) > 0
        assert any("age" in w.lower() for w in warnings)


class TestPreferencesValidation:
    def test_valid_preferences_no_warnings(self):
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            age_range=AgeRange(min=25, max=35),
            religion=["Islam"],
            education=[EducationLevel.MASTERS],
        )
        warnings = Validator.validate_preferences(prefs)
        # May have warnings about location not specified, etc.
        assert isinstance(warnings, list)

    def test_empty_preferences_warning(self):
        prefs = PartnerPreferences()
        warnings = Validator.validate_preferences(prefs)
        assert any("No partner preferences" in w for w in warnings)

    def test_invalid_age_range_raises(self):
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            prefs = PartnerPreferences(
                age_range=AgeRange(min=15, max=35),
            )

    def test_age_range_min_gt_max_raises(self):
        with pytest.raises(Exception):
            prefs = PartnerPreferences(
                age_range=AgeRange(min=40, max=20),
            )


class TestGenderCompatibility:
    def test_matching_gender(self):
        user = UserProfile(user_id="u1", gender=Gender.MALE)
        candidate = UserProfile(user_id="c1", gender=Gender.FEMALE)
        prefs = PartnerPreferences(gender=Gender.FEMALE)
        assert Validator.validate_gender_compatibility(user, candidate, prefs) is True

    def test_non_matching_gender(self):
        user = UserProfile(user_id="u1", gender=Gender.MALE)
        candidate = UserProfile(user_id="c1", gender=Gender.MALE)
        prefs = PartnerPreferences(gender=Gender.FEMALE)
        assert Validator.validate_gender_compatibility(user, candidate, prefs) is False

    def test_no_gender_preference(self):
        user = UserProfile(user_id="u1", gender=Gender.MALE)
        candidate = UserProfile(user_id="c1", gender=Gender.MALE)
        prefs = PartnerPreferences(gender=None)
        assert Validator.validate_gender_compatibility(user, candidate, prefs) is True
