"""
Matchmaking Input/Output Schemas

These Pydantic models define the strict contracts for:
- What the backend sends TO the matchmaking model (Input)
- What the matchmaking model sends BACK to the backend (Output)

All validation happens at the schema level.
The backend is the source of truth for data.
The AI model is the source of truth for matchmaking intelligence.

Partner preference coverage follows section 17 of the product document:
    Age range, Height range, Location, Country, Marital status, Religion,
    Sect, Religious practice, Minimum education, Preferred field, Profession,
    Employment status, Income range, Family structure, Living arrangement,
    Family involvement, Smoking, Diet, Exercise, Social lifestyle,
    Personality traits, Marriage timeline, Children preference, Relocation,
    Career expectations.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from matchmaking.schemas.examples import MUTUAL_MATCH_EXAMPLE


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MaritalStatus(str, Enum):
    NEVER_MARRIED = "never_married"
    DIVORCED = "divorced"
    WIDOWED = "widowed"
    SEPARATED = "separated"
    AWAITING_DIVORCE = "awaiting_divorce"
    UNKNOWN = "unknown"


class EducationLevel(str, Enum):
    HIGH_SCHOOL = "high_school"
    DIPLOMA = "diploma"
    BACHELORS = "bachelors"
    MASTERS = "masters"
    DOCTORATE = "doctorate"
    PROFESSIONAL = "professional"
    OTHER = "other"
    UNKNOWN = "unknown"


class ReligiousPractice(str, Enum):
    """How actively a person practices their religion (document field 8)."""

    NOT_PRACTICING = "not_practicing"
    OCCASIONALLY_PRACTICING = "occasionally_practicing"
    MODERATELY_PRACTICING = "moderately_practicing"
    PRACTICING = "practicing"
    VERY_PRACTICING = "very_practicing"
    UNKNOWN = "unknown"


class EmploymentStatus(str, Enum):
    """Employment situation (document field 12)."""

    EMPLOYED = "employed"
    SELF_EMPLOYED = "self_employed"
    BUSINESS_OWNER = "business_owner"
    STUDENT = "student"
    HOMEMAKER = "homemaker"
    UNEMPLOYED = "unemployed"
    RETIRED = "retired"
    UNKNOWN = "unknown"


class FamilyStructure(str, Enum):
    """Family setup (document field 14)."""

    NUCLEAR = "nuclear"
    JOINT = "joint"
    EXTENDED = "extended"
    SINGLE_PARENT = "single_parent"
    UNKNOWN = "unknown"


class LivingArrangement(str, Enum):
    """Preferred living arrangement after marriage (document field 15)."""

    WITH_PARENTS = "with_parents"
    SEPARATE_HOUSE = "separate_house"
    INDEPENDENT = "independent"
    ABROAD = "abroad"
    FLEXIBLE = "flexible"
    UNKNOWN = "unknown"


class FamilyInvolvement(str, Enum):
    """How involved the extended family is in daily life (document field 16)."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    MINIMAL = "minimal"
    UNKNOWN = "unknown"


class ExerciseFrequency(str, Enum):
    """Exercise habits (document field 19)."""

    DAILY = "daily"
    REGULAR = "regular"
    OCCASIONAL = "occasional"
    RARELY = "rarely"
    NEVER = "never"
    UNKNOWN = "unknown"


class SocialLifestyle(str, Enum):
    """Social lifestyle (document field 20)."""

    VERY_SOCIAL = "very_social"
    SOCIAL = "social"
    BALANCED = "balanced"
    RESERVED = "reserved"
    HOMEBODY = "homebody"
    UNKNOWN = "unknown"


class MarriageTimeline(str, Enum):
    """How soon the person wants to marry (document field 22)."""

    IMMEDIATELY = "immediately"
    WITHIN_6_MONTHS = "within_6_months"
    WITHIN_1_YEAR = "within_1_year"
    WITHIN_2_YEARS = "within_2_years"
    NO_RUSH = "no_rush"
    UNDECIDED = "undecided"
    UNKNOWN = "unknown"


class ChildrenPreference(str, Enum):
    """Attitude towards children (document field 23)."""

    WANT_CHILDREN = "want_children"
    DONT_WANT_CHILDREN = "dont_want_children"
    OPEN_TO_CHILDREN = "open_to_children"
    HAVE_AND_WANT_MORE = "have_and_want_more"
    HAVE_AND_NO_MORE = "have_and_no_more"
    UNDECIDED = "undecided"
    UNKNOWN = "unknown"


