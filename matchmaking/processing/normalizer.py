"""
Input Normalizer

Normalizes all incoming data to consistent formats before matching:
- Whitespace trimming and casing normalization
- Location normalization
- Array deduplication
- Enum normalization
- Numeric range normalization
- Date normalization

This ensures "Islamabad", "islamabad", "ISLAMABAD" are treated consistently.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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


class Normalizer:
    """Normalizes input data for consistent processing."""

    # Common aliases for locations
    LOCATION_ALIASES: Dict[str, str] = {
        "rawalpindi": "Rawalpindi",
        "islamabad": "Islamabad",
        "karachi": "Karachi",
        "lahore": "Lahore",
        "faisalabad": "Faisalabad",
        "multan": "Multan",
        "peshawar": "Peshawar",
        "quetta": "Quetta",
    }

    @classmethod
    def normalize_string(cls, value: Optional[str]) -> Optional[str]:
        """Trim whitespace, normalize casing."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return cleaned

    @classmethod
    def normalize_lower(cls, value: Optional[str]) -> Optional[str]:
        """Normalize to lowercase, trimmed."""
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        return cleaned

    @classmethod
    def normalize_string_list(cls, values: List[str]) -> List[str]:
        """Normalize a list of strings: trim, deduplicate, sort."""
        normalized = []
        seen = set()
        for v in values:
            n = cls.normalize_string(v)
            if n is not None:
                key = n.lower()
                if key not in seen:
                    seen.add(key)
                    normalized.append(n)
        return sorted(normalized)

    @classmethod
    def normalize_location(cls, location: Location) -> Location:
        """Normalize location fields with alias mapping."""
        city = cls.normalize_string(location.city)
        if city is not None:
            key = city.lower()
            city = cls.LOCATION_ALIASES.get(key, city)
        country = cls.normalize_string(location.country)
        state = cls.normalize_string(location.state)
        return Location(city=city, country=country, state=state)

    @classmethod
    def normalize_location_list(cls, locations: List[str]) -> List[str]:
        """Normalize a list of location names, applying aliases."""
        normalized = []
        seen = set()
        for loc in locations:
            n = cls.normalize_string(loc)
            if n is not None:
                key = n.lower()
                # Apply alias mapping
                canonical = cls.LOCATION_ALIASES.get(key, n)
                canon_key = canonical.lower()
                if canon_key not in seen:
                    seen.add(canon_key)
                    normalized.append(canonical)
        return sorted(normalized)

    @classmethod
    def normalize_age_range(cls, age_range: Optional[AgeRange]) -> Optional[AgeRange]:
        """Normalize age range."""
        if age_range is None:
            return None
        return AgeRange(
            min=age_range.min,
            max=age_range.max,
        )

    @classmethod
    def normalize_height_range(
        cls, height_range: Optional[HeightRange]
    ) -> Optional[HeightRange]:
        """Normalize height range."""
        if height_range is None:
            return None
        return HeightRange(
            min_cm=height_range.min_cm,
            max_cm=height_range.max_cm,
        )

    @classmethod
    def normalize_user_profile(cls, profile: UserProfile) -> UserProfile:
        """Normalize all fields of a user profile."""
        data = profile.model_dump()

        # Normalize string fields
        for field_name in [
            "name",
            "mother_tongue",
            "religion",
            "sect",
            "education_field",
            "profession",
            "profession_category",
            "income_range",
            "diet",
            "about_me",
        ]:
            if data.get(field_name) is not None:
                data[field_name] = cls.normalize_string(data[field_name])

        # Normalize education
        if data.get("education") is not None:
            data["education"] = EducationLevel(data["education"].lower())

        # Normalize marital status
        if data.get("marital_status") is not None:
            data["marital_status"] = MaritalStatus(data["marital_status"].lower())

        # Normalize gender
        if data.get("gender") is not None:
            data["gender"] = Gender(data["gender"].lower())

        # Normalize lists
        data["interests"] = cls.normalize_string_list(data.get("interests") or [])
        data["hobbies"] = cls.normalize_string_list(data.get("hobbies") or [])
        data["personality_traits"] = cls.normalize_string_list(
            data.get("personality_traits") or []
        )

        # Normalize location
        if data.get("location") is not None:
            loc = data["location"]
            if isinstance(loc, dict):
                loc_model = Location(**loc)
            else:
                loc_model = loc
            data["location"] = cls.normalize_location(loc_model).model_dump()

        # Deduplicate family details dict values
        if data.get("family_details"):
            fd = data["family_details"]
            data["family_details"] = {
                k: cls.normalize_string(str(v)) if isinstance(v, str) else v
                for k, v in fd.items()
            }

        # Remove None values from extra fields to keep clean
        cleaned = {k: v for k, v in data.items() if v is not None}

        return UserProfile(**cleaned)

    @classmethod
    def normalize_partner_preferences(
        cls, prefs: PartnerPreferences
    ) -> PartnerPreferences:
        """Normalize all fields of partner preferences."""
        data = prefs.model_dump()

        # Normalize enum fields
        if data.get("gender") is not None:
            data["gender"] = Gender(data["gender"].lower())

        # Free-text list preferences: trim, deduplicate, sort.
        # Enum-valued lists are left alone - pydantic re-validates them below.
        for field_name in ["mother_tongue", "religion", "sect", "preferred_field",
                           "profession", "profession_category", "location",
                           "country", "diet"]:
            val = data.get(field_name)
            if val is not None and isinstance(val, list):
                data[field_name] = cls.normalize_string_list(
                    [v for v in val if isinstance(v, str)]
                ) or data[field_name]

        # Normalize interests/hobbies/personality
        data["interests"] = cls.normalize_string_list(data.get("interests") or [])
        data["hobbies"] = cls.normalize_string_list(data.get("hobbies") or [])
        data["personality_traits"] = cls.normalize_string_list(
            data.get("personality_traits") or []
        )

        # Normalize deal breakers
        data["deal_breakers"] = cls.normalize_string_list(data.get("deal_breakers") or [])

        # Normalize age/height ranges
        if data.get("age_range"):
            ar = data["age_range"]
            if isinstance(ar, dict):
                data["age_range"] = cls.normalize_age_range(AgeRange(**ar)).model_dump()
        if data.get("height_range"):
            hr = data["height_range"]
            if isinstance(hr, dict):
                data["height_range"] = cls.normalize_height_range(
                    HeightRange(**hr)
                ).model_dump()

        # Income may be a structured range or a free-text band
        if isinstance(data.get("income_range"), str):
            data["income_range"] = cls.normalize_string(data["income_range"])

        # Clean None values
        cleaned = {k: v for k, v in data.items() if v is not None}

        return PartnerPreferences(**cleaned)

    @classmethod
    def compute_data_completeness(cls, profile: UserProfile) -> float:
        """Calculate how complete a profile is (0-100)."""
        # The core fields that define a usable profile. The extra preference
        # fields from the product document are enrichment: they raise
        # confidence through the number of criteria actually evaluated
        # (see CompatibilityEngine._calculate_confidence) rather than here.
        important_fields = [
            "gender", "age", "height_cm", "marital_status", "religion",
            "education", "profession", "location", "interests",
        ]
        filled = 0
        total = len(important_fields)
        data = profile.model_dump()
        for field_name in important_fields:
            val = data.get(field_name)
            if val is not None:
                if isinstance(val, list) and len(val) == 0:
                    continue
                if isinstance(val, dict):
                    # For location, check if at least city is set
                    if field_name == "location" and not val.get("city"):
                        continue
                filled += 1
        return round((filled / total) * 100, 1) if total > 0 else 100.0
