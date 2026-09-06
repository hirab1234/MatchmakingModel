"""
AI Matchmaking Service

Enhances deterministic matchmaking with AI reasoning.
Uses the AI provider to:
- Analyze semantic compatibility (interests, personality)
- Generate nuanced insights
- Validate and enrich the deterministic result

CRITICAL: AI never overrides hard constraints or deal breakers.
AI adds intelligence on top of deterministic business rules.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from matchmaking.ai.ai_provider import AIProvider
from matchmaking.ai.prompt_builder import PromptBuilder
from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.exceptions import AIProviderError, AIResponseValidationError
from matchmaking.models import AiMatchMakingModel
from matchmaking.schemas import PartnerPreferences, UserProfile

logger = logging.getLogger("matchmaking.ai")


class AIMatchmakingService:
    """Enhances matchmaking results with AI reasoning."""

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self.ai_provider = AIProvider(self.config)

    def enhance_match(
        self,
        user: UserProfile,
        candidate: UserProfile,
        prefs: PartnerPreferences,
        deterministic_result: AiMatchMakingModel,
    ) -> AiMatchMakingModel:
        """Enhance a deterministic result with AI insights.

        Args:
            user: The user seeking a partner.
            candidate: The candidate being evaluated.
            prefs: Partner preferences.
            deterministic_result: The result from deterministic processing.

        Returns:
            Enhanced AiMatchMakingModel with AI insights.

        Falls back to the deterministic result if AI fails.
        """
        if not self.config.ai_enabled:
            logger.info("AI disabled, returning deterministic result")
            return deterministic_result

        # Never enhance rejected candidates — hard constraints are absolute
        if deterministic_result.match_status.value == "rejected":
            logger.info(
                "Candidate rejected by hard constraints, skipping AI enhancement"
            )
            return deterministic_result

        try:
            # Build prompt
            prompt = PromptBuilder.build_matchmaking_prompt(
                user=user,
                candidate=candidate,
                prefs=prefs,
                deterministic_score=deterministic_result.match_score,
            )

            # Call AI
            ai_response = self.ai_provider.generate_structured_response(
                system_prompt=PromptBuilder.SYSTEM_PROMPT,
                user_prompt=prompt,
                response_schema=PromptBuilder.STRUCTURED_OUTPUT_SCHEMA,
            )

            # Validate AI response
            validated = self._validate_ai_response(ai_response)

            # Merge AI insights into the result
            enhanced = self._merge_insights(deterministic_result, validated)
            enhanced.ai_enhanced = True
            enhanced.ai_insights = validated

            logger.info(
                f"AI enhancement applied: relationship_potential="
                f"{validated.get('relationship_potential', 'unknown')}"
            )

            return enhanced

        except AIProviderError as e:
            logger.warning(f"AI enhancement failed, returning deterministic result: {e}")
            return deterministic_result
        except AIResponseValidationError as e:
            logger.warning(f"AI response validation failed: {e}")
            return deterministic_result
        except Exception as e:
            logger.error(f"Unexpected error in AI enhancement: {e}")
            return deterministic_result

    def _validate_ai_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize AI response."""
        if not isinstance(response, dict):
            raise AIResponseValidationError("AI response is not a dict")

        # Validate required fields
        required_fields = [
            "semantic_interests_score",
            "semantic_personality_score",
            "personality_insights",
            "interest_insights",
            "lifestyle_insights",
            "potential_challenges",
            "relationship_potential",
        ]

        for field in required_fields:
            if field not in response:
                raise AIResponseValidationError(
                    f"AI response missing required field: {field}"
                )

        # Clamp scores to 0-100
        for score_field in ["semantic_interests_score", "semantic_personality_score"]:
            val = response[score_field]
            if isinstance(val, (int, float)):
                response[score_field] = max(0, min(100, val))
            else:
                response[score_field] = 50  # Default neutral

        # Ensure lists are actually lists
        for list_field in [
            "personality_insights",
            "interest_insights",
            "lifestyle_insights",
            "potential_challenges",
        ]:
            if not isinstance(response[list_field], list):
                response[list_field] = []

        # Validate relationship_potential
        valid_potentials = ["excellent", "good", "moderate", "challenging", "poor"]
        if response["relationship_potential"] not in valid_potentials:
            response["relationship_potential"] = "moderate"

        return response

    def _merge_insights(
        self,
        base: AiMatchMakingModel,
        ai_data: Dict[str, Any],
    ) -> AiMatchMakingModel:
        """Merge AI insights into the base matchmaking model.

        AI insights are ADDED to the existing result, never replacing
        deterministic scores.
        """
        # Add AI-generated concerns and recommendations
        additional_concerns = list(ai_data.get("potential_challenges", []))
        additional_recommendations = []

        potential = ai_data.get("relationship_potential", "moderate")
        if potential == "excellent":
            additional_recommendations.append(
                "AI analysis suggests excellent relationship potential"
            )
        elif potential == "challenging":
            additional_recommendations.append(
                "AI analysis suggests some challenges to address"
            )
        elif potential == "poor":
            additional_recommendations.append(
                "AI analysis suggests significant compatibility concerns"
            )

        # Combine personality/interest insights into match reasons
        personality_insights = ai_data.get("personality_insights", [])
        interest_insights = ai_data.get("interest_insights", [])

        # Add to the data_completeness-aware confidence
        ai_confidence_boost = 0
        if ai_data.get("semantic_interests_score") is not None:
            ai_confidence_boost += 5
        if ai_data.get("semantic_personality_score") is not None:
            ai_confidence_boost += 5

        new_confidence = min(100, base.confidence_score + ai_confidence_boost)

        # Build updated model
        return base.model_copy(update={
            "concerns": base.concerns + additional_concerns,
            "recommendations": base.recommendations + additional_recommendations,
            "match_reasons": base.match_reasons + [
                f"AI: {insight}" for insight in (personality_insights + interest_insights)[:3]
            ],
            "confidence_score": new_confidence,
        })
