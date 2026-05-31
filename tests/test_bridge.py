"""Tests for coagula.bridge — Orchestrator integration bridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from coagula.bridge import OrchestratorBridge
from coagula.models import SpeckitResult, ToolCall
from tests.conftest import make_mock_run_response


class TestOrchestratorBridge:
    """``OrchestratorBridge`` behaviour."""

    @patch("coagula.bridge.SpeckitEngine")
    def test_register_and_handle_tool_call(
        self, mock_engine_cls, valid_speckit_result: SpeckitResult
    ) -> None:
        """Registering a pipeline then handling a tool call should succeed."""
        mock_instance = mock_engine_cls.return_value
        mock_instance.run.return_value = valid_speckit_result

        bridge = OrchestratorBridge()
        bridge.register_pipeline("my_pipeline")

        tc = ToolCall(
            name="my_pipeline",
            arguments={
                "data_source": "test data",
                "business_objective": "test objective",
            },
            tool_call_id="call_001",
        )
        result = bridge.handle_tool_call(tc)

        # Attribute access (typed)
        assert result.success is True
        assert result.data is not None
        assert result.data.final_decision == valid_speckit_result.final_decision
        assert result.data.confidence_score == 0.95
        assert result.error is None

        # Dict-style access (backward compat)
        assert result["success"] is True
        assert result["data"] is not None
        assert result["error"] is None

        # tool_call_id
        assert result.tool_call_id == "call_001"
        assert result["tool_call_id"] == "call_001"

        mock_instance.run.assert_called_once_with(
            data_source="test data",
            business_objective="test objective",
        )

    def test_unknown_pipeline(self) -> None:
        """An unknown pipeline should return an error."""
        bridge = OrchestratorBridge()
        tc = ToolCall(
            name="nonexistent",
            arguments={},
            tool_call_id="call_002",
        )
        result = bridge.handle_tool_call(tc)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert "Unknown pipeline" in result.error

        # Dict-style
        assert result["success"] is False
        assert "Unknown pipeline" in result["error"]

    def test_invalid_arguments(self) -> None:
        """Missing required arguments should produce an error."""
        bridge = OrchestratorBridge()
        bridge.register_pipeline("p1")

        tc = ToolCall(
            name="p1",
            arguments={"data_source": "only data"},
            tool_call_id="call_003",
        )
        result = bridge.handle_tool_call(tc)

        assert result.success is False
        assert result.error is not None
        assert "Missing required" in result.error

    def test_unregister_pipeline(self) -> None:
        """After unregistering, the pipeline should not be usable."""
        bridge = OrchestratorBridge()
        bridge.register_pipeline("tmp")
        bridge.unregister_pipeline("tmp")

        tc = ToolCall(
            name="tmp",
            arguments={},
            tool_call_id="call_004",
        )
        result = bridge.handle_tool_call(tc)

        assert result.success is False
        assert "Unknown pipeline" in result.error

    @patch("coagula.bridge.SpeckitEngine")
    def test_successful_execution(
        self, mock_engine_cls, valid_speckit_result: SpeckitResult
    ) -> None:
        """A complete success path should return a result."""
        mock_instance = mock_engine_cls.return_value
        mock_instance.run.return_value = valid_speckit_result

        bridge = OrchestratorBridge()
        bridge.register_pipeline("data_pipeline")

        tc = ToolCall(
            name="data_pipeline",
            arguments={
                "data_source": "revenue data",
                "business_objective": "profit check",
            },
            tool_call_id="call_success",
        )

        result = bridge.handle_tool_call(tc)

        assert result.success is True
        assert result.data is not None
        assert result.data.final_decision == valid_speckit_result.final_decision
        assert result.data.confidence_score == 0.95
        assert result.error is None

        # tool_call_id preserved
        assert result.tool_call_id == "call_success"

    @patch("coagula.bridge.SpeckitEngine")
    def test_execution_failure(
        self, mock_engine_cls
    ) -> None:
        """If the engine raises, the bridge returns an error."""
        mock_instance = mock_engine_cls.return_value
        from coagula.exceptions import ExecutionError
        mock_instance.run.side_effect = ExecutionError("LLM API timeout")

        bridge = OrchestratorBridge()
        bridge.register_pipeline("faulty")

        tc = ToolCall(
            name="faulty",
            arguments={
                "data_source": "x",
                "business_objective": "y",
            },
            tool_call_id="call_fail",
        )

        result = bridge.handle_tool_call(tc)

        assert result.success is False
        assert result.data is None
        assert result.error is not None
        assert "Speckit execution failed" in result.error

    def test_format_as_tool_response(self) -> None:
        """``format_as_tool_response`` should produce the standard shape."""
        formatted = OrchestratorBridge.format_as_tool_response(
            tool_call_id="call_xyz",
            content={"decision": "ok", "score": 0.9},
        )
        assert formatted["role"] == "tool"
        assert formatted["tool_call_id"] == "call_xyz"
        assert isinstance(formatted["content"], str)  # JSON string

    def test_engine_caching(self) -> None:
        """The same engine instance should be reused for the same pipeline."""
        bridge = OrchestratorBridge()
        bridge.register_pipeline("cached_pipe")

        engine1 = bridge._get_or_create_engine("cached_pipe", bridge._registry.get("cached_pipe")[1])  # noqa: SLF001
        engine2 = bridge._get_or_create_engine("cached_pipe", bridge._registry.get("cached_pipe")[1])  # noqa: SLF001
        assert engine1 is engine2

    @patch("coagula.bridge.SpeckitEngine")
    def test_custom_response_model_via_bridge(
        self, mock_engine_cls, valid_speckit_result: SpeckitResult
    ) -> None:
        """Bridge should handle custom response models correctly."""
        mock_instance = mock_engine_cls.return_value
        mock_instance.run.return_value = valid_speckit_result

        bridge = OrchestratorBridge()
        bridge.register_pipeline("custom_pipe")

        tc = ToolCall(
            name="custom_pipe",
            arguments={
                "data_source": "test",
                "business_objective": "test",
            },
            tool_call_id="call_custom",
        )

        result = bridge.handle_tool_call(tc)
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["tool_call_id"] == "call_custom"
        assert result["result"]["final_decision"] == valid_speckit_result.final_decision
