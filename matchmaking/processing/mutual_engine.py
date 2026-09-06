"""
Mutual (two-way) Matchmaking Engine

The logged-in user does not just need candidates who fit THEIR partner
preferences - they need candidates whose OWN partner preferences they fit too.
A match that only works in one direction is not a match.

    direction 1  (user_to_candidate):
        the logged-in user's partner preferences  ->  the candidate's profile
        "Does this person match what I am looking for?"

    direction 2  (candidate_to_user):
        the candidate's partner preferences  ->  the logged-in user's profile
        "Am I what this person is looking for?"

    mutual score =
        direction1 * user_preference_weight
      + direction2 * candidate_preference_weight
      - one-sidedness penalty

If either direction is rejected (deal breaker or failed hard constraint) the
pair is rejected outright, regardless of the numeric score.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.models import AiMatchMakingModel
from matchmaking.processing.compatibility_engine import CompatibilityEngine
from matchmaking.processing.normalizer import Normalizer
from matchmaking.schemas import (
    CompatibilityLevel,
    DirectionResult,
    MatchDirection,
    MatchStatus,
    ModelConfidence,
    MutualMatchResult,
    PartnerPreferences,
    UserProfile,
)

logger = logging.getLogger("matchmaking.mutual")


class MutualMatchingEngine:
    """Evaluates and ranks candidates using both sides' partner preferences."""

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self.compatibility_engine = CompatibilityEngine(self.config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match_against_list(
        self,
        user: UserProfile,
        user_prefs: PartnerPreferences,
        candidates: List[UserProfile],
        top_n: Optional[int] = None,
        min_score: Optional[int] = None,
        include_criterion_breakdown: bool = True,
    ) -> Tuple[List[MutualMatchResult], List[str]]:
        """Score the logged-in user against every user in the list.

        Returns:
            (results sorted by mutual score descending, warnings)
        """
        warnings: List[str] = []
        results: List[MutualMatchResult] = []

        normalized_user = Normalizer.normalize_user_profile(user)
        normalized_user_prefs = Normalizer.normalize_partner_preferences(user_prefs)

        for raw_candidate in candidates:
            if raw_candidate.user_id == normalized_user.user_id:
                warnings.append(
                    f"Skipped {raw_candidate.user_id}: same as the logged-in user"
                )
                continue
            try:
                results.append(
                    self.evaluate_pair(
                        user=normalized_user,
                        user_prefs=normalized_user_prefs,
                        candidate=raw_candidate,
                        include_criterion_breakdown=include_criterion_breakdown,
                    )
                )
            except Exception as exc:  # one bad profile must not break the batch
                logger.warning(
                    "Skipping candidate %s: %s", raw_candidate.user_id, exc
                )
                warnings.append(
                    f"Skipped {raw_candidate.user_id}: could not be evaluated"
                )

        results.sort(
            key=lambda r: (r.match_score, r.confidence_score), reverse=True
        )

        if min_score is not None:
            results = [r for r in results if r.match_score >= min_score]
        if top_n is not None and top_n > 0:
            results = results[:top_n]

        return results, warnings

    def evaluate_pair(
        self,
        user: UserProfile,
        user_prefs: PartnerPreferences,
        candidate: UserProfile,
        include_criterion_breakdown: bool = True,
    ) -> MutualMatchResult:
        """Evaluate one logged-in-user / candidate pair in both directions."""
        normalized_candidate = Normalizer.normalize_user_profile(candidate)
        candidate_prefs = candidate.partner_preferences

        # Direction 1: does the candidate fit what the logged-in user wants?
        forward_model = self.compatibility_engine.evaluate(
            user=user, candidate=normalized_candidate, prefs=user_prefs
        )
        forward = self._to_direction(
            forward_model,
            MatchDirection.USER_TO_CANDIDATE,
            include_criterion_breakdown,
        )

        # Direction 2: does the logged-in user fit what the candidate wants?
        if candidate_prefs is not None:
            normalized_candidate_prefs = Normalizer.normalize_partner_preferences(
                candidate_prefs
            )
            reverse_model = self.compatibility_engine.evaluate(
                user=normalized_candidate, candidate=user,
                prefs=normalized_candidate_prefs,
            )
            reverse = self._to_direction(
                reverse_model,
                MatchDirection.CANDIDATE_TO_USER,
                include_criterion_breakdown,
            )
        else:
            reverse_model = None
            reverse = DirectionResult(
                direction=MatchDirection.CANDIDATE_TO_USER,
                evaluated=False,
                note=(
                    f"{candidate.user_id} has not defined any partner preferences, "
                    "so only the logged-in user's preferences were scored"
                ),
            )

        mutual_score, balance, penalty = self._combine(forward_model, reverse_model)
        rejected = self._is_rejected(forward_model, reverse_model)

        compatibility_level = self._level(mutual_score)
        match_status = self._status(mutual_score, rejected)
        is_match = (
            not rejected and mutual_score >= self.config.match_threshold
        )

        confidence = self._combined_confidence(forward_model, reverse_model)
        mutual_prefs, one_sided = self._compare_directions(forward_model, reverse_model)

        return MutualMatchResult(
            candidate_id=normalized_candidate.user_id,
            candidate_name=normalized_candidate.name,
            is_match=is_match,
            match_score=mutual_score,
            match_percentage=float(mutual_score),
            compatibility_level=compatibility_level,
            match_status=match_status,
            model_confidence=self._confidence_bucket(confidence),
            confidence_score=confidence,
            your_preferences_match=forward,
            their_preferences_match=reverse,
            mutual_matched_preferences=mutual_prefs,
            one_sided_preferences=one_sided,
            match_reasons=self._reasons(forward_model, reverse_model, rejected),
            concerns=self._concerns(forward_model, reverse_model, balance, penalty),
            recommendations=self._recommendations(
                mutual_score, compatibility_level, rejected, balance
            ),
            score_balance=balance,
            ai_enhanced=forward_model.ai_enhanced,
        )

    # ------------------------------------------------------------------
    # Score combination
    # ------------------------------------------------------------------

    def _combine(
        self,
        forward: AiMatchMakingModel,
        reverse: Optional[AiMatchMakingModel],
    ) -> Tuple[int, int, float]:
        """Combine both directions into one mutual score.

        Returns (mutual_score, score_gap, penalty_applied).
        """
        if reverse is None:
            # Only one side has preferences - report that side's score as-is.
            return forward.match_score, 0, 0.0

        fw = self.config.user_preference_weight
        rw = self.config.candidate_preference_weight
        total = fw + rw
        if total <= 0:
            fw, rw, total = 0.5, 0.5, 1.0

        combined = (forward.match_score * fw + reverse.match_score * rw) / total
        gap = abs(forward.match_score - reverse.match_score)

        penalty = 0.0
        if self.config.mutual_balance_penalty_enabled:
            threshold = self.config.mutual_balance_gap_threshold
            if gap > threshold:
                # Scale linearly from 0 at the threshold to the configured max
                over = gap - threshold
                span = max(1, 100 - threshold)
                penalty = min(
                    self.config.mutual_balance_max_penalty,
                    self.config.mutual_balance_max_penalty * (over / span),
                )

        score = int(round(max(0.0, min(100.0, combined - penalty))))
        return score, gap, round(penalty, 2)

    @staticmethod
    def _is_rejected(
        forward: AiMatchMakingModel, reverse: Optional[AiMatchMakingModel]
    ) -> bool:
        """A pair is rejected if EITHER side has a blocking failure."""
        for model in (forward, reverse):
            if model is None:
                continue
            if model.deal_breakers_violated or not model.hard_constraints_passed:
                return True
        return False

    def _combined_confidence(
        self,
        forward: AiMatchMakingModel,
        reverse: Optional[AiMatchMakingModel],
    ) -> int:
        if reverse is None:
            # Only half the picture is available, so cap the confidence.
            return max(0, min(100, int(round(forward.confidence_score * 0.75))))
        return max(
            0,
            min(100, int(round((forward.confidence_score + reverse.confidence_score) / 2))),
        )

    def _confidence_bucket(self, confidence: int) -> ModelConfidence:
        if confidence >= self.config.confidence_high_threshold:
            return ModelConfidence.HIGH
        if confidence >= self.config.confidence_medium_threshold:
            return ModelConfidence.MEDIUM
        return ModelConfidence.LOW

    def _level(self, score: int) -> CompatibilityLevel:
        if score >= self.config.high_compatibility_threshold:
            return CompatibilityLevel.VERY_HIGH
        if score >= self.config.match_threshold:
            return CompatibilityLevel.HIGH
        if score >= self.config.medium_compatibility_threshold:
            return CompatibilityLevel.MEDIUM
        if score >= self.config.low_compatibility_threshold:
            return CompatibilityLevel.LOW
        if score > 0:
            return CompatibilityLevel.VERY_LOW
        return CompatibilityLevel.NONE

    def _status(self, score: int, rejected: bool) -> MatchStatus:
        if rejected:
            return MatchStatus.REJECTED
        if score >= self.config.match_threshold:
            return MatchStatus.MATCH
        if score >= self.config.medium_compatibility_threshold:
            return MatchStatus.PARTIAL_MATCH
        return MatchStatus.NO_MATCH

    # ------------------------------------------------------------------
    # Presentation
    # ------------------------------------------------------------------

    def _to_direction(
        self,
        model: AiMatchMakingModel,
        direction: MatchDirection,
        include_criterion_breakdown: bool,
    ) -> DirectionResult:
        """Convert one deterministic evaluation into a DirectionResult."""
        breakdown = []
        if include_criterion_breakdown:
            # Only report criteria the preference-owner actually asked about.
            breakdown = [c for c in model.criterion_matches if c.applicable]
            breakdown.sort(key=lambda c: c.weight, reverse=True)

        return DirectionResult(
            direction=direction,
            evaluated=True,
            score=model.match_score,
            match_percentage=float(model.match_score),
            compatibility_level=model.compatibility_level,
            match_status=model.match_status,
            is_match=model.is_match,
            criterion_matches=breakdown,
            matched_preferences=model.matched_preferences,
            partial_matches=model.partial_matches,
            mismatched_preferences=model.mismatched_preferences,
            deal_breakers_violated=model.deal_breakers_violated,
            failed_hard_constraints=model.failed_hard_constraints,
        )

    @staticmethod
    def _compare_directions(
        forward: AiMatchMakingModel, reverse: Optional[AiMatchMakingModel]
    ) -> Tuple[List[str], List[str]]:
        """Split criteria into 'satisfied both ways' and 'satisfied one way'."""
        fw = set(forward.matched_preferences)
        if reverse is None:
            return sorted(fw), []
        rv = set(reverse.matched_preferences)
        return sorted(fw & rv), sorted(fw ^ rv)

    def _reasons(
        self,
        forward: AiMatchMakingModel,
        reverse: Optional[AiMatchMakingModel],
        rejected: bool,
    ) -> List[str]:
        reasons: List[str] = []

        if rejected:
            for label, model in (
                ("Your requirements", forward),
                ("Their requirements", reverse),
            ):
                if model is None:
                    continue
                if model.deal_breakers_violated:
                    reasons.append(
                        f"{label}: deal breaker violated "
                        f"({', '.join(model.deal_breakers_violated)})"
                    )
                if not model.hard_constraints_passed:
                    reasons.append(
                        f"{label}: mandatory criteria not met "
                        f"({'; '.join(model.failed_hard_constraints[:2])})"
                    )
            return reasons[:5]

        mutual, _ = self._compare_directions(forward, reverse)
        if mutual:
            reasons.append(f"Satisfied in both directions: {', '.join(mutual[:5])}")

        reasons.extend(forward.match_reasons[:2])
        if reverse is not None:
            reasons.extend(
                f"They would also find a match on: {r}"
                for r in reverse.match_reasons[:1]
            )
        return reasons[:5]

    @staticmethod
    def _concerns(
        forward: AiMatchMakingModel,
        reverse: Optional[AiMatchMakingModel],
        balance: int,
        penalty: float,
    ) -> List[str]:
        concerns: List[str] = []

        if reverse is None:
            concerns.append(
                "Only one side's preferences were available - the score is one-way"
            )
        elif penalty > 0:
            higher = "you" if forward.match_score > reverse.match_score else "they"
            concerns.append(
                f"One-sided interest: the scores differ by {balance} points "
                f"({higher} match far better than the other way round)"
            )

        concerns.extend(forward.concerns[:2])
        if reverse is not None:
            concerns.extend(f"From their side: {c}" for c in reverse.concerns[:2])
        return concerns[:5]

    def _recommendations(
        self,
        score: int,
        level: CompatibilityLevel,
        rejected: bool,
        balance: int,
    ) -> List[str]:
        if rejected:
            return ["Do not surface this pairing - a mandatory requirement fails"]

        recommendations: List[str] = []
        if level in (CompatibilityLevel.VERY_HIGH, CompatibilityLevel.HIGH):
            recommendations.append(
                "Strong two-way compatibility - recommend surfacing this profile"
            )
        elif level == CompatibilityLevel.MEDIUM:
            recommendations.append(
                "Moderate compatibility - surface with the differences highlighted"
            )
        else:
            recommendations.append(
                "Low compatibility - only surface if the candidate pool is small"
            )

        if balance > self.config.mutual_balance_gap_threshold:
            recommendations.append(
                "Interest is uneven; expect a lower response rate from the "
                "lower-scoring side"
            )
        return recommendations[:3]
