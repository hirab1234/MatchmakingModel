"""
Unit Tests: Normalizer

Tests input normalization for:
- String trimming and casing
- Location normalization and alias mapping
- List deduplication
- User profile normalization
- Partner preferences normalization
- Data completeness calculation
"""

from matchmaking.processing.normalizer import Normalizer
from matchmaking.schemas import (
    AgeRange,
    EducationLevel,
    Gender,
    HeightRange,
    Location,
    MaritalStatus,
    PartnerPreferences,
    UserProfile,
)


class TestStringNormalization:
    def test_trim_whitespace(self):
        assert Normalizer.normalize_string("  hello  ") == "hello"

    def test_none_passthrough(self):
        assert Normalizer.normalize_string(None) is None

    def test_empty_string_returns_none(self):
        assert Normalizer.normalize_string("   ") is None

    def test_lower_normalization(self):
        assert Normalizer.normalize_lower("  HELLO  ") == "hello"

    def test_string_list_deduplication(self):
        result = Normalizer.normalize_string_list(["a", "B", "a", "c", "B"])
        assert result == ["B", "a", "c"]  # sorted

    def test_string_list_with_whitespace(self):
        result = Normalizer.normalize_string_list([" hello ", "world", " hello "])
        assert result == ["hello", "world"]


class TestLocationNormalization:
    def test_location_aliases(self):
        result = Normalizer.normalize_location_list(["islamabad", "RAWALPINDI"])
        assert "Islamabad" in result
        assert "Rawalpindi" in result

    def test_location_deduplication(self):
        result = Normalizer.normalize_location_list(
            ["islamabad", "Islamabad", "ISLAMABAD"]
        )
        assert len(result) == 1

    def test_location_sorting(self):
        result = Normalizer.normalize_location_list(["Lahore", "Islamabad", "Karachi"])
        assert result == ["Islamabad", "Karachi", "Lahore"]


class TestUserProfileNormalization:
    def test_normalize_full_profile(self):
        profile = UserProfile(
            user_id="test1",
            gender=Gender.MALE,
            age=30,
            religion="  Islam  ",
            interests=["  Reading  ", "travel", "READING"],
            location=Location(city="Islamabad", country="pakistan"),
        )
        normalized = Normalizer.normalize_user_profile(profile)
        assert normalized.religion == "Islam"
        assert len(normalized.interests) == 2  # Reading and travel deduplicated
        assert normalized.location.city == "Islamabad"

    def test_normalize_interests_deduplication(self):
        profile = UserProfile(
            user_id="test2",
            interests=["Travel", "travel", "TRAVEL", "Cooking"],
        )
        normalized = Normalizer.normalize_user_profile(profile)
        assert len(normalized.interests) == 2


class TestPartnerPreferencesNormalization:
    def test_normalize_preferences(self):
        prefs = PartnerPreferences(
            gender=Gender.MALE,
            religion=[" islam ", "ISLAM"],
            location=["islamabad", "ISLAMABAD"],
            interests=["  Reading  ", "reading"],
        )
        normalized = Normalizer.normalize_partner_preferences(prefs)
        assert len(normalized.religion) == 1
        assert len(normalized.location) == 1
        assert len(normalized.interests) == 1


class TestDataCompleteness:
    def test_complete_profile(self):
        profile = UserProfile(
            user_id="complete",
            gender=Gender.MALE,
            age=30,
            height_cm=175,
            marital_status=MaritalStatus.NEVER_MARRIED,
            religion="Islam",
            education=EducationLevel.MASTERS,
            profession="Engineer",
            location=Location(city="Islamabad"),
            interests=["Travel"],
        )
        completeness = Normalizer.compute_data_completeness(profile)
        assert completeness == 100.0

    def test_incomplete_profile(self):
        profile = UserProfile(user_id="incomplete")
        completeness = Normalizer.compute_data_completeness(profile)
        assert completeness < 50.0

    def test_partial_profile(self):
        profile = UserProfile(
            user_id="partial",
            gender=Gender.FEMALE,
            age=25,
            religion="Islam",
            education=EducationLevel.BACHELORS,
        )
        completeness = Normalizer.compute_data_completeness(profile)
        assert 30 < completeness < 70
