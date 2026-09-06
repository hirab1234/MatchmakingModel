"""
Input Validator

Validates incoming data against the matchmaking schema.
Ensures all required fields are present and data is well-formed.
Provides structured validation errors without exposing internals.
"""

from __future__ import annotations

from typing import List, Tuple

from matchmaking.exceptions import InputValidationError
from matchmaking.schemas import (
    MatchmakingRequest,
    PartnerPreferences,
    UserProfile,
)
from matchmaking.config import get_config


class Validator:
    """Validates matchmaking input data."""

    @classmethod
    def validate_request(cls, request: MatchmakingRequest) -> List[str]:
        """Validate the full matchmaking request. Returns list of warnings."""
        warnings: List[str] = []

        # Validate user profile
        user_warnings = cls.validate_user_profile(request.user, "user")
        warnings.extend(user_warnings)

        # Validate partner preferences
        pref_warnings = cls.validate_preferences(request.partner_preferences)
        warnings.extend(pref_warnings)

        # Validate candidates
        if request.candidate is not None:
            cand_warnings = cls.validate_user_profile(
                request.candidate, "candidate"
            )
            warnings.extend(cand_warnings)

        if request.candidates is not None:
            for i, candidate in enumerate(request.candidates):
                cand_warnings = cls.validate_user_profile(
                    candidate, f"candidates[{i}]"
                )
                warnings.extend(cand_warnings)

            # Check max candidates
            config = get_config()
            if len(request.candidates) > config.max_candidates_per_request:
                raise InputValidationError(
                    message=f"Too many candidates: {len(request.candidates)} "
                    f"(max: {config.max_candidates_per_request})",
                    field="candidates",
                )

        return warnings

    @classmethod
    def validate_user_profile(
        cls, profile: UserProfile, prefix: str
    ) -> List[str]:
        """Validate a user profile. Returns list of warnings."""
        warnings: List[str] = []

        if not profile.user_id:
            raise InputValidationError(
                message=f"{prefix}.user_id is required",
                field=f"{prefix}.user_id",
            )

        # Validate age
        if profile.age is not None and profile.age < 18:
            raise InputValidationError(
                message=f"{prefix}.age must be >= 18",
                field=f"{prefix}.age",
            )

        # Validate age from DOB
        if profile.date_of_birth is not None and profile.age is not None:
            if profile.age < 18:
                raise InputValidationError(
                    message=f"{prefix} must be at least 18 years old",
                    field=f"{prefix}.date_of_birth",
                )

        # Warn about incomplete data
        if profile.age is None and profile.date_of_birth is None:
            warnings.append(f"{prefix}: age/date_of_birth not provided")

        if not profile.location:
            warnings.append(f"{prefix}: location not provided")

        if profile.religion is None:
            warnings.append(f"{prefix}: religion not provided")

        if not profile.interests:
            warnings.append(f"{prefix}: interests not provided")

        return warnings

    @classmethod
    def validate_preferences(cls, prefs: PartnerPreferences) -> List[str]:
        """Validate partner preferences. Returns list of warnings."""
        warnings: List[str] = []

        # Check if preferences are completely empty
        has_any = any([
            prefs.gender is not None,
            prefs.age_range is not None,
            prefs.height_range is not None,
            prefs.marital_status is not None,
            prefs.religion is not None,
            prefs.education is not None,
            prefs.profession is not None,
            prefs.location is not None,
            prefs.interests,
            prefs.deal_breakers,
        ])

        if not has_any:
            warnings.append("No partner preferences specified - will use neutral scoring")

        # Validate age range
        if prefs.age_range is not None:
            if prefs.age_range.min is not None and prefs.age_range.min < 18:
                raise InputValidationError(
                    message="age_range.min must be >= 18",
                    field="partner_preferences.age_range.min",
                )
            if prefs.age_range.max is not None and prefs.age_range.max > 120:
                raise InputValidationError(
                    message="age_range.max must be <= 120",
                    field="partner_preferences.age_range.max",
                )

        return warnings

    @classmethod
    def validate_gender_compatibility(
        cls, user: UserProfile, candidate: UserProfile, prefs: PartnerPreferences
    ) -> bool:
        """Quick gender compatibility check (hard constraint)."""
        if prefs.gender is not None and candidate.gender is not None:
            return candidate.gender == prefs.gender
        return True  # Unknown = don't reject
