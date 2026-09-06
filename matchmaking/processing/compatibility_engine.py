"""
Compatibility Engine

Assembles the final compatibility result by combining:
- Hard constraint results
- Deal breaker results
- Criterion scores from the scoring engine
- Explainability (reasons, concerns, recommendations)
- Confidence calculation
- AI enhancement (if enabled)

This is where the AiMatchMakingModel is constructed.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.models import AiMatchMakingModel
from matchmaking.processing.normalizer import Normalizer
from matchmaking.processing.preference_processor import (
    PreferenceClassification,
    PreferenceProcessor,
)
from matchmaking.processing.scoring_engine import ScoringEngine
from matchmaking.schemas import (
    CompatibilityLevel,
    CriterionMatch,
    MatchStatus,
    ModelConfidence,
    PartnerPreferences,
    UserProfile,
)


class CompatibilityEngine:
    """Calculates overall compatibility and produces the AiMatchMakingModel."""

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self.scoring_engine = ScoringEngine(self.config)

    def evaluate(
        self,
        user: UserProfile,
        candidate: UserProfile,
        prefs: PartnerPreferences,
        classification: Optional[PreferenceClassification] = None,
    ) -> AiMatchMakingModel:
        """Full evaluation of a candidate against partner preferences.

        Args:
            user: The user seeking a partner.
            candidate: The candidate being evaluated.
            prefs: Partner preferences (from backend).
            classification: Pre-classified preferences (optional, computed if not provided).

        Returns:
            AiMatchMakingModel with complete evaluation results.
        """
        # Step 1: Classify preferences if not provided
        if classification is None:
            classification = PreferenceProcessor.classify_preferences(
                prefs, self.config.weights.to_dict()
            )

        # Step 2: Check hard constraints
        failed_constraints = PreferenceProcessor.check_hard_constraints(
            candidate, classification, user
        )
        hard_constraints_passed = len(failed_constraints) == 0

        # Step 3: Check deal breakers
        deal_breakers_violated = PreferenceProcessor.check_deal_breakers(
            candidate, classification
        )

        # Step 4: Score all criteria
        criterion_matches, overall_score, criterion_scores = (
            self.scoring_engine.score_all_criteria(user, candidate, prefs)
        )

        # Step 5: Apply deal breaker penalty
        if deal_breakers_violated:
            overall_score = max(0, overall_score - self.config.deal_breaker_penalty)

        # Step 6: Apply hard constraint failure penalty
        if not hard_constraints_passed:
            penalty = self.config.hard_constraint_failure_penalty * len(failed_constraints)
            overall_score = max(0, overall_score - penalty)

        overall_score = round(min(100.0, max(0.0, overall_score)))

        # Step 7: Determine compatibility level and match status
        compatibility_level = self._determine_compatibility_level(overall_score)
        match_status = self._determine_match_status(
            overall_score, hard_constraints_passed, deal_breakers_violated
        )
        is_match = overall_score >= self.config.match_threshold and hard_constraints_passed

        # Step 8: Generate explainability
        applicable = [c for c in criterion_matches if c.applicable]
        matched, partial, mismatched = self._categorize_criteria(applicable)
        match_reasons = self._generate_match_reasons(
            applicable, hard_constraints_passed, deal_breakers_violated
        )
        concerns = self._generate_concerns(
            applicable, failed_constraints, deal_breakers_violated
        )
        recommendations = self._generate_recommendations(
            applicable, overall_score, compatibility_level
        )

        # Step 9: Calculate confidence
        data_completeness = Normalizer.compute_data_completeness(candidate)
        user_completeness = Normalizer.compute_data_completeness(user)
        applicable_criteria = [c for c in criterion_matches if c.applicable]
        evaluated_criteria = [
            c for c in applicable_criteria if c.status != MatchStatus.UNKNOWN
        ]
        confidence = self._calculate_confidence(
            overall_score, data_completeness, user_completeness,
            hard_constraints_passed, len(evaluated_criteria)
        )
        model_confidence = self._confidence_bucket(confidence)

        # Step 10: Build the AiMatchMakingModel
        return AiMatchMakingModel(
            candidate_id=candidate.user_id,
            match_score=overall_score,
            compatibility_level=compatibility_level,
            is_match=is_match,
            match_status=match_status,
            criterion_scores=criterion_scores,
            criterion_matches=criterion_matches,
            matched_preferences=matched,
            partial_matches=partial,
            mismatched_preferences=mismatched,
            deal_breakers_violated=deal_breakers_violated,
            hard_constraints_passed=hard_constraints_passed,
            failed_hard_constraints=failed_constraints,
            match_reasons=match_reasons,
            concerns=concerns,
            recommendations=recommendations,
            confidence_score=confidence,
            model_confidence=model_confidence,
            data_completeness=data_completeness,
        )

    def _confidence_bucket(self, confidence: int) -> ModelConfidence:
        """Map a numeric confidence to the low/med/high bucket the document asks for."""
        if confidence >= self.config.confidence_high_threshold:
            return ModelConfidence.HIGH
        if confidence >= self.config.confidence_medium_threshold:
            return ModelConfidence.MEDIUM
        return ModelConfidence.LOW

    def _determine_compatibility_level(self, score: float) -> CompatibilityLevel:
        """Map score to compatibility level."""
        if score >= self.config.high_compatibility_threshold:
            return CompatibilityLevel.VERY_HIGH
        elif score >= self.config.match_threshold:
            return CompatibilityLevel.HIGH
        elif score >= self.config.medium_compatibility_threshold:
            return CompatibilityLevel.MEDIUM
        elif score >= self.config.low_compatibility_threshold:
            return CompatibilityLevel.LOW
        elif score > 0:
            return CompatibilityLevel.VERY_LOW
        else:
            return CompatibilityLevel.NONE

    def _determine_match_status(
        self,
        score: float,
        hard_constraints_passed: bool,
        deal_breakers_violated: List[str],
    ) -> MatchStatus:
        """Determine detailed match status."""
        if deal_breakers_violated:
            return MatchStatus.REJECTED
        if not hard_constraints_passed:
            return MatchStatus.REJECTED
        if score >= self.config.match_threshold:
            return MatchStatus.MATCH
        elif score >= self.config.medium_compatibility_threshold:
            return MatchStatus.PARTIAL_MATCH
        else:
            return MatchStatus.NO_MATCH

    def _categorize_criteria(
        self, criteria: List[CriterionMatch]
    ) -> Tuple[List[str], List[str], List[str]]:
        """Categorize criteria into matched, partial, mismatched."""
        matched = []
        partial = []
        mismatched = []

        for c in criteria:
            label = c.criterion.replace("_", " ").title()
            if c.status == MatchStatus.MATCH:
                matched.append(label)
            elif c.status == MatchStatus.PARTIAL_MATCH:
                partial.append(label)
            elif c.status in (MatchStatus.NO_MATCH, MatchStatus.REJECTED):
                mismatched.append(label)

        return matched, partial, mismatched

    def _generate_match_reasons(
        self,
        criteria: List[CriterionMatch],
        hard_constraints_passed: bool,
        deal_breakers: List[str],
    ) -> List[str]:
        """Generate human-readable reasons for the match quality."""
        reasons = []

        if deal_breakers:
            reasons.append(
                f"Deal breakers violated: {', '.join(deal_breakers)}"
            )
            return reasons

        if not hard_constraints_passed:
            reasons.append("Hard constraints not satisfied")
            return reasons

        # Add top reasons from high-scoring criteria
        for c in sorted(criteria, key=lambda x: x.score, reverse=True):
            if c.status == MatchStatus.MATCH and c.score >= 80:
                reasons.append(c.reason)

        if not reasons:
            for c in sorted(criteria, key=lambda x: x.score, reverse=True):
                if c.status == MatchStatus.PARTIAL_MATCH:
                    reasons.append(c.reason)
                    break

        return reasons[:5]  # Limit to top 5

    def _generate_concerns(
        self,
        criteria: List[CriterionMatch],
        failed_constraints: List[str],
        deal_breakers: List[str],
    ) -> List[str]:
        """Generate concerns about the match."""
        concerns = []

        if deal_breakers:
            concerns.append("Deal breaker(s) detected")

        if failed_constraints:
            concerns.append("Mandatory preferences not met")

        for c in criteria:
            if c.status == MatchStatus.NO_MATCH and not c.is_hard_constraint:
                concerns.append(f"Mismatch on {c.criterion.replace('_', ' ')}")

        return concerns[:5]

    def _generate_recommendations(
        self,
        criteria: List[CriterionMatch],
        score: float,
        level: CompatibilityLevel,
    ) -> List[str]:
        """Generate recommendations based on the evaluation."""
        recommendations = []

        if level in (CompatibilityLevel.VERY_HIGH, CompatibilityLevel.HIGH):
            recommendations.append(
                "Strong compatibility - recommend proceeding"
            )
        elif level == CompatibilityLevel.MEDIUM:
            recommendations.append(
                "Moderate compatibility - review shared values and interests"
            )
        elif level == CompatibilityLevel.LOW:
            recommendations.append(
                "Low compatibility - significant differences in preferences"
            )

        # Specific recommendations based on weak areas
        weak_criteria = [
            c for c in criteria
            if c.status in (MatchStatus.NO_MATCH, MatchStatus.PARTIAL_MATCH)
            and c.score < 50
        ]
        if weak_criteria:
            areas = [c.criterion.replace("_", " ") for c in weak_criteria[:2]]
            recommendations.append(
                f"Consider discussing: {', '.join(areas)}"
            )

        return recommendations[:3]

    def _calculate_confidence(
        self,
        score: float,
        candidate_completeness: float,
        user_completeness: float,
        hard_constraints_passed: bool,
        criteria_count: int,
    ) -> int:
        """Calculate confidence in the assessment (0-100).

        Confidence depends on:
        - Data completeness (more data = more confidence)
        - Number of criteria evaluated
        - Whether hard constraints were evaluated
        """
        # Base confidence from data completeness
        data_factor = (candidate_completeness + user_completeness) / 2

        # More criteria = more confidence
        criteria_factor = min(100, criteria_count * 8)

        # Weighted average
        confidence = (data_factor * 0.6) + (criteria_factor * 0.4)

        # Less confident about extreme scores when the profiles are sparse
        if data_factor < 50 and (score > 85 or score < 20):
            confidence *= 0.8

        return max(0, min(100, round(confidence)))
