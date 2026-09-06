"""
Test Fixtures

Shared test data for matchmaking tests.
Provides realistic sample data for various matchmaking scenarios.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Any

from matchmaking.schemas import (
    AgeRange,
    EducationLevel,
    Gender,
    HeightRange,
    Location,
    MaritalStatus,
    MatchmakingRequest,
    PartnerPreferences,
    UserProfile,
)


# ---------------------------------------------------------------------------
# User Profiles
# ---------------------------------------------------------------------------

def make_user_ahmed() -> UserProfile:
    """Ahmed - typical male user profile."""
    return UserProfile(
        user_id="user_ahmed",
        gender=Gender.MALE,
        date_of_birth=date(1992, 5, 15),
        age=34,
        height_cm=175,
        marital_status=MaritalStatus.NEVER_MARRIED,
        mother_tongue="Urdu",
        religion="Islam",
        sect="Sunni",
        education=EducationLevel.MASTERS,
        profession="Software Engineer",
        profession_category="Technology",
        location=Location(city="Islamabad", country="Pakistan"),
        interests=["Technology", "Travel", "Reading", "Cooking", "Photography"],
        hobbies=["Hiking", "Chess", "Photography"],
        personality_traits=["Introverted", "Analytical", "Calm"],
        lifestyle={"exercise": "regular", "diet": "halal", "social": "moderate"},
        smoking=False,
        drinking=False,
        diet="Halal",
        about_me="I enjoy technology, travel, and good conversations.",
    )


def make_user_fatima() -> UserProfile:
    """Fatima - typical female user profile."""
    return UserProfile(
        user_id="user_fatima",
        gender=Gender.FEMALE,
        date_of_birth=date(1994, 8, 20),
        age=31,
        height_cm=162,
        marital_status=MaritalStatus.NEVER_MARRIED,
        mother_tongue="Urdu",
        religion="Islam",
        sect="Sunni",
        education=EducationLevel.MASTERS,
        profession="Doctor",
        profession_category="Healthcare",
        location=Location(city="Islamabad", country="Pakistan"),
        interests=["Reading", "Cooking", "Travel", "Art", "Music"],
        hobbies=["Painting", "Cooking", "Yoga"],
        personality_traits=["Extroverted", "Creative", "Empathetic"],
        lifestyle={"exercise": "regular", "diet": "halal", "social": "active"},
        smoking=False,
        drinking=False,
        diet="Halal",
    )


def make_candidate_zain() -> UserProfile:
    """Zain - good match for Fatima's preferences."""
    return UserProfile(
        user_id="candidate_zain",
        gender=Gender.MALE,
        date_of_birth=date(1990, 3, 10),
        age=36,
        height_cm=178,
        marital_status=MaritalStatus.NEVER_MARRIED,
        mother_tongue="Urdu",
        religion="Islam",
        sect="Sunni",
        education=EducationLevel.DOCTORATE,
        profession="Professor",
        profession_category="Education",
        location=Location(city="Islamabad", country="Pakistan"),
        interests=["Reading", "Travel", "Technology", "Philosophy"],
        hobbies=["Reading", "Hiking", "Photography"],
        personality_traits=["Analytical", "Calm", "Patient"],
        lifestyle={"exercise": "regular", "diet": "halal", "social": "moderate"},
        smoking=False,
        drinking=False,
        diet="Halal",
    )


def make_candidate_sara() -> UserProfile:
    """Sara - partial match for Ahmed's preferences."""
    return UserProfile(
        user_id="candidate_sara",
        gender=Gender.FEMALE,
        date_of_birth=date(1995, 12, 5),
        age=30,
        height_cm=165,
        marital_status=MaritalStatus.NEVER_MARRIED,
        mother_tongue="Punjabi",
        religion="Islam",
        sect="Sunni",
        education=EducationLevel.BACHELORS,
        profession="Marketing Manager",
        profession_category="Business",
        location=Location(city="Lahore", country="Pakistan"),
        interests=["Music", "Dance", "Fashion", "Cooking"],
        hobbies=["Dancing", "Shopping", "Cooking"],
        personality_traits=["Extroverted", "Creative", "Spontaneous"],
        lifestyle={"exercise": "sometimes", "diet": "halal", "social": "very_active"},
        smoking=False,
        drinking=False,
    )


