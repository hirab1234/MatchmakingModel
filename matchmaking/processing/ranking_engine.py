"""
Ranking Engine

Handles evaluation and ranking of multiple candidates.
Sorts candidates by match score (descending) and returns
top results.
"""

from __future__ import annotations

from typing import List, Optional

from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.models import AiMatchMakingModel
from matchmaking.processing.compatibility_engine import CompatibilityEngine
from matchmaking.processing.normalizer import Normalizer
from matchmaking.processing.preference_processor import PreferenceProcessor
from matchmaking.schemas import PartnerPreferences, UserProfile


class RankingEngine:
    """Evaluates and ranks multiple candidates."""

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self.compatibility_engine = CompatibilityEngine(self.config)

    def evaluate_and_rank(
        self,
        user: UserProfile,
        candidates: List[UserProfile],
        prefs: PartnerPreferences,
        top_n: Optional[int] = None,
    ) -> List[AiMatchMakingModel]:
        """Evaluate all candidates and return ranked results.

        Args:
            user: The user seeking a partner.
            candidates: List of candidates to evaluate.
            prefs: Partner preferences.
            top_n: Optional limit on results returned.

        Returns:
            List of AiMatchMakingModel sorted by score (descending).
        """
        # Normalize candidates once
        normalized_candidates = [
            Normalizer.normalize_user_profile(c) for c in candidates
        ]

        # Classify preferences once for all candidates
        weights = self.config.weights.to_dict()
        classification = PreferenceProcessor.classify_preferences(prefs, weights)

        # Evaluate each candidate
        results: List[AiMatchMakingModel] = []
        for candidate in normalized_candidates:
            try:
                result = self.compatibility_engine.evaluate(
                    user=user,
                    candidate=candidate,
                    prefs=prefs,
                    classification=classification,
                )
                results.append(result)
            except Exception:
                # Don't let one bad candidate break the batch
                continue

        # Sort by match score descending, then by confidence
        results.sort(
            key=lambda r: (r.match_score, r.confidence_score),
            reverse=True,
        )

        # Apply top_n limit
        if top_n is not None and top_n > 0:
            results = results[:top_n]

        return results
