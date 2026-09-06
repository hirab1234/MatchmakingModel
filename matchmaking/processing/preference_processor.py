"""
Preference Processor

Analyzes and classifies partner preferences into:
- Hard constraints (failure = rejection or major penalty)
- Soft preferences (failure = score reduction)
- Deal breakers (failure = immediate rejection)
- Neutral/optional preferences

This classification is driven by the partner preferences
sent from the backend — nothing is hardcoded here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from matchmaking.schemas import (
    MatchmakingRequest,
    PartnerPreferences,
    UserProfile,
)


@dataclass
class ClassifiedPreference:
    """A single preference with its classification."""

    name: str
    category: str  # "hard_constraint", "soft_preference", "deal_breaker"
    weight: float
    value: Any
    is_required: bool = False
    description: str = ""


@dataclass
class PreferenceClassification:
    """Result of classifying all preferences."""

    hard_constraints: List[ClassifiedPreference] = field(default_factory=list)
    soft_preferences: List[ClassifiedPreference] = field(default_factory=list)
    deal_breakers: List[ClassifiedPreference] = field(default_factory=list)
    all_preferences: List[ClassifiedPreference] = field(default_factory=list)


class PreferenceProcessor:
    """Classifies and processes partner preferences."""

    # These are treated as hard constraints when present in preferences
    # because they represent fundamental compatibility requirements
    # as typically used in matrimonial matchmaking
    HARDCONSTRAINT_FIELDS: Set[str] = {
        "gender",
        "religion",
        "sect",
        "marital_status",
    }

    # These are soft preferences that affect scoring but don't reject
    SOFT_PREFERENCE_FIELDS: Set[str] = {
        "age_range",
        "height_range",
        "location",
        "country",
        "mother_tongue",
        "religious_practice",
        "education",
        "min_education",
        "preferred_field",
        "profession",
        "profession_category",
        "employment_status",
        "income_range",
        "family_structure",
        "living_arrangement",
        "family_involvement",
        "smoking",
        "drinking",
        "diet",
        "exercise",
        "social_lifestyle",
        "lifestyle",
        "interests",
        "hobbies",
        "personality_traits",
        "marriage_timeline",
        "children_preference",
        "relocation",
        "career_expectation",
    }

    @classmethod
    def classify_preferences(
        cls,
        prefs: PartnerPreferences,
        weights: Optional[Dict[str, float]] = None,
    ) -> PreferenceClassification:
        """Classify all preferences into hard/soft/deal-breaker categories.

        Args:
            prefs: Partner preferences from the backend.
            weights: Optional scoring weights override.

        Returns:
            Classification of all preferences.
        """
        classification = PreferenceClassification()
        prefs_dict = prefs.model_dump(exclude_none=True)

        # Process deal breakers first (highest priority)
        for db in prefs.deal_breakers:
            pref = ClassifiedPreference(
                name=f"deal_breaker_{db}",
                category="deal_breaker",
                weight=1.0,
                value=db,
                is_required=True,
                description=f"Deal breaker: {db}",
            )
            classification.deal_breakers.append(pref)

        # Process hard constraints
        for field_name in cls.HARDCONSTRAINT_FIELDS:
            value = prefs_dict.get(field_name)
            if value is not None:
                pref = ClassifiedPreference(
                    name=field_name,
                    category="hard_constraint",
                    weight=1.0,
                    value=value,
                    is_required=True,
                    description=f"Required: {field_name} = {value}",
                )
                classification.hard_constraints.append(pref)

        # Process soft preferences
        for field_name in cls.SOFT_PREFERENCE_FIELDS:
            value = prefs_dict.get(field_name)
            if value is not None and value != [] and value != {} and value != "":
                weight = 0.5  # Default weight
                if weights and field_name in weights:
                    weight = weights[field_name]

                pref = ClassifiedPreference(
                    name=field_name,
                    category="soft_preference",
                    weight=weight,
                    value=value,
                    is_required=False,
                    description=f"Preferred: {field_name} = {value}",
                )
                classification.soft_preferences.append(pref)

        # Also process hard_constraints dict from preferences
        for key, value in prefs.hard_constraints.items():
            pref = ClassifiedPreference(
                name=key,
                category="hard_constraint",
                weight=1.0,
                value=value,
                is_required=True,
                description=f"Hard constraint: {key} = {value}",
            )
            classification.hard_constraints.append(pref)

        # Also process soft_preferences dict from preferences
        for key, value in prefs.soft_preferences.items():
            pref = ClassifiedPreference(
                name=key,
                category="soft_preference",
                weight=0.5,
                value=value,
                is_required=False,
                description=f"Soft preference: {key} = {value}",
            )
            classification.soft_preferences.append(pref)

        # Aggregate
        classification.all_preferences = (
            classification.deal_breakers
            + classification.hard_constraints
            + classification.soft_preferences
        )

        return classification

    @classmethod
    def check_hard_constraints(
        cls,
        candidate: UserProfile,
        classification: PreferenceClassification,
        user: UserProfile,
    ) -> List[str]:
        """Check if candidate satisfies all hard constraints.

        Returns list of failed hard constraints (empty = all passed).
        """
        failed: List[str] = []

        for constraint in classification.hard_constraints:
            if not cls._check_single_constraint(candidate, constraint, user):
                failed.append(
                    f"{constraint.name}: expected "
                    f"{cls._render(constraint.value)}, "
                    f"got {cls._render(getattr(candidate, constraint.name, None))}"
                )

        return failed

    @staticmethod
    def _render(value: Any) -> str:
        """Render enums and lists of enums as plain readable values."""
        if value is None:
            return "not provided"
        if isinstance(value, (list, tuple, set)):
            rendered = [PreferenceProcessor._render(v) for v in value]
            return ", ".join(rendered) if rendered else "not provided"
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @classmethod
    def check_deal_breakers(
        cls,
        candidate: UserProfile,
        classification: PreferenceClassification,
    ) -> List[str]:
        """Check if candidate triggers any deal breakers.

        Returns list of violated deal breakers.
        """
        violated: List[str] = []

        for db in classification.deal_breakers:
            if cls._check_deal_breaker(candidate, db):
                violated.append(db.value)

        return violated

    @classmethod
    def _check_single_constraint(
        cls,
        candidate: UserProfile,
        constraint: ClassifiedPreference,
        user: UserProfile,
    ) -> bool:
        """Check a single hard constraint against the candidate."""
        field_name = constraint.name
        expected = constraint.value

        def _to_str(val):
            """Convert an enum or string to a lowercase string for comparison."""
            if hasattr(val, "value"):
                return str(val.value).lower()
            return str(val).lower()

        if field_name == "gender":
            if candidate.gender is None:
                return False  # Unknown gender with constraint = fail
            if isinstance(expected, list):
                return any(candidate.gender.value == _to_str(e) for e in expected)
            return candidate.gender.value == _to_str(expected)

        elif field_name == "religion":
            if candidate.religion is None:
                return False
            if isinstance(expected, list):
                return any(candidate.religion.lower() == _to_str(e) for e in expected)
            return candidate.religion.lower() == _to_str(expected)

        elif field_name == "sect":
            if candidate.sect is None:
                return False
            if isinstance(expected, list):
                return any(candidate.sect.lower() == _to_str(e) for e in expected)
            return candidate.sect.lower() == _to_str(expected)

        elif field_name == "marital_status":
            if candidate.marital_status is None:
                return False
            if isinstance(expected, list):
                return any(candidate.marital_status.value == _to_str(e) for e in expected)
            return candidate.marital_status.value == _to_str(expected)

        return True  # Unknown constraint field = pass

    @classmethod
    def _check_deal_breaker(
        cls,
        candidate: UserProfile,
        deal_breaker: ClassifiedPreference,
    ) -> bool:
        """Check if a deal breaker is triggered."""
        db_value = deal_breaker.value.lower()

        # Check against known profile attributes
        if db_value == "smoking" and candidate.smoking is True:
            return True
        if db_value == "drinking" and candidate.drinking is True:
            return True
        if db_value == "divorced" and candidate.marital_status and \
                candidate.marital_status.value == "divorced":
            return True
        if db_value == "has_children":
            # Check family details for children
            children = candidate.family_details.get("has_children", False)
            if children:
                return True

        return False
