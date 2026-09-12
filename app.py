"""
AI Matchmaking Model - FastAPI Application

2 APIs:
  1. POST /users       → Backend sends all user data (profiles + partner preferences)
  2. GET  /match/{id}  → Run matchmaking for a user, return ranked matches
  GET  /health        → Health check
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from matchmaking import __model_version__
from matchmaking.config import get_config
from matchmaking.exceptions import InputValidationError, MatchmakingError
from matchmaking.processing.mutual_engine import MutualMatchingEngine
from matchmaking.processing.normalizer import Normalizer
from matchmaking.processing.validator import Validator
from matchmaking.schemas import (
    MatchmakingResponse,
    MutualMatchRequest,
    MutualMatchResponse,
    PartnerPreferences,
    UserProfile,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("matchmaking.api")


# ---------------------------------------------------------------------------
# In-memory user store  (backend pushes data, model reads it)
# ---------------------------------------------------------------------------

_users: Dict[str, UserProfile] = {}  # user_id → profile

# Deployment settings (env-driven, safe defaults)
_API_KEY = os.environ.get("MATCHMAKING_API_KEY", "").strip()
_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("MATCHMAKING_ALLOWED_ORIGINS", "*").split(",") if o.strip()
] or ["*"]
_config = get_config()
_mutual_engine = MutualMatchingEngine(_config)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Matchmaking Model",
    description=(
        "2 APIs:\n"
        "1) POST /users — backend sends all user data\n"
        "2) GET  /match/{user_id} — matchmaking for one user"
    ),
    version=__model_version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    # Credentials cannot be combined with a "*" origin (browsers reject it).
    allow_credentials=_ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Optional API-key guard
#
# Disabled by default (MATCHMAKING_API_KEY unset) so existing backend calls
# keep working. Set the env var and send `X-API-Key: <key>` to lock the API
# down; the health check stays open so uptime probes keep working.
# ---------------------------------------------------------------------------


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if not _API_KEY:
        return
    if x_api_key != _API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"error": True, "code": "UNAUTHORIZED", "message": "Invalid or missing X-API-Key header."},
        )


# ---------------------------------------------------------------------------
# Request / Response models (local to app, not in schemas package)
# ---------------------------------------------------------------------------


class UsersUploadRequest(BaseModel):
    """Backend sends ALL users in one call."""
    users: List[UserProfile] = Field(..., min_length=2, description="All users (logged-in + others)")


class UsersUploadResponse(BaseModel):
    success: bool = True
    total_users: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# API 1: POST /users  — backend pushes all user data
# ---------------------------------------------------------------------------


@app.post("/users", response_model=UsersUploadResponse, dependencies=[Depends(require_api_key)])
async def upload_users(request: UsersUploadRequest):
    """Backend sends ALL user data to the matchmaking model.

    Send every user (logged-in users + other users) with their profiles
    and partner_preferences. The model stores them in memory.

    Call this every time the backend wants to refresh the user pool.
    """
    global _users
    _users.clear()

    for u in request.users:
        normalized = Normalizer.normalize_user_profile(u)
        _users[normalized.user_id] = normalized

    logger.info(f"Users uploaded: {len(_users)} users")

    return UsersUploadResponse(
        success=True,
        total_users=len(_users),
        message=f"Stored {len(_users)} users successfully",
    )


# ---------------------------------------------------------------------------
# API 2: GET /match/{user_id}  — matchmaking for one user
# ---------------------------------------------------------------------------


@app.get("/match/{user_id}", response_model=MutualMatchResponse, dependencies=[Depends(require_api_key)])
async def get_matches(
    user_id: str,
    top_n: Optional[int] = Query(None, ge=1, description="Return only top N matches"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Drop results below this score"),
):
    """Run matchmaking for a logged-in user against all other users.

    The model:
    1. Finds the user by user_id
    2. Gets their partner_preferences from their profile
    3. Scores them against EVERY other user (both directions)
    4. Returns ranked results (best first)
    """
    start_time = time.time()

    # 1. Find the user
    user = _users.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"error": True, "code": "USER_NOT_FOUND", "message": f"User '{user_id}' not found. Call POST /users first."},
        )

    # 2. Get their partner preferences
    user_prefs = user.partner_preferences
    if user_prefs is None:
        raise HTTPException(
            status_code=422,
            detail={"error": True, "code": "NO_PREFERENCES", "message": f"User '{user_id}' has no partner_preferences in their profile."},
        )

    # 3. Get all OTHER users as candidates
    candidates = [u for u in _users.values() if u.user_id != user_id]
    if not candidates:
        elapsed_ms = (time.time() - start_time) * 1000
        return MutualMatchResponse(
            success=True,
            model_version=_config.model_version,
            request_id=str(uuid.uuid4()),
            processing_time_ms=round(elapsed_ms, 2),
            logged_in_user_id=user_id,
            total_users_evaluated=0,
            total_matches=0,
            matches=[],
            warnings=["No other users available for matching"],
        )

    # 4. Run mutual matching
    try:
        results, warnings = _mutual_engine.match_against_list(
            user=user,
            user_prefs=user_prefs,
            candidates=candidates,
            top_n=top_n,
            min_score=min_score,
        )

        elapsed_ms = (time.time() - start_time) * 1000
        for r in results:
            r.processing_time_ms = round(elapsed_ms, 2)

        logger.info(
            f"Match for {user_id}: {len(results)} evaluated, "
            f"{sum(1 for r in results if r.is_match)} matches, {elapsed_ms:.0f}ms"
        )

        return MutualMatchResponse(
            success=True,
            model_version=_config.model_version,
            request_id=str(uuid.uuid4()),
            processing_time_ms=round(elapsed_ms, 2),
            logged_in_user_id=user_id,
            total_users_evaluated=len(candidates),
            total_matches=sum(1 for r in results if r.is_match),
            matches=results,
            warnings=warnings,
        )

    except Exception as e:
        logger.error(f"Match error for {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": True, "code": "MATCH_ERROR", "message": str(e)},
        )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    """Service banner — confirms the API is live."""
    return {
        "service": "AI Matchmaking Model",
        "model_version": _config.model_version,
        "status": "live",
        "docs": "/docs",
        "endpoints": {"upload_users": "POST /users", "match": "GET /match/{user_id}", "health": "GET /health"},
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_version": _config.model_version,
        "users_loaded": len(_users),
    }
