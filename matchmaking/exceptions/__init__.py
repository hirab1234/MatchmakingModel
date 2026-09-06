"""
Matchmaking Exception Hierarchy

All custom exceptions for the matchmaking system.
Provides structured error information without exposing internals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class MatchmakingError(Exception):
    """Base exception for all matchmaking errors."""

    def __init__(
        self,
        message: str,
        code: str = "MATCHMAKING_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class InputValidationError(MatchmakingError):
    """Raised when input data fails validation."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="INPUT_VALIDATION_ERROR",
            details={**(details or {}), "field": field},
        )


class PreferenceProcessingError(MatchmakingError):
    """Raised when preference processing fails."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="PREFERENCE_PROCESSING_ERROR",
            details=details,
        )


class ScoringError(MatchmakingError):
    """Raised when scoring computation fails."""

    def __init__(
        self,
        message: str,
        criterion: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="SCORING_ERROR",
            details={**(details or {}), "criterion": criterion},
        )


class AIProviderError(MatchmakingError):
    """Raised when the AI provider fails."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="AI_PROVIDER_ERROR",
            details={**(details or {}), "provider": provider},
        )


class AIResponseValidationError(MatchmakingError):
    """Raised when AI response doesn't match expected schema."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="AI_RESPONSE_VALIDATION_ERROR",
            details=details,
        )


class ProcessingTimeoutError(MatchmakingError):
    """Raised when processing exceeds time limit."""

    def __init__(
        self,
        message: str = "Processing timed out",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="PROCESSING_TIMEOUT",
            details=details,
        )


class CandidateRejectedError(MatchmakingError):
    """Raised when a candidate is definitively rejected by hard constraints."""

    def __init__(
        self,
        message: str,
        failed_constraints: Optional[list] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            code="CANDIDATE_REJECTED",
            details={**(details or {}), "failed_constraints": failed_constraints or []},
        )
