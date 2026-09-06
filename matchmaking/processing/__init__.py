"""
Matchmaking Processing Package

Contains the core processing modules:
- normalizer: Input data normalization
- validator: Input validation
- preference_processor: Preference analysis and classification
- scoring_engine: Criterion-level scoring with weighting
- compatibility_engine: Overall compatibility calculation
- ranking_engine: Multi-candidate ranking
- mutual_engine: Two-way (mutual) matchmaking
"""

from matchmaking.processing.normalizer import Normalizer
from matchmaking.processing.validator import Validator
from matchmaking.processing.preference_processor import PreferenceProcessor
from matchmaking.processing.scoring_engine import ScoringEngine
from matchmaking.processing.compatibility_engine import CompatibilityEngine
from matchmaking.processing.ranking_engine import RankingEngine
from matchmaking.processing.mutual_engine import MutualMatchingEngine

__all__ = [
    "Normalizer",
    "Validator",
    "PreferenceProcessor",
    "ScoringEngine",
    "CompatibilityEngine",
    "RankingEngine",
    "MutualMatchingEngine",
]
