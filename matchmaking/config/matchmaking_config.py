"""
Matchmaking Configuration

All configurable values are centralized here.
Values can be overridden via environment variables.
No magic numbers are scattered throughout the codebase.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class ScoringWeights:
    """Configurable weights for each matching criterion.

    Weights determine the relative importance of each criterion
    in the final compatibility score calculation.

    Weight range: 0.0 (ignored) to 1.0 (maximum importance).
    The defaults sum to 1.0 and cover every partner preference listed in
    section 17 of the product document.

    Note: the final score is a weighted AVERAGE over the criteria that were
    actually applicable (i.e. the user specified that preference), so the
    weights do not have to sum to 1.0 - they only define relative importance.
    """

    # Basic
    age: float = 0.06
    height: float = 0.02
    location: float = 0.10
    marital_status: float = 0.04
    mother_tongue: float = 0.02

    # Religion
    religion: float = 0.09
    sect: float = 0.05
    religious_practice: float = 0.05

    # Education / career
    education: float = 0.05
    education_field: float = 0.02
    profession: float = 0.04
    employment_status: float = 0.03
    income: float = 0.03

    # Family
    family_structure: float = 0.03
    living_arrangement: float = 0.02
    family_involvement: float = 0.02

    # Lifestyle
    smoking: float = 0.02
    drinking: float = 0.01
    diet: float = 0.02
    exercise: float = 0.02
    social_lifestyle: float = 0.02
    lifestyle: float = 0.01

    # Personality / interests
    personality: float = 0.05
    interests: float = 0.05

    # Marriage expectations
    marriage_timeline: float = 0.04
    children_preference: float = 0.05
    relocation: float = 0.02
    career_expectation: float = 0.02

    def to_dict(self) -> Dict[str, float]:
        return {
            "age": self.age,
            "height": self.height,
            "location": self.location,
            "marital_status": self.marital_status,
            "mother_tongue": self.mother_tongue,
            "religion": self.religion,
            "sect": self.sect,
            "religious_practice": self.religious_practice,
            "education": self.education,
            "education_field": self.education_field,
            "profession": self.profession,
            "employment_status": self.employment_status,
            "income": self.income,
            "family_structure": self.family_structure,
            "living_arrangement": self.living_arrangement,
            "family_involvement": self.family_involvement,
            "smoking": self.smoking,
            "drinking": self.drinking,
            "diet": self.diet,
            "exercise": self.exercise,
            "social_lifestyle": self.social_lifestyle,
            "lifestyle": self.lifestyle,
            "personality": self.personality,
            "interests": self.interests,
            "marriage_timeline": self.marriage_timeline,
            "children_preference": self.children_preference,
            "relocation": self.relocation,
            "career_expectation": self.career_expectation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "ScoringWeights":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass(frozen=True)
class MatchmakingConfig:
    """Production configuration for the matchmaking model."""

    # Model versioning
    model_version: str = "1.0.0"

    # Matching thresholds
    match_threshold: int = 70  # Score >= this = is_match
    high_compatibility_threshold: int = 85
    medium_compatibility_threshold: int = 60
    low_compatibility_threshold: int = 40

    # Deal breaker configuration
    deal_breaker_penalty: float = 100.0  # Full penalty for deal breaker
    hard_constraint_failure_penalty: float = 80.0

    # Scoring configuration
    weights: ScoringWeights = field(default_factory=ScoringWeights)

    # Missing data behavior
    missing_data_score: float = 50.0  # Neutral score for unknown data
    missing_data_enabled: bool = True  # Whether to score missing data as neutral

    # --- Mutual (two-way) matching -----------------------------------------
    # How the two directions are combined into one mutual score:
    #   mutual = (user->candidate * user_preference_weight)
    #          + (candidate->user * candidate_preference_weight)
    user_preference_weight: float = 0.6
    candidate_preference_weight: float = 0.4
    # A large gap between the two directions means one-sided interest.
    mutual_balance_penalty_enabled: bool = True
    mutual_balance_gap_threshold: int = 30  # Gap above which the penalty starts
    mutual_balance_max_penalty: float = 8.0  # Maximum points deducted

    # Model confidence buckets (document: low / med / high)
    confidence_high_threshold: int = 75
    confidence_medium_threshold: int = 50

    # AI configuration
    ai_provider: str = "openai"
    ai_model: str = "gpt-4o"
    ai_temperature: float = 0.1  # Low temperature for deterministic output
    ai_timeout: int = 30  # Seconds
    ai_max_retries: int = 2
    ai_enabled: bool = True  # Can disable AI for testing or fallback

    # Processing
    max_candidates_per_request: int = 100
    processing_timeout: int = 60  # Seconds

    # Logging
    log_level: str = "INFO"
    log_sensitive_data: bool = False

    @classmethod
    def from_env(cls) -> "MatchmakingConfig":
        """Load configuration from environment variables with defaults."""

        weights_dict = {}
        default_weights = ScoringWeights()
        for field_name in default_weights.to_dict():
            env_key = f"SCORING_WEIGHT_{field_name.upper()}"
            env_val = os.getenv(env_key)
            if env_val is not None:
                weights_dict[field_name] = float(env_val)

        weights = (
            ScoringWeights.from_dict(weights_dict)
            if weights_dict
            else default_weights
        )

        return cls(
            model_version=os.getenv("MODEL_VERSION", "1.0.0"),
            match_threshold=int(os.getenv("MATCH_THRESHOLD", "70")),
            high_compatibility_threshold=int(
                os.getenv("HIGH_COMPATIBILITY_THRESHOLD", "85")
            ),
            medium_compatibility_threshold=int(
                os.getenv("MEDIUM_COMPATIBILITY_THRESHOLD", "60")
            ),
            low_compatibility_threshold=int(
                os.getenv("LOW_COMPATIBILITY_THRESHOLD", "40")
            ),
            weights=weights,
            user_preference_weight=float(
                os.getenv("USER_PREFERENCE_WEIGHT", "0.6")
            ),
            candidate_preference_weight=float(
                os.getenv("CANDIDATE_PREFERENCE_WEIGHT", "0.4")
            ),
            mutual_balance_penalty_enabled=os.getenv(
                "MUTUAL_BALANCE_PENALTY_ENABLED", "true"
            ).lower() == "true",
            mutual_balance_gap_threshold=int(
                os.getenv("MUTUAL_BALANCE_GAP_THRESHOLD", "30")
            ),
            mutual_balance_max_penalty=float(
                os.getenv("MUTUAL_BALANCE_MAX_PENALTY", "8.0")
            ),
            confidence_high_threshold=int(
                os.getenv("CONFIDENCE_HIGH_THRESHOLD", "75")
            ),
            confidence_medium_threshold=int(
                os.getenv("CONFIDENCE_MEDIUM_THRESHOLD", "50")
            ),
            ai_provider=os.getenv("AI_PROVIDER", "openai"),
            ai_model=os.getenv("AI_MODEL", "gpt-4o"),
            ai_temperature=float(os.getenv("AI_TEMPERATURE", "0.1")),
            ai_timeout=int(os.getenv("AI_TIMEOUT", "30")),
            ai_max_retries=int(os.getenv("AI_MAX_RETRIES", "2")),
            ai_enabled=os.getenv("AI_ENABLED", "true").lower() == "true",
            max_candidates_per_request=int(
                os.getenv("MAX_CANDIDATES_PER_REQUEST", "100")
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


# Singleton instance
_config: Optional[MatchmakingConfig] = None


def get_config() -> MatchmakingConfig:
    """Get or create the singleton configuration instance."""
    global _config
    if _config is None:
        _config = MatchmakingConfig.from_env()
    return _config


def reset_config() -> None:
    """Reset configuration (useful for testing)."""
    global _config
    _config = None
