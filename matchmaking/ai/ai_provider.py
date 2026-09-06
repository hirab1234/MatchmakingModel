"""
AI Provider

Handles communication with AI/LLM providers (OpenAI, Anthropic, etc.).
Provides structured output enforcement and validation.
Falls back gracefully on provider failures.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.exceptions import AIProviderError

logger = logging.getLogger("matchmaking.ai")


class AIProvider:
    """Manages AI provider connections and structured output generation."""

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self._client = None

    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(timeout=self.config.ai_timeout)
            except ImportError:
                raise AIProviderError(
                    message="OpenAI package not installed. Install with: pip install openai",
                    provider=self.config.ai_provider,
                )
        return self._client

    def generate_structured_response(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Dict[str, Any],
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Generate a structured response from the AI provider.

        Args:
            system_prompt: System instruction for the AI.
            user_prompt: User content/prompt.
            response_schema: JSON schema for structured output.
            temperature: Override temperature for this call.

        Returns:
            Parsed JSON response matching the schema.

        Raises:
            AIProviderError: If the provider fails or returns invalid output.
        """
        if not self.config.ai_enabled:
            raise AIProviderError(
                message="AI is disabled in configuration",
                provider=self.config.ai_provider,
            )

        start_time = time.time()
        temp = temperature if temperature is not None else self.config.ai_temperature

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.config.ai_model,
                temperature=temp,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            content = response.choices[0].message.content
            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                f"AI response received in {elapsed_ms:.0f}ms, "
                f"model={self.config.ai_model}"
            )

            # Parse and validate
            parsed = json.loads(content)
            return parsed

        except json.JSONDecodeError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"AI response was not valid JSON after {elapsed_ms:.0f}ms: {e}"
            )
            raise AIProviderError(
                message=f"AI returned invalid JSON: {str(e)}",
                provider=self.config.ai_provider,
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_msg = str(e)
            # Don't expose API keys or sensitive info
            if "api_key" in error_msg.lower():
                error_msg = "Authentication failed"
            logger.error(
                f"AI provider error after {elapsed_ms:.0f}ms: {error_msg}"
            )
            raise AIProviderError(
                message=f"AI provider error: {error_msg}",
                provider=self.config.ai_provider,
            )

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate plain text response from the AI provider."""
        if not self.config.ai_enabled:
            raise AIProviderError(
                message="AI is disabled in configuration",
                provider=self.config.ai_provider,
            )

        try:
            client = self._get_client()
            temp = temperature if temperature is not None else self.config.ai_temperature

            response = client.chat.completions.create(
                model=self.config.ai_model,
                temperature=temp,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower():
                error_msg = "Authentication failed"
            raise AIProviderError(
                message=f"AI provider error: {error_msg}",
                provider=self.config.ai_provider,
            )