class RelocationPreference(str, Enum):
    """Willingness to relocate (document field 24)."""

    WILLING = "willing"
    NEGOTIABLE = "negotiable"
    WITHIN_COUNTRY_ONLY = "within_country_only"
    NOT_WILLING = "not_willing"
    UNKNOWN = "unknown"


class CareerExpectation(str, Enum):
    """Career expectation after marriage (document field 25)."""

    CONTINUE_CAREER = "continue_career"
    PART_TIME = "part_time"
    FLEXIBLE = "flexible"
    STOP_AFTER_MARRIAGE = "stop_after_marriage"
    UNDECIDED = "undecided"
    UNKNOWN = "unknown"


class CompatibilityLevel(str, Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"
    NONE = "none"


class MatchStatus(str, Enum):
    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    NO_MATCH = "no_match"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


class ModelConfidence(str, Enum):
    """Document requirement: MODEL CONFIDENCE (low / med / high)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MatchDirection(str, Enum):
    """Which side's partner preferences were applied."""

    USER_TO_CANDIDATE = "user_to_candidate"
    CANDIDATE_TO_USER = "candidate_to_user"


# ---------------------------------------------------------------------------
# Nested Data Models
# ---------------------------------------------------------------------------


class AgeRange(BaseModel):
    """Age range preference."""

    min: Optional[int] = Field(None, ge=18, le=100, description="Minimum age")
    max: Optional[int] = Field(None, ge=18, le=100, description="Maximum age")

    @field_validator("min")
    @classmethod
    def validate_min(cls, v: Optional[int]) -> Optional[int]:
        return v

    @model_validator(mode="after")
    def validate_range(self) -> "AgeRange":
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                raise ValueError("min age cannot be greater than max age")
        return self


class HeightRange(BaseModel):
    """Height range in centimeters."""

    min_cm: Optional[int] = Field(None, ge=100, le=250)
    max_cm: Optional[int] = Field(None, ge=100, le=250)

    @model_validator(mode="after")
    def validate_range(self) -> "HeightRange":
        if self.min_cm is not None and self.max_cm is not None:
            if self.min_cm > self.max_cm:
                raise ValueError("min height cannot be greater than max height")
        return self


class IncomeRange(BaseModel):
    """Monthly income range preference (document field 13).

    ``currency`` is informational only - the backend is responsible for
    sending comparable figures.
    """

    min: Optional[float] = Field(None, ge=0, description="Minimum monthly income")
    max: Optional[float] = Field(None, ge=0, description="Maximum monthly income")
    currency: Optional[str] = Field(None, description="e.g. PKR, USD")

    @model_validator(mode="after")
    def validate_range(self) -> "IncomeRange":
        if self.min is not None and self.max is not None:
            if self.min > self.max:
                raise ValueError("min income cannot be greater than max income")
        return self


class Location(BaseModel):
    """Location information for a user/candidate."""

    city: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None

    model_config = {"extra": "allow"}


class PartnerPreferences(BaseModel):
    """Partner preferences sent by the backend.

    These are the preferences a user has specified for their ideal partner.
    The AI model processes these dynamically - they are NEVER hardcoded.

    Every field of section 17 of the product document is represented here.
    Any field left as ``None``/empty is simply not evaluated: it does not
    drag the score towards neutral.
    """

    # --- Basic ----------------------------------------------------------
    gender: Optional[Gender] = None
    age_range: Optional[AgeRange] = None
    height_range: Optional[HeightRange] = None
    marital_status: Optional[List[MaritalStatus]] = None
    mother_tongue: Optional[List[str]] = None

    # --- Location -------------------------------------------------------
    location: Optional[List[str]] = Field(None, description="Preferred cities")
    country: Optional[List[str]] = Field(None, description="Preferred countries")

    # --- Religion -------------------------------------------------------
    religion: Optional[List[str]] = None
    sect: Optional[List[str]] = None
    religious_practice: Optional[List[ReligiousPractice]] = Field(
        None, description="Acceptable levels of religious practice"
    )

    # --- Education / Career ---------------------------------------------
    education: Optional[List[EducationLevel]] = Field(
        None, description="Acceptable education levels"
    )
    min_education: Optional[EducationLevel] = Field(
        None,
        description=(
            "Minimum acceptable education level. Anything at or above this "
            "level scores as a match."
        ),
    )
    preferred_field: Optional[List[str]] = Field(
        None, description="Preferred field of study, e.g. Medicine, Engineering"
    )
    profession: Optional[List[str]] = None
    profession_category: Optional[List[str]] = None
    employment_status: Optional[List[EmploymentStatus]] = None
    income_range: Optional[Union[IncomeRange, str]] = Field(
        None,
        description=(
            "Preferred monthly income. Either a structured {min, max, currency} "
            "object or a free-text band such as '150000-300000'."
        ),
    )

    # --- Family -----------------------------------------------------------
    family_structure: Optional[List[FamilyStructure]] = None
    living_arrangement: Optional[List[LivingArrangement]] = None
    family_involvement: Optional[List[FamilyInvolvement]] = None

    # --- Lifestyle --------------------------------------------------------
    smoking: Optional[bool] = Field(
        None, description="True = partner may smoke, False = partner must not smoke"
    )
    drinking: Optional[bool] = None
    diet: Optional[List[str]] = Field(
        None, description="Acceptable diets, e.g. ['Halal', 'Vegetarian']"
    )
    exercise: Optional[List[ExerciseFrequency]] = None
    social_lifestyle: Optional[List[SocialLifestyle]] = None
    lifestyle: Dict[str, Any] = Field(default_factory=dict)

    # --- Personality / Interests -------------------------------------------
    personality_traits: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    hobbies: List[str] = Field(default_factory=list)

    # --- Marriage expectations ----------------------------------------------
    marriage_timeline: Optional[List[MarriageTimeline]] = None
    children_preference: Optional[List[ChildrenPreference]] = None
    relocation: Optional[List[RelocationPreference]] = None
    career_expectation: Optional[List[CareerExpectation]] = None

    # --- Constraints ----------------------------------------------------------
    deal_breakers: List[str] = Field(default_factory=list)
    hard_constraints: Dict[str, Any] = Field(default_factory=dict)
    soft_preferences: Dict[str, Any] = Field(default_factory=dict)

    # Allow extra fields for forward compatibility
    model_config = {"extra": "allow"}

    @field_validator("diet", mode="before")
    @classmethod
    def coerce_diet(cls, v: Any) -> Any:
        """Accept a single string for backwards compatibility."""
        if isinstance(v, str):
            return [v]
        return v


class UserProfile(BaseModel):
    """User/Candidate profile data.

    This model represents the data the backend sends about a user or candidate.
    All fields are optional to support incomplete profiles.

    A candidate may carry its own ``partner_preferences`` so that the model can
    score the match in BOTH directions (mutual matchmaking).
    """

    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    name: Optional[str] = Field(None, description="Display name, for readability only")
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = Field(None, ge=18, le=120)
    height_cm: Optional[int] = Field(None, ge=100, le=250)
    marital_status: Optional[MaritalStatus] = None
    mother_tongue: Optional[str] = None

    # --- Religion -------------------------------------------------------
    religion: Optional[str] = None
    sect: Optional[str] = None
    religious_practice: Optional[ReligiousPractice] = None

    # --- Education / Career ---------------------------------------------
    education: Optional[EducationLevel] = None
    education_details: Optional[str] = None
    education_field: Optional[str] = Field(
        None, description="Field of study, e.g. Computer Science"
    )
    profession: Optional[str] = None
    profession_category: Optional[str] = None
    employment_status: Optional[EmploymentStatus] = None
    income_range: Optional[str] = None
    monthly_income: Optional[float] = Field(
        None, ge=0, description="Numeric monthly income, preferred over income_range"
    )

    # --- Location -------------------------------------------------------
    location: Optional[Location] = None

    # --- Family -----------------------------------------------------------
    family_structure: Optional[FamilyStructure] = None
    living_arrangement: Optional[LivingArrangement] = None
    family_involvement: Optional[FamilyInvolvement] = None
    family_details: Dict[str, Any] = Field(default_factory=dict)

    # --- Lifestyle --------------------------------------------------------
    interests: List[str] = Field(default_factory=list)
    hobbies: List[str] = Field(default_factory=list)
    personality_traits: List[str] = Field(default_factory=list)
    lifestyle: Dict[str, Any] = Field(default_factory=dict)
    smoking: Optional[bool] = None
    drinking: Optional[bool] = None
    diet: Optional[str] = None
    exercise: Optional[ExerciseFrequency] = None
    social_lifestyle: Optional[SocialLifestyle] = None

    # --- Marriage expectations ----------------------------------------------
    marriage_timeline: Optional[MarriageTimeline] = None
    children_preference: Optional[ChildrenPreference] = None
    relocation: Optional[RelocationPreference] = None
    career_expectation: Optional[CareerExpectation] = None

    # --- Free text -----------------------------------------------------------
    about_me: Optional[str] = None
    photos_count: int = 0
    profile_completeness: Optional[float] = Field(None, ge=0, le=100)

    # --- This person's OWN preferences (enables mutual matching) --------------
    partner_preferences: Optional[PartnerPreferences] = Field(
        None,
        description=(
            "This person's own partner preferences. When present, the model "
            "also scores how well the logged-in user fits THEM, producing a "
            "mutual (two-way) match score."
        ),
    )

    # Allow extra fields for forward compatibility
    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def compute_age_from_dob(self) -> "UserProfile":
        """Compute age from date_of_birth if age is not provided."""
        if self.age is None and self.date_of_birth is not None:
            today = date.today()
            self.age = (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
        return self


class MatchContext(BaseModel):
    """Additional context for matchmaking."""

    request_timestamp: Optional[datetime] = None
    source: Optional[str] = None  # e.g., "api", "batch", "recommendation"
    priority: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Request / Response Contracts
# ---------------------------------------------------------------------------


class MatchmakingRequest(BaseModel):
    """Request contract: what the backend sends to the matchmaking model.

    The backend is responsible for fetching all data and sending it here.
    The AI model does NOT access any database.
    """

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier for tracking",
    )
    user: UserProfile = Field(..., description="The user seeking a partner")
    partner_preferences: PartnerPreferences = Field(
        ..., description="Partner preferences from the backend"
    )
    candidate: Optional[UserProfile] = Field(
        None,
        description="Single candidate to evaluate against preferences",
    )
    candidates: Optional[List[UserProfile]] = Field(
        None,
        description="Multiple candidates to evaluate and rank",
    )
    context: MatchContext = Field(default_factory=MatchContext)

    @model_validator(mode="after")
    def validate_candidate_or_candidates(self) -> "MatchmakingRequest":
        if self.candidate is None and self.candidates is None:
            raise ValueError(
                "Either 'candidate' or 'candidates' must be provided"
            )
        return self


class CriterionMatch(BaseModel):
    """Result of evaluating a single criterion."""

    criterion: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(ge=0, le=1.0)
    weighted_score: float = Field(ge=0, le=100)
    status: MatchStatus
    reason: str
    is_hard_constraint: bool = False
    applicable: bool = Field(
        default=True,
        description=(
            "False when no preference was specified for this criterion. "
            "Non-applicable criteria are excluded from the weighted score so "
            "unset preferences never pull the result towards 50%."
        ),
    )
    candidate_value: Optional[Any] = None
    preference_value: Optional[Any] = None


class CandidateMatchResult(BaseModel):
    """Matchmaking result for a single candidate."""

    candidate_id: str
    is_match: bool
    match_score: int = Field(ge=0, le=100)
    match_percentage: float = Field(
        default=0.0, ge=0, le=100, description="Match score expressed as a percentage"
    )
    compatibility_level: CompatibilityLevel
    match_status: MatchStatus

    # Breakdown
    criterion_matches: List[CriterionMatch] = Field(default_factory=list)

    # Explanation
    matched_preferences: List[str] = Field(default_factory=list)
    partial_matches: List[str] = Field(default_factory=list)
    mismatched_preferences: List[str] = Field(default_factory=list)
    deal_breakers_violated: List[str] = Field(default_factory=list)
    match_reasons: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    # Confidence
    confidence_score: int = Field(
        ge=0, le=100, description="How confident the model is in this result"
    )
    model_confidence: ModelConfidence = Field(
        default=ModelConfidence.MEDIUM,
        description="Confidence bucket: low / medium / high",
    )

    # Metadata
    processing_time_ms: Optional[float] = None
    ai_enhanced: bool = False


class MatchmakingResponse(BaseModel):
    """Response contract: what the matchmaking model returns to the backend.

    This is machine-readable, structured, and validated.
    The backend can directly consume this.
    """

    success: bool = True
    model_version: str = "1.0.0"
    request_id: str = ""
    processing_time_ms: Optional[float] = None

    # Single candidate result
    result: Optional[CandidateMatchResult] = None

    # Multiple candidate results (sorted by score descending)
    results: Optional[List[CandidateMatchResult]] = None

    # Error information
    error: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Mutual (two-way) matchmaking contracts
# ---------------------------------------------------------------------------


class DirectionResult(BaseModel):
    """One direction of a two-way evaluation.

    ``user_to_candidate``  = how well the candidate satisfies the logged-in
                             user's partner preferences.
    ``candidate_to_user``  = how well the logged-in user satisfies the
                             candidate's own partner preferences.
    """

    direction: MatchDirection
    evaluated: bool = Field(
        default=True,
        description="False when this side has not defined any partner preferences",
    )
    score: int = Field(default=0, ge=0, le=100)
    match_percentage: float = Field(default=0.0, ge=0, le=100)
    compatibility_level: CompatibilityLevel = CompatibilityLevel.NONE
    match_status: MatchStatus = MatchStatus.UNKNOWN
    is_match: bool = False

    criterion_matches: List[CriterionMatch] = Field(default_factory=list)
    matched_preferences: List[str] = Field(default_factory=list)
    partial_matches: List[str] = Field(default_factory=list)
    mismatched_preferences: List[str] = Field(default_factory=list)
    deal_breakers_violated: List[str] = Field(default_factory=list)
    failed_hard_constraints: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class MutualMatchResult(BaseModel):
    """Two-way matchmaking result between the logged-in user and one candidate."""

    candidate_id: str
    candidate_name: Optional[str] = None

    is_match: bool
    match_score: int = Field(ge=0, le=100, description="Mutual compatibility score")
    match_percentage: float = Field(
        ge=0, le=100, description="Mutual compatibility as a percentage"
    )
    compatibility_level: CompatibilityLevel
    match_status: MatchStatus

    # Document requirement: MODEL CONFIDENCE (low / med / high)
    model_confidence: ModelConfidence
    confidence_score: int = Field(ge=0, le=100)

    # Both directions
    your_preferences_match: DirectionResult = Field(
        description="Logged-in user's preferences evaluated against this candidate"
    )
    their_preferences_match: DirectionResult = Field(
        description="This candidate's preferences evaluated against the logged-in user"
    )

    # Aggregated explainability
    mutual_matched_preferences: List[str] = Field(default_factory=list)
    one_sided_preferences: List[str] = Field(
        default_factory=list,
        description="Criteria satisfied in one direction only",
    )
    match_reasons: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)

    score_balance: int = Field(
        default=0,
        description="abs(your score - their score); high values mean one-sided interest",
    )
    ai_enhanced: bool = False
    processing_time_ms: Optional[float] = None


class MutualMatchRequest(BaseModel):
    """Request contract for logged-in-user vs. user-list matchmaking.

    The backend sends the logged-in user (with their partner preferences) and
    the list of users currently visible to them. Each listed user may carry
    their OWN partner preferences, which enables true two-way matching.
    """

    request_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier for tracking",
    )
    logged_in_user: UserProfile = Field(
        ..., description="The currently logged-in user"
    )
    partner_preferences: Optional[PartnerPreferences] = Field(
        None,
        description=(
            "Logged-in user's partner preferences. Optional if they are already "
            "set on logged_in_user.partner_preferences; this field wins if both "
            "are present."
        ),
    )
    users: List[UserProfile] = Field(
        ...,
        min_length=1,
        description=(
            "The users appearing in the list. Each one should include its own "
            "partner_preferences for two-way scoring."
        ),
    )
    top_n: Optional[int] = Field(
        None, ge=1, description="Return only the top N matches"
    )
    min_score: Optional[int] = Field(
        None, ge=0, le=100, description="Drop results below this mutual score"
    )
    include_criterion_breakdown: bool = Field(
        True, description="Include the per-criterion score breakdown in the response"
    )
    context: MatchContext = Field(default_factory=MatchContext)

    model_config = {"json_schema_extra": {"examples": [MUTUAL_MATCH_EXAMPLE]}}

    @model_validator(mode="after")
    def ensure_preferences_present(self) -> "MutualMatchRequest":
        if self.partner_preferences is None:
            if self.logged_in_user.partner_preferences is None:
                raise ValueError(
                    "partner_preferences must be provided either at the top "
                    "level or on logged_in_user.partner_preferences"
                )
            self.partner_preferences = self.logged_in_user.partner_preferences
        return self


class MutualMatchResponse(BaseModel):
    """Response contract for logged-in-user vs. user-list matchmaking."""

    success: bool = True
    model_version: str = "1.0.0"
    request_id: str = ""
    processing_time_ms: Optional[float] = None

    logged_in_user_id: str = ""
    total_users_evaluated: int = 0
    total_matches: int = 0

    matches: List[MutualMatchResult] = Field(
        default_factory=list,
        description="Ranked by mutual match score, highest first",
    )

    warnings: List[str] = Field(default_factory=list)
    error: Optional[Dict[str, Any]] = None
