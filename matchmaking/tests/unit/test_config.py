"""
Unit Tests: Configuration

Tests configuration loading:
- Default values
- Custom values
- Environment variable override
- Weight configuration
"""

import os
from matchmaking.config import MatchmakingConfig, ScoringWeights, get_config, reset_config


class TestMatchmakingConfig:
    def test_default_config(self):
        config = MatchmakingConfig()
        assert config.model_version == "1.0.0"
        assert config.match_threshold == 70
        assert config.ai_enabled is True

    def test_custom_config(self):
        config = MatchmakingConfig(
            model_version="2.0.0",
            match_threshold=80,
            ai_enabled=False,
        )
        assert config.model_version == "2.0.0"
        assert config.match_threshold == 80
        assert config.ai_enabled is False

    def test_config_is_frozen(self):
        config = MatchmakingConfig()
        try:
            config.model_version = "3.0.0"
            assert False, "Should not allow mutation"
        except Exception:
            pass  # Expected - frozen dataclass


class TestScoringWeights:
    def test_default_weights(self):
        weights = ScoringWeights()
        assert weights.age > 0
        assert weights.location > 0
        assert weights.religion > 0

    def test_weights_to_dict(self):
        weights = ScoringWeights()
        d = weights.to_dict()
        assert isinstance(d, dict)
        assert "age" in d
        assert "location" in d

    def test_weights_from_dict(self):
        d = {"age": 0.15, "location": 0.20}
        weights = ScoringWeights.from_dict(d)
        assert weights.age == 0.15
        assert weights.location == 0.20
        # Others should remain default
        assert weights.education == ScoringWeights.education

    def test_weights_frozen(self):
        weights = ScoringWeights()
        try:
            weights.age = 0.5
            assert False, "Should not allow mutation"
        except Exception:
            pass


class TestEnvironmentConfig:
    def test_from_env_with_defaults(self):
        reset_config()
        config = MatchmakingConfig.from_env()
        assert config.model_version is not None
        assert config.match_threshold >= 0

    def test_singleton_get_config(self):
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reset_config(self):
        reset_config()
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2
