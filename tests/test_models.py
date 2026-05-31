"""Tests for coagula.models — Pydantic data contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from coagula.models import SpeckitConfig, SpeckitResult, ToolCall


class TestSpeckitResult:
    """Validation of ``SpeckitResult``."""

    def test_valid_result(self, valid_speckit_result: SpeckitResult) -> None:
        """A fully-populated result should pass validation."""
        result = valid_speckit_result
        assert result.context_analysis
        assert len(result.executed_steps) >= 1
        assert result.final_decision
        assert 0.0 <= result.confidence_score <= 1.0

    def test_minimal_fields_required(self) -> None:
        """All fields are required; omitting any should raise."""
        with pytest.raises(ValidationError):
            SpeckitResult()  # type: ignore[call-arg]

    def test_confidence_score_ge_zero(self) -> None:
        """Negative confidence scores must be rejected."""
        with pytest.raises(ValidationError):
            SpeckitResult(
                context_analysis="test",
                executed_steps=["step 1"],
                final_decision="yes",
                confidence_score=-0.1,
            )

    def test_confidence_score_le_one(self) -> None:
        """Confidence > 1.0 must be rejected."""
        with pytest.raises(ValidationError):
            SpeckitResult(
                context_analysis="test",
                executed_steps=["step 1"],
                final_decision="yes",
                confidence_score=1.1,
            )

    def test_executed_steps_non_empty(self) -> None:
        """Every step string must be non-empty."""
        with pytest.raises(ValidationError):
            SpeckitResult(
                context_analysis="test",
                executed_steps=["step 1", ""],
                final_decision="yes",
                confidence_score=0.5,
            )

    def test_executed_steps_at_least_one(self) -> None:
        """At least one step is required."""
        with pytest.raises(ValidationError):
            SpeckitResult(
                context_analysis="test",
                executed_steps=[],
                final_decision="yes",
                confidence_score=0.5,
            )

    def test_context_analysis_non_empty(self) -> None:
        """context_analysis must have at least 1 character."""
        with pytest.raises(ValidationError):
            SpeckitResult(
                context_analysis="",
                executed_steps=["step 1"],
                final_decision="yes",
                confidence_score=0.5,
            )

    def test_final_decision_non_empty(self) -> None:
        """final_decision must have at least 1 character."""
        with pytest.raises(ValidationError):
            SpeckitResult(
                context_analysis="test",
                executed_steps=["step 1"],
                final_decision="",
                confidence_score=0.5,
            )

    def test_model_dump_roundtrip(
        self, valid_speckit_result: SpeckitResult
    ) -> None:
        """``model_dump()`` -> re-construct should produce the same object."""
        data = valid_speckit_result.model_dump()
        restored = SpeckitResult(**data)
        assert restored == valid_speckit_result


class TestToolCall:
    """Validation of ``ToolCall``."""

    def test_valid_tool_call(self, valid_tool_call: ToolCall) -> None:
        """A fully-populated ToolCall should pass."""
        tc = valid_tool_call
        assert tc.name == "execute_speckit_data_pipeline"
        assert "data_source" in tc.arguments
        assert "business_objective" in tc.arguments
        assert tc.tool_call_id == "call_abc123"

    def test_missing_arguments(self) -> None:
        """``arguments`` is required."""
        with pytest.raises(ValidationError):
            ToolCall(  # type: ignore[call-arg]
                name="test", tool_call_id="call_1"
            )


class TestSpeckitConfig:
    """Validation of ``SpeckitConfig``."""

    def test_default_config(self, default_config: SpeckitConfig) -> None:
        """Defaults should be sensible."""
        cfg = default_config
        assert cfg.provider == "openai"
        assert cfg.model_id == "gpt-4o"
        assert cfg.max_retries == 3
        assert cfg.instructions is None

    def test_custom_config(self, custom_config: SpeckitConfig) -> None:
        """Custom values should be stored correctly."""
        cfg = custom_config
        assert cfg.provider == "anthropic"
        assert cfg.model_id == "claude-3-opus-20240229"
        assert cfg.max_retries == 5
        assert cfg.instructions is not None
        assert len(cfg.instructions) == 2

    def test_any_provider_string(self) -> None:
        """Provider is now a string — any value is accepted at construction."""
        cfg = SpeckitConfig(provider="ollama")
        assert cfg.provider == "ollama"

    def test_max_retries_bounds(self) -> None:
        """max_retries must be between 0 and 10."""
        with pytest.raises(ValidationError):
            SpeckitConfig(max_retries=15)
        with pytest.raises(ValidationError):
            SpeckitConfig(max_retries=-1)
        # Boundary values should work
        cfg_0 = SpeckitConfig(max_retries=0)
        assert cfg_0.max_retries == 0
        cfg_10 = SpeckitConfig(max_retries=10)
        assert cfg_10.max_retries == 10


class TestSpeckitResultDetails:
    """``details`` field on SpeckitResult."""

    def test_details_default_none(
        self, valid_speckit_result: SpeckitResult
    ) -> None:
        """``details`` should be None by default."""
        assert valid_speckit_result.details is None

    def test_details_with_data(self) -> None:
        """``details`` can hold arbitrary structured data."""
        result = SpeckitResult(
            context_analysis="test",
            executed_steps=["step 1"],
            final_decision="yes",
            confidence_score=0.9,
            details={"schema": {"type": "object"}, "tasks": ["a", "b"]},
        )
        assert result.details is not None
        assert result.details["schema"]["type"] == "object"
        assert result.details["tasks"] == ["a", "b"]

    def test_details_model_dump_roundtrip(self) -> None:
        """``details`` survives model_dump -> recreate."""
        result = SpeckitResult(
            context_analysis="test",
            executed_steps=["step 1"],
            final_decision="yes",
            confidence_score=0.9,
            details={"key": "value", "nested": [1, 2, 3]},
        )
        data = result.model_dump()
        restored = SpeckitResult(**data)
        assert restored.details == {"key": "value", "nested": [1, 2, 3]}


class TestSpeckitConfigOutputMode:
    """``output_mode`` field on SpeckitConfig."""

    def test_default_mode(self) -> None:
        """Default output_mode should be 'verbose'."""
        cfg = SpeckitConfig()
        assert cfg.output_mode == "verbose"

    def test_concise_mode(self) -> None:
        """Concise mode should be accepted."""
        cfg = SpeckitConfig(output_mode="concise")
        assert cfg.output_mode == "concise"

    def test_technical_mode(self) -> None:
        """Technical mode should be accepted."""
        cfg = SpeckitConfig(output_mode="technical")
        assert cfg.output_mode == "technical"

    def test_invalid_mode_raises(self) -> None:
        """Invalid output_mode should raise."""
        with pytest.raises(ValidationError):
            SpeckitConfig(output_mode="invalid")  # type: ignore[arg-type]


class TestSpeckitConfigCustomResponseModel:
    """Custom ``response_model`` on SpeckitConfig."""

    def test_default_response_model(self) -> None:
        """Default response_model should be None (uses SpeckitResult fallback)."""
        cfg = SpeckitConfig()
        assert cfg.response_model is None

    def test_custom_response_model(self) -> None:
        """A custom Pydantic model should be accepted."""
        from pydantic import BaseModel

        class CustomResult(BaseModel):
            answer: str
            score: float

        cfg = SpeckitConfig(response_model=CustomResult)
        assert cfg.response_model is CustomResult

    def test_custom_model_excluded_from_dump(self) -> None:
        """Custom model in config does not appear in model_dump()."""
        from pydantic import BaseModel

        class CustomResult(BaseModel):
            command: str
            args: list[str]

        cfg = SpeckitConfig(response_model=CustomResult)
        data = cfg.model_dump()
        assert "response_model" not in data
        # Recreating without response_model gives None (runtime default)
        restored = SpeckitConfig(**data)
        assert restored.response_model is None

class TestBridgeResult:
    """``BridgeResult`` model."""

    def test_success_result(self, valid_speckit_result: SpeckitResult) -> None:
        """Success path should populate data, not error."""
        from coagula.models import BridgeResult

        br = BridgeResult(
            success=True,
            tool_call_id="call_001",
            data=valid_speckit_result,
        )
        assert br.success is True
        assert br.data is not None
        assert br.data.final_decision == valid_speckit_result.final_decision
        assert br.error is None

        # Dict-style access (backward compat)
        assert br["success"] is True
        assert br["result"]["final_decision"] == valid_speckit_result.final_decision
        # data is a BaseModel, not a dict — use attribute access on data
        assert br["data"].final_decision == valid_speckit_result.final_decision

    def test_error_result(self) -> None:
        """Error path should populate error, not data."""
        from coagula.models import BridgeResult

        br = BridgeResult(
            success=False,
            tool_call_id="call_002",
            error="Something broke",
        )
        assert br.success is False
        assert br.data is None
        assert br.error == "Something broke"

        # Dict-style access
        assert br["error"] == "Something broke"
        assert br["data"] is None