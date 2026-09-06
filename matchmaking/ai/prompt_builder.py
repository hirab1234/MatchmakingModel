"""
Prompt Builder

Constructs production-grade prompts for AI-enhanced matchmaking.
Prompts are designed to:
- Extract semantic compatibility insights
- Generate explainable match reasons
- Detect nuanced preference alignment
- Never override hard business rules
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from matchmaking.schemas import PartnerPreferences, UserProfile


class PromptBuilder:
    """Builds structured prompts for AI matchmaking enhancement."""

    SYSTEM_PROMPT = """You are an expert matchmaking compatibility analyst.

Your role is to analyze two profiles and a set of partner preferences,
then provide structured compatibility insights.

IMPORTANT RULES:
1. You must respond ONLY in valid JSON matching the provided schema.
2. You must NEVER override hard constraints (gender, religion, sect, marital status).
3. You must base your analysis ONLY on the data provided — never assume.
4. If data is missing, note it as "insufficient_data" rather than guessing.
5. Your insights enhance but do NOT replace deterministic scoring.
6. Focus on semantic and nuanced compatibility that simple rules cannot capture.
7. Consider cultural context appropriate for matrimonial matchmaking.
"""

    STRUCTURED_OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "semantic_interests_score": {
                "type": "number",
                "description": "Semantic similarity of interests (0-100)",
            },
            "semantic_personality_score": {
                "type": "number",
                "description": "Personality compatibility score (0-100)",
            },
            "personality_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key personality compatibility observations",
            },
            "interest_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key interest compatibility observations",
            },
            "lifestyle_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lifestyle compatibility observations",
            },
            "potential_challenges": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Potential areas of friction",
            },
            "relationship_potential": {
                "type": "string",
                "enum": ["excellent", "good", "moderate", "challenging", "poor"],
                "description": "Overall relationship potential assessment",
            },
            "additional_notes": {
                "type": "string",
                "description": "Any additional relevant observations",
            },
        },
        "required": [
            "semantic_interests_score",
            "semantic_personality_score",
            "personality_insights",
            "interest_insights",
            "lifestyle_insights",
            "potential_challenges",
            "relationship_potential",
        ],
    }

    @classmethod
    def build_matchmaking_prompt(
        cls,
        user: UserProfile,
        candidate: UserProfile,
        prefs: PartnerPreferences,
        deterministic_score: Optional[float] = None,
    ) -> str:
        """Build the user prompt for AI matchmaking analysis.

        Args:
            user: The user seeking a partner.
            candidate: The candidate being evaluated.
            prefs: Partner preferences.
            optional deterministic_score: The score already calculated deterministically.

        Returns:
            Formatted prompt string.
        """
        # Build profile summaries (strip sensitive/unnecessary data)
        user_summary = cls._profile_summary(user, "User")
        candidate_summary = cls._profile_summary(candidate, "Candidate")

        # Build preferences summary
        prefs_summary = cls._preferences_summary(prefs)

        prompt_parts = [
            "Analyze the following matchmaking scenario:",
            "",
            "## Partner Preferences",
            prefs_summary,
            "",
            "## User Profile",
            user_summary,
            "",
            "## Candidate Profile",
            candidate_summary,
            "",
        ]

        if deterministic_score is not None:
            prompt_parts.append(
                f"## Deterministic Score Already Calculated: {deterministic_score}/100"
            )
            prompt_parts.append(
                "Use this as context but provide your own semantic analysis."
            )
            prompt_parts.append("")

        prompt_parts.extend([
            "Provide your analysis as JSON with the following structure:",
            json.dumps(cls.STRUCTURED_OUTPUT_SCHEMA, indent=2),
            "",
            "Focus on:",
            "1. Semantic interest overlap (not just keyword matching)",
            "2. Personality trait compatibility",
            "3. Lifestyle alignment",
            "4. Potential relationship challenges",
            "5. Overall relationship potential",
            "",
            "Respond ONLY with valid JSON.",
        ])

        return "\n".join(prompt_parts)

    @classmethod
    def build_explanation_prompt(
        cls,
        user: UserProfile,
        candidate: UserProfile,
        prefs: PartnerPreferences,
        score: float,
        matched: List[str],
        mismatched: List[str],
    ) -> str:
        """Build a prompt for generating a human-readable match explanation."""
        prompt_parts = [
            "Generate a brief, warm, and honest explanation of this match.",
            "",
            f"Match Score: {score}/100",
            f"Matched criteria: {', '.join(matched) if matched else 'None'}",
            f"Mismatched criteria: {', '.join(mismatched) if mismatched else 'None'}",
            "",
            f"User interests: {', '.join(user.interests) if user.interests else 'Not provided'}",
            f"Candidate interests: {', '.join(candidate.interests) if candidate.interests else 'Not provided'}",
            "",
            "Provide 2-3 sentences explaining the compatibility.",
            "Be specific about shared values and areas of difference.",
            "Be respectful and culturally appropriate.",
        ]
        return "\n".join(prompt_parts)

    @classmethod
    def _profile_summary(cls, profile: UserProfile, label: str) -> str:
        """Create a readable summary of a user profile."""
        parts = []
        if profile.gender:
            parts.append(f"Gender: {profile.gender.value}")
        if profile.age:
            parts.append(f"Age: {profile.age}")
        if profile.height_cm:
            parts.append(f"Height: {profile.height_cm}cm")
        if profile.religion:
            parts.append(f"Religion: {profile.religion}")
        if profile.sect:
            parts.append(f"Sect: {profile.sect}")
        if profile.education:
            parts.append(f"Education: {profile.education.value}")
        if profile.profession:
            parts.append(f"Profession: {profile.profession}")
        if profile.marital_status:
            parts.append(f"Marital status: {profile.marital_status.value}")
        if profile.mother_tongue:
            parts.append(f"Mother tongue: {profile.mother_tongue}")
        if profile.location:
            loc_parts = []
            if profile.location.city:
                loc_parts.append(profile.location.city)
            if profile.location.country:
                loc_parts.append(profile.location.country)
            parts.append(f"Location: {', '.join(loc_parts)}")
        if profile.interests:
            parts.append(f"Interests: {', '.join(profile.interests)}")
        if profile.hobbies:
            parts.append(f"Hobbies: {', '.join(profile.hobbies)}")
        if profile.personality_traits:
            parts.append(f"Personality: {', '.join(profile.personality_traits)}")
        if profile.diet:
            parts.append(f"Diet: {profile.diet}")
        if profile.smoking is not None:
            parts.append(f"Smoking: {'Yes' if profile.smoking else 'No'}")
        if profile.drinking is not None:
            parts.append(f"Drinking: {'Yes' if profile.drinking else 'No'}")
        if profile.about_me:
            parts.append(f"About: {profile.about_me[:200]}")

        return "\n".join(f"- {p}" for p in parts) if parts else f"{label}: No data available"

    @classmethod
    def _preferences_summary(cls, prefs: PartnerPreferences) -> str:
        """Create a readable summary of partner preferences."""
        parts = []
        if prefs.gender:
            parts.append(f"Gender: {prefs.gender.value}")
        if prefs.age_range:
            age_str = f"{prefs.age_range.min or '?'}-{prefs.age_range.max or '?'}"
            parts.append(f"Age range: {age_str}")
        if prefs.height_range:
            h_str = f"{prefs.height_range.min_cm or '?'}-{prefs.height_range.max_cm or '?'}cm"
            parts.append(f"Height range: {h_str}")
        if prefs.religion:
            parts.append(f"Religion: {', '.join(prefs.religion)}")
        if prefs.sect:
            parts.append(f"Sect: {', '.join(prefs.sect)}")
        if prefs.education:
            parts.append(f"Education: {', '.join(e.value for e in prefs.education)}")
        if prefs.profession:
            parts.append(f"Profession: {', '.join(prefs.profession)}")
        if prefs.location:
            parts.append(f"Location: {', '.join(prefs.location)}")
        if prefs.country:
            parts.append(f"Country: {', '.join(prefs.country)}")
        if prefs.marital_status:
            parts.append(f"Marital status: {', '.join(m.value for m in prefs.marital_status)}")
        if prefs.mother_tongue:
            parts.append(f"Mother tongue: {', '.join(prefs.mother_tongue)}")
        if prefs.interests:
            parts.append(f"Interests: {', '.join(prefs.interests)}")
        if prefs.personality_traits:
            parts.append(f"Personality traits: {', '.join(prefs.personality_traits)}")
        if prefs.lifestyle:
            lifestyle_str = ", ".join(f"{k}={v}" for k, v in prefs.lifestyle.items())
            parts.append(f"Lifestyle: {lifestyle_str}")
        if prefs.deal_breakers:
            parts.append(f"Deal breakers: {', '.join(prefs.deal_breakers)}")
        if prefs.smoking is not None:
            parts.append(f"Smoking preference: {'No' if prefs.smoking is False else 'OK'}")
        if prefs.drinking is not None:
            parts.append(f"Drinking preference: {'No' if prefs.drinking is False else 'OK'}")

        return "\n".join(f"- {p}" for p in parts) if parts else "No preferences specified"