def make_candidate_rejected() -> UserProfile:
    """Candidate that violates hard constraints."""
    return UserProfile(
        user_id="candidate_rejected",
        gender=Gender.MALE,
        date_of_birth=date(1998, 1, 1),
        age=28,
        height_cm=170,
        marital_status=MaritalStatus.DIVORCED,
        mother_tongue="English",
        religion="Christian",
        education=EducationLevel.BACHELORS,
        profession="Artist",
        location=Location(city="Karachi", country="Pakistan"),
        interests=["Art", "Music"],
        personality_traits=["Creative"],
        lifestyle={},
        smoking=True,
        drinking=True,
    )


# ---------------------------------------------------------------------------
# Partner Preferences
# ---------------------------------------------------------------------------

def make_fatima_preferences() -> PartnerPreferences:
    """Fatima's partner preferences."""
    return PartnerPreferences(
        gender=Gender.MALE,
        age_range=AgeRange(min=28, max=40),
        height_range=HeightRange(min_cm=165, max_cm=190),
        marital_status=[MaritalStatus.NEVER_MARRIED],
        religion=["Islam"],
        sect=["Sunni"],
        education=[EducationLevel.MASTERS, EducationLevel.DOCTORATE],
        profession=["Software Engineer", "Doctor", "Professor", "Engineer"],
        location=["Islamabad", "Rawalpindi"],
        country=["Pakistan"],
        interests=["Reading", "Travel", "Technology"],
        personality_traits=["Analytical", "Patient", "Calm"],
        lifestyle={"exercise": "regular", "diet": "halal"},
        smoking=False,
        drinking=False,
        deal_breakers=["smoking"],
    )


def make_ahmed_preferences() -> PartnerPreferences:
    """Ahmed's partner preferences."""
    return PartnerPreferences(
        gender=Gender.FEMALE,
        age_range=AgeRange(min=25, max=33),
        height_range=HeightRange(min_cm=155, max_cm=175),
        marital_status=[MaritalStatus.NEVER_MARRIED],
        religion=["Islam"],
        education=[EducationLevel.BACHELORS, EducationLevel.MASTERS],
        location=["Islamabad", "Rawalpindi"],
        interests=["Technology", "Travel", "Reading"],
        smoking=False,
        drinking=False,
    )


# ---------------------------------------------------------------------------
# Request Builders
# ---------------------------------------------------------------------------

def make_single_match_request(
    user=None,
    candidate=None,
    prefs=None,
) -> MatchmakingRequest:
    """Build a single-candidate matchmaking request."""
    return MatchmakingRequest(
        request_id="test_request_001",
        user=user or make_user_fatima(),
        partner_preferences=prefs or make_fatima_preferences(),
        candidate=candidate or make_candidate_zain(),
    )


def make_multi_match_request(
    user=None,
    candidates=None,
    prefs=None,
) -> MatchmakingRequest:
    """Build a multi-candidate matchmaking request."""
    return MatchmakingRequest(
        request_id="test_request_002",
        user=user or make_user_fatima(),
        partner_preferences=prefs or make_fatima_preferences(),
        candidates=candidates or [
            make_candidate_zain(),
            make_candidate_sara(),
            make_candidate_rejected(),
        ],
    )


# ---------------------------------------------------------------------------
# Edge Case Profiles
# ---------------------------------------------------------------------------

def make_incomplete_profile() -> UserProfile:
    """Profile with minimal data."""
    return UserProfile(
        user_id="user_incomplete",
        gender=Gender.MALE,
        age=30,
    )


def make_empty_preferences() -> PartnerPreferences:
    """Preferences with no fields set."""
    return PartnerPreferences()


def make_strict_preferences() -> PartnerPreferences:
    """Very strict preferences with deal breakers."""
    return PartnerPreferences(
        gender=Gender.MALE,
        age_range=AgeRange(min=28, max=30),
        height_range=HeightRange(min_cm=175, max_cm=178),
        religion=["Islam"],
        sect=["Sunni"],
        education=[EducationLevel.DOCTORATE],
        profession=["Software Engineer"],
        location=["Islamabad"],
        country=["Pakistan"],
        interests=["Technology", "AI", "Machine Learning"],
        personality_traits=["Introverted", "Analytical"],
        smoking=False,
        drinking=False,
        deal_breakers=["smoking", "drinking", "divorced"],
    )
