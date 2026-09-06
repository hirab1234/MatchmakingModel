"""
Matchmaking Service

The main orchestration service that implements the MatchMakingAiModel.

This is the entry point that the backend calls. It orchestrates:

    Backend
        ↓
    MatchMakingAiModel (this service)
        ↓
    Processing / Matching Engine
        ↓
    AiMatchMakingModel
        ↓
    Response
        ↓
    Backend

Responsibilities:
- Receives data FROM the backend (never fetches it)
- Validates input
- Normalizes data
- Processes matching
- Optionally enhances with AI
- Returns structured response
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.exceptions import InputValidationError, MatchmakingError
from matchmaking.models import AiMatchMakingModel
from matchmaking.processing.compatibility_engine import CompatibilityEngine
from matchmaking.processing.mutual_engine import MutualMatchingEngine
from matchmaking.processing.normalizer import Normalizer
from matchmaking.processing.preference_processor import PreferenceProcessor
from matchmaking.processing.ranking_engine import RankingEngine
from matchmaking.processing.validator import Validator
from matchmaking.schemas import (
    CandidateMatchResult,
    CriterionMatch,
    MatchmakingRequest,
    MatchmakingResponse,
    MutualMatchRequest,
    MutualMatchResponse,
)

logger = logging.getLogger("matchmaking")


class MatchmakingService:
    """Production matchmaking service.

    Implements the full matchmaking pipeline:
    Input → Validate → Normalize → Process → Score → AI Enhance → Response
    """

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self.compatibility_engine = CompatibilityEngine(self.config)
        self.ranking_engine = RankingEngine(self.config)
        self.mutual_engine = MutualMatchingEngine(self.config)
        self._ai_service = None

    @property
    def ai_service(self):
        """Lazy-load AI service to avoid import issues when AI is disabled."""
        if self._ai_service is None:
            from matchmaking.ai.ai_matchmaking_service import AIMatchmakingService
            self._ai_service = AIMatchmakingService(self.config)
        return self._ai_service

    def process(self, request: MatchmakingRequest) -> MatchmakingResponse:
        """Process a matchmaking request.

        This is the main entry point. The backend calls this with
        all required data.

        Args:
            request: Validated matchmaking request from the backend.

        Returns:
            Structured matchmaking response for the backend.
        """
        start_time = time.time()

        try:
            # Step 1: Validate input
            logger.info(
                f"Processing matchmaking request: {request.request_id}"
            )
            warnings = Validator.validate_request(request)
            if warnings:
                logger.info(f"Validation warnings: {warnings}")

            # Step 2: Normalize user profile
            user = Normalizer.normalize_user_profile(request.user)

            # Step 3: Normalize preferences
            prefs = Normalizer.normalize_partner_preferences(
                request.partner_preferences
            )

            # Step 4: Process based on single candidate or multiple candidates
            if request.candidate is not None:
                return self._process_single(
                    request, user, prefs, start_time
                )
            elif request.candidates is not None:
                return self._process_multiple(
                    request, user, prefs, start_time
                )
            else:
                raise InputValidationError(
                    message="Either candidate or candidates must be provided"
                )

        except MatchmakingError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Matchmaking error for {request.request_id}: {e.message}"
            )
            return MatchmakingResponse(
                success=False,
                model_version=self.config.model_version,
                request_id=request.request_id,
                processing_time_ms=elapsed_ms,
                error=e.to_dict(),
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Unexpected error for {request.request_id}: {str(e)}"
            )
            return MatchmakingResponse(
                success=False,
                model_version=self.config.model_version,
                request_id=request.request_id,
                processing_time_ms=elapsed_ms,
                error={
                    "error": True,
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during processing",
                },
            )

    def _process_single(
        self,
        request: MatchmakingRequest,
        user,
        prefs,
        start_time: float,
    ) -> MatchmakingResponse:
        """Process a single candidate evaluation."""
        candidate = Normalizer.normalize_user_profile(request.candidate)

        # Run deterministic evaluation
        result = self.compatibility_engine.evaluate(
            user=user, candidate=candidate, prefs=prefs
        )

        # Optionally enhance with AI
        if self.config.ai_enabled:
            result = self.ai_service.enhance_match(
                user=user, candidate=candidate, prefs=prefs,
                deterministic_result=result,
            )

        elapsed_ms = (time.time() - start_time) * 1000

        # Format response
        candidate_result = self._format_result(candidate.user_id, result, elapsed_ms)

        return MatchmakingResponse(
            success=True,
            model_version=self.config.model_version,
            request_id=request.request_id,
            processing_time_ms=elapsed_ms,
            result=candidate_result,
        )

    def _process_multiple(
        self,
        request: MatchmakingRequest,
        user,
        prefs,
        start_time: float,
    ) -> MatchmakingResponse:
        """Process multiple candidates and return ranked results."""
        # Normalize all candidates
        candidates = [
            Normalizer.normalize_user_profile(c) for c in request.candidates
        ]

        # Evaluate and rank
        results = self.ranking_engine.evaluate_and_rank(
            user=user, candidates=candidates, prefs=prefs
        )

        # Optionally enhance top results with AI
        if self.config.ai_enabled:
            enhanced_results = []
            for result in results:
                # Find the matching candidate by ID
                matching_candidate = next(
                    (c for c in candidates if c.user_id == result.candidate_id),
                    None,
                )
                if matching_candidate is not None:
                    enhanced = self.ai_service.enhance_match(
                        user=user,
                        candidate=matching_candidate,
                        prefs=prefs,
                        deterministic_result=result,
                    )
                    enhanced_results.append(enhanced)
                else:
                    enhanced_results.append(result)
            results = enhanced_results

        elapsed_ms = (time.time() - start_time) * 1000

        # Format all results
        formatted_results = [
            self._format_result(r.candidate_id, r, elapsed_ms)
            for r in results
        ]

        return MatchmakingResponse(
            success=True,
            model_version=self.config.model_version,
            request_id=request.request_id,
            processing_time_ms=elapsed_ms,
            results=formatted_results,
        )

    def _format_result(
        self,
        candidate_id: str,
        model: AiMatchMakingModel,
        elapsed_ms: float,
    ) -> CandidateMatchResult:
        """Convert AiMatchMakingModel to CandidateMatchResult."""
        # Report only the criteria the user actually expressed a preference for,
        # heaviest first, keeping each criterion's own status and reason.
        criterion_matches = sorted(
            (c for c in model.criterion_matches if c.applicable),
            key=lambda c: c.weight,
            reverse=True,
        )

        return CandidateMatchResult(
            candidate_id=candidate_id,
            is_match=model.is_match,
            match_score=model.match_score,
            match_percentage=float(model.match_score),
            compatibility_level=model.compatibility_level,
            match_status=model.match_status,
            criterion_matches=criterion_matches,
            matched_preferences=model.matched_preferences,
            partial_matches=model.partial_matches,
            mismatched_preferences=model.mismatched_preferences,
            deal_breakers_violated=model.deal_breakers_violated,
            match_reasons=model.match_reasons,
            concerns=model.concerns,
            recommendations=model.recommendations,
            confidence_score=model.confidence_score,
            model_confidence=model.model_confidence,
            processing_time_ms=elapsed_ms,
            ai_enhanced=model.ai_enhanced,
        )

    # ------------------------------------------------------------------
    # Mutual (two-way) matchmaking
    # ------------------------------------------------------------------

    def process_mutual(self, request: MutualMatchRequest) -> MutualMatchResponse:
        """Match the logged-in user against a list of users, in BOTH directions.

        For every user in the list the model scores:
          1. how well that user fits the logged-in user's partner preferences,
          2. how well the logged-in user fits that user's own preferences,
        then combines the two into a single mutual compatibility percentage.

        Args:
            request: Logged-in user, their preferences, and the user list.

        Returns:
            Ranked mutual matches, highest score first.
        """
        start_time = time.time()

        try:
            logger.info(
                f"Processing mutual matchmaking request {request.request_id} "
                f"for {request.logged_in_user.user_id} against "
                f"{len(request.users)} users"
            )

            if len(request.users) > self.config.max_candidates_per_request:
                raise InputValidationError(
                    message=(
                        f"Too many users: {len(request.users)} "
                        f"(max: {self.config.max_candidates_per_request})"
                    ),
                    field="users",
                )

            warnings = Validator.validate_user_profile(
                request.logged_in_user, "logged_in_user"
            )
            warnings.extend(
                Validator.validate_preferences(request.partner_preferences)
            )

            users_without_prefs = [
                u.user_id for u in request.users if u.partner_preferences is None
            ]
            if users_without_prefs:
                warnings.append(
                    "One-way scoring only (no partner_preferences) for: "
                    + ", ".join(users_without_prefs[:10])
                )

            results, engine_warnings = self.mutual_engine.match_against_list(
                user=request.logged_in_user,
                user_prefs=request.partner_preferences,
                candidates=request.users,
                top_n=request.top_n,
                min_score=request.min_score,
                include_criterion_breakdown=request.include_criterion_breakdown,
            )
            warnings.extend(engine_warnings)

            elapsed_ms = (time.time() - start_time) * 1000
            for r in results:
                r.processing_time_ms = round(elapsed_ms, 2)

            logger.info(
                f"Request {request.request_id}: {len(results)} results, "
                f"{sum(1 for r in results if r.is_match)} matches, "
                f"{elapsed_ms:.0f}ms"
            )

            return MutualMatchResponse(
                success=True,
                model_version=self.config.model_version,
                request_id=request.request_id,
                processing_time_ms=round(elapsed_ms, 2),
                logged_in_user_id=request.logged_in_user.user_id,
                total_users_evaluated=len(request.users),
                total_matches=sum(1 for r in results if r.is_match),
                matches=results,
                warnings=warnings,
            )

        except MatchmakingError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Mutual matchmaking error for {request.request_id}: {e.message}"
            )
            return MutualMatchResponse(
                success=False,
                model_version=self.config.model_version,
                request_id=request.request_id,
                processing_time_ms=elapsed_ms,
                logged_in_user_id=request.logged_in_user.user_id,
                error=e.to_dict(),
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Unexpected error for {request.request_id}: {str(e)}",
                exc_info=True,
            )
            return MutualMatchResponse(
                success=False,
                model_version=self.config.model_version,
                request_id=request.request_id,
                processing_time_ms=elapsed_ms,
                logged_in_user_id=request.logged_in_user.user_id,
                error={
                    "error": True,
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred during processing",
                },
            )
