"""Tests for coagula.engine — the SpeckitEngine."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from coagula.engine import SpeckitEngine
from coagula.exceptions import (
    ConfigurationError,
    RetryExhaustedError,
)
from coagula.models import SpeckitConfig, SpeckitResult
from tests.conftest import make_mock_run_response


class MockModel:
    """Fake Phidata model class — accepts ``id`` kwarg like real models."""

    def __init__(self, id: str) -> None:
        self.id = id


class TestSpeckitEngineConstruction:
    """Engine instantiation."""

    def test_default_config(self) -> None:
        """Engine should use a default ``SpeckitConfig`` when none given."""
        engine = SpeckitEngine()
        assert engine.config.provider == "openai"

    def test_custom_config(self, custom_config: SpeckitConfig) -> None:
        """Engine should store the provided config."""
        engine = SpeckitEngine(config=custom_config)
        assert engine.config.provider == "anthropic"

    def test_config_property(self) -> None:
        """``.config`` property should return the config."""
        config = SpeckitConfig(max_retries=0)
        engine = SpeckitEngine(config=config)
        assert engine.config.max_retries == 0

    def test_unsupported_provider_raises(self) -> None:
        """Building an agent with an unsupported provider should raise.

        Provider is a free string now, but the engine still validates
        it at runtime by attempting to import the phidata module.
        """
        engine = SpeckitEngine(config=SpeckitConfig(provider="nonexistent"))
        with pytest.raises(ConfigurationError):
            engine.run(data_source="x", business_objective="y")


class TestSpeckitEngineRun:
    """Engine execution behaviour (with mocked Phidata Agent)."""

    def test_successful_run(
        self, valid_speckit_result: SpeckitResult
    ) -> None:
        """A successful run should return a ``SpeckitResult``."""
        with (
            patch("coagula.engine._get_agent_class") as mock_get_agent,
            patch("coagula.engine._get_openai_chat") as mock_get_openai,
        ):
            mock_get_openai.return_value = MockModel
            mock_agent_instance = mock_get_agent.return_value.return_value
            mock_agent_instance.run.return_value = make_mock_run_response(
                valid_speckit_result
            )

            engine = SpeckitEngine(config=SpeckitConfig(max_retries=1))
            result = engine.run(
                data_source="test data",
                business_objective="test objective",
            )

        assert isinstance(result, SpeckitResult)
        assert result.final_decision == valid_speckit_result.final_decision
        assert result.confidence_score == 0.95
        mock_agent_instance.run.assert_called_once()

    def test_retry_on_failure(
        self, valid_speckit_result: SpeckitResult
    ) -> None:
        """Engine should retry on validation failure and succeed on retry."""
        with (
            patch("coagula.engine._get_agent_class") as mock_get_agent,
            patch("coagula.engine._get_openai_chat") as mock_get_openai,
        ):
            mock_get_openai.return_value = MockModel
            mock_agent_instance = mock_get_agent.return_value.return_value

            mock_agent_instance.run.side_effect = [
                ValueError("LLM output not valid"),
                make_mock_run_response(valid_speckit_result),
            ]

            engine = SpeckitEngine(config=SpeckitConfig(max_retries=2))
            result = engine.run(
                data_source="test data",
                business_objective="test objective",
            )

        assert isinstance(result, SpeckitResult)
        assert mock_agent_instance.run.call_count == 2

    def test_exhaust_retries(self) -> None:
        """Engine should raise RetryExhaustedError when all retries fail."""
        with (
            patch("coagula.engine._get_agent_class") as mock_get_agent,
            patch("coagula.engine._get_openai_chat") as mock_get_openai,
        ):
            mock_get_openai.return_value = MockModel
            mock_agent_instance = mock_get_agent.return_value.return_value
            mock_agent_instance.run.side_effect = ValueError("Persistent error")

            engine = SpeckitEngine(config=SpeckitConfig(max_retries=2))
            with pytest.raises(
                RetryExhaustedError, match="failed after 2 retries"
            ):
                engine.run(
                    data_source="test data",
                    business_objective="test objective",
                )

            assert mock_agent_instance.run.call_count == 3

    def test_run_with_zero_retries(
        self, valid_speckit_result: SpeckitResult
    ) -> None:
        """With max_retries=0, a single failure should raise immediately."""
        with (
            patch("coagula.engine._get_agent_class") as mock_get_agent,
            patch("coagula.engine._get_openai_chat") as mock_get_openai,
        ):
            mock_get_openai.return_value = MockModel
            mock_agent_instance = mock_get_agent.return_value.return_value
            mock_agent_instance.run.side_effect = RuntimeError("Immediate failure")

            engine = SpeckitEngine(config=SpeckitConfig(max_retries=0))
            with pytest.raises(RetryExhaustedError):
                engine.run(
                    data_source="test data",
                    business_objective="test objective",
                )

            assert mock_agent_instance.run.call_count == 1

    def test_non_speckit_result_content(self) -> None:
        """If ``.content`` is not a SpeckitResult, raise ExecutionError."""
        with (
            patch("coagula.engine._get_agent_class") as mock_get_agent,
            patch("coagula.engine._get_openai_chat") as mock_get_openai,
        ):
            mock_get_openai.return_value = MockModel
            mock_agent_instance = mock_get_agent.return_value.return_value
            mock_agent_instance.run.return_value = SimpleNamespace(
                content={"some": "dict"}
            )

            engine = SpeckitEngine(config=SpeckitConfig(max_retries=1))
            with pytest.raises(RetryExhaustedError):
                engine.run(
                    data_source="test data",
                    business_objective="test objective",
                )

    def test_custom_response_model(self) -> None:
        """Using a custom response_model should work and return that model."""
        from pydantic import BaseModel

        class CustomResult(BaseModel):
            answer: str
            score: int

        custom_result = CustomResult(answer="yes", score=42)

        with (
            patch("coagula.engine._get_agent_class") as mock_get_agent,
            patch("coagula.engine._get_openai_chat") as mock_get_openai,
        ):
            mock_get_openai.return_value = MockModel
            mock_agent_instance = mock_get_agent.return_value.return_value
            mock_agent_instance.run.return_value = SimpleNamespace(
                content=custom_result
            )

            engine = SpeckitEngine(
                config=SpeckitConfig(
                    max_retries=1,
                    response_model=CustomResult,
                )
            )
            result = engine.run(
                data_source="test data",
                business_objective="test objective",
            )

        assert isinstance(result, CustomResult)
        assert result.answer == "yes"
        assert result.score == 42


class TestPatchForOpenAICompatible:
    """``_patch_for_openai_compatible`` behaviour."""

    def test_no_patch_when_openai_direct(self) -> None:
        """No patching when OPENAI_BASE_URL is not set."""
        # Ensure env is clean
        if "OPENAI_BASE_URL" in __import__("os").environ:
            __import__("os").environ.pop("OPENAI_BASE_URL")

        from coagula.engine import _patch_for_openai_compatible

        class MockModel:
            @staticmethod
            def format_message(self, message, map_system_to_developer=True):
                return {"role": "developer" if map_system_to_developer else "system"}

        patched = _patch_for_openai_compatible(MockModel)
        result = patched.format_message(None, "hello")
        # No env -> no patch -> developer role kept
        assert result["role"] == "developer"

    def test_patches_when_deepseek_url(self, monkeypatch) -> None:
        """Patching should force system role when OPENAI_BASE_URL is set."""
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")

        from coagula.engine import _patch_for_openai_compatible

        class MockModel:
            @staticmethod
            def format_message(self, message, map_system_to_developer=True):
                return {"role": "developer" if map_system_to_developer else "system"}

        patched = _patch_for_openai_compatible(MockModel)
        result = patched.format_message(None, "hello")
        assert result["role"] == "system"  # forced by patch

    def test_no_patch_for_openai_com(self, monkeypatch) -> None:
        """No patching when OPENAI_BASE_URL points to api.openai.com."""
        monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        from coagula.engine import _patch_for_openai_compatible

        class MockModel:
            @staticmethod
            def format_message(self, message, map_system_to_developer=True):
                return {"role": "developer" if map_system_to_developer else "system"}

        patched = _patch_for_openai_compatible(MockModel)
        result = patched.format_message(None, "hello")
        assert result["role"] == "developer"  # no patch
