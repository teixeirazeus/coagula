"""Tests for coagula.tools — Tool schema generation and registry."""

from __future__ import annotations

import json

import pytest

from coagula.exceptions import ValidationError
from coagula.models import SpeckitConfig, ToolCall
from coagula.tools import (
    SpeckitToolRegistry,
    get_speckit_tool_schema,
    validate_tool_arguments,
)


class TestGetSpeckitToolSchema:
    """``get_speckit_tool_schema()`` behaviour."""

    def test_returns_dict(self) -> None:
        """The result must be a dictionary."""
        schema = get_speckit_tool_schema()
        assert isinstance(schema, dict)

    def test_required_top_keys(self) -> None:
        """Schema must contain ``name``, ``description``, ``parameters``."""
        schema = get_speckit_tool_schema()
        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema

    def test_parameters_structure(self) -> None:
        """Parameters must have ``type``, ``properties``, ``required``."""
        params = get_speckit_tool_schema()["parameters"]
        assert params["type"] == "object"
        assert "data_source" in params["properties"]
        assert "business_objective" in params["properties"]
        assert params["required"] == ["data_source", "business_objective"]

    def test_returns_copy(self) -> None:
        """Each call should return a fresh copy, not a shared reference."""
        s1 = get_speckit_tool_schema()
        s2 = get_speckit_tool_schema()
        assert s1 is not s2
        assert s1 == s2


class TestValidateToolArguments:
    """``validate_tool_arguments()`` behaviour."""

    def test_passes_valid_call(self, valid_tool_call: ToolCall) -> None:
        """A valid tool call should return its arguments unchanged."""
        args = validate_tool_arguments(valid_tool_call)
        assert args == valid_tool_call.arguments

    def test_rejects_missing_required(
        self, invalid_tool_call: ToolCall
    ) -> None:
        """Missing ``business_objective`` must raise ValidationError."""
        with pytest.raises(ValidationError, match="Missing required"):
            validate_tool_arguments(invalid_tool_call)

    def test_rejects_wrong_type(self) -> None:
        """Non-string arguments for string properties must be rejected."""
        tc = ToolCall(
            name="execute_speckit_data_pipeline",
            arguments={
                "data_source": 42,  # should be a string
                "business_objective": "test",
            },
            tool_call_id="call_ghi789",
        )
        with pytest.raises(ValidationError, match="must be of type 'string'"):
            validate_tool_arguments(tc)

    def test_uses_custom_schema(self) -> None:
        """A custom schema can be provided instead of the default."""
        custom_schema = {
            "name": "custom_tool",
            "parameters": {
                "type": "object",
                "properties": {"foo": {"type": "string"}},
                "required": ["foo"],
            },
        }
        tc = ToolCall(
            name="custom_tool",
            arguments={"foo": "bar"},
            tool_call_id="call_xyz",
        )
        args = validate_tool_arguments(tc, schema=custom_schema)
        assert args == {"foo": "bar"}


class TestSpeckitToolRegistry:
    """``SpeckitToolRegistry`` behaviour."""

    def test_empty_registry(self) -> None:
        """A fresh registry should be empty."""
        reg = SpeckitToolRegistry()
        assert len(reg) == 0
        assert reg.list_schemas() == []

    def test_register_and_get(self) -> None:
        """Registering a pipeline should make it retrievable."""
        reg = SpeckitToolRegistry()
        reg.register("my_pipeline")
        schema, config, desc = reg.get("my_pipeline")
        assert schema["name"] == "execute_speckit_data_pipeline"
        assert isinstance(config, SpeckitConfig)
        assert desc == ""  # default description

    def test_register_duplicate_raises(self) -> None:
        """Registering the same name twice should raise."""
        reg = SpeckitToolRegistry()
        reg.register("dup")
        with pytest.raises(ValueError, match="already registered"):
            reg.register("dup")

    def test_get_unknown_raises(self) -> None:
        """Getting an unknown name should raise KeyError."""
        reg = SpeckitToolRegistry()
        with pytest.raises(KeyError, match="unknown"):
            reg.get("unknown")

    def test_unregister(self) -> None:
        """Unregistering should remove the pipeline."""
        reg = SpeckitToolRegistry()
        reg.register("tmp")
        assert len(reg) == 1
        reg.unregister("tmp")
        assert len(reg) == 0

    def test_unregister_unknown_raises(self) -> None:
        """Unregistering an unknown name should raise KeyError."""
        reg = SpeckitToolRegistry()
        with pytest.raises(KeyError):
            reg.unregister("nope")

    def test_list_schemas(self) -> None:
        """``list_schemas()`` should return schemas for all pipelines."""
        reg = SpeckitToolRegistry()
        reg.register("a")
        reg.register("b")
        schemas = reg.list_schemas()
        assert len(schemas) == 2
        assert all(s["name"] == "execute_speckit_data_pipeline" for s in schemas)

    def test_register_with_custom_schema_and_config(self) -> None:
        """Custom schema and config can be provided at registration."""
        custom_schema = {
            "name": "my_custom_tool",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        }
        custom_config = SpeckitConfig(provider="gemini", model_id="gemini-2.0-flash")
        reg = SpeckitToolRegistry()
        reg.register("custom", schema=custom_schema, config=custom_config)
        schema, config, desc = reg.get("custom")
        assert schema["name"] == "my_custom_tool"
        assert config.provider == "gemini"
        assert desc == ""  # default description