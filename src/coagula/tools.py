"""
Tool schema generation and registry for coagula Speckit pipelines.

Provides utilities to generate the exact JSON tool schema that orchestrators
like Hermes and OpenClaw consume, as well as a registry for managing multiple
Speckit pipeline definitions.
"""

from __future__ import annotations

import json
from typing import Any

from coagula.exceptions import ValidationError
from coagula.models import SpeckitConfig, ToolCall


# ---------------------------------------------------------------------------
# Default tool schema   (matches the design-document spec)
# ---------------------------------------------------------------------------

_DEFAULT_TOOL_SCHEMA: dict[str, Any] = {
    "name": "execute_speckit_data_pipeline",
    "description": (
        "Executes the strict, automated Speckit data analysis SOP.  "
        "Use this tool autonomously when a user requests analysis.  "
        "DO NOT ask the user for procedural help.  Gather the required "
        "parameters and trigger this function."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "data_source": {
                "type": "string",
                "description": "Raw data, text, or context to be processed.",
            },
            "business_objective": {
                "type": "string",
                "description": "The specific goal of the analysis.",
            },
        },
        "required": ["data_source", "business_objective"],
    },
}


def get_speckit_tool_schema() -> dict[str, Any]:
    """Return a copy of the default Speckit tool JSON schema.

    Orchestrators need this schema to understand how to invoke the
    ``execute_speckit_data_pipeline`` tool.
    """
    return json.loads(json.dumps(_DEFAULT_TOOL_SCHEMA))


# ---------------------------------------------------------------------------
# Validator for tool-call arguments
# ---------------------------------------------------------------------------


def validate_tool_arguments(
    tool_call: ToolCall, schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validate that ``tool_call.arguments`` matches the tool schema.

    Parameters
    ----------
    tool_call:
        The incoming tool call from the orchestrator.
    schema:
        The tool schema to validate against.  Defaults to the built-in
        ``execute_speckit_data_pipeline`` schema.

    Returns
    -------
    The validated arguments dictionary.

    Raises
    ------
    ValidationError:
        If required keys are missing or argument types are incorrect.
    """
    resolved = schema or _DEFAULT_TOOL_SCHEMA
    required: list[str] = resolved.get("parameters", {}).get("required", [])
    properties: dict[str, Any] = resolved.get("parameters", {}).get("properties", {})

    args = tool_call.arguments

    for key in required:
        if key not in args:
            raise ValidationError(
                f"Missing required argument '{key}' in tool call "
                f"'{tool_call.name}' (id={tool_call.tool_call_id})"
            )

    for key, value in args.items():
        prop = properties.get(key)
        if prop is None:
            continue
        expected_type = prop.get("type", "string")
        # Basic type-check — orchestrators typically pass strings.
        if expected_type == "string" and not isinstance(value, str):
            raise ValidationError(
                f"Argument '{key}' must be of type '{expected_type}', "
                f"got {type(value).__name__}"
            )

    return args


# ---------------------------------------------------------------------------
# Speckit tool registry
# ---------------------------------------------------------------------------


class SpeckitToolRegistry:
    """Registry for multiple named Speckit pipeline definitions.

    Each entry maps a pipeline name to a ``(schema, config)`` pair, enabling
    an orchestrator to invoke different SOPs through the same registry.
    """

    def __init__(self) -> None:
        self._pipelines: dict[str, tuple[dict[str, Any], SpeckitConfig]] = {}

    def register(
        self,
        name: str,
        schema: dict[str, Any] | None = None,
        config: SpeckitConfig | None = None,
    ) -> None:
        """Register a Speckit pipeline.

        Parameters
        ----------
        name:
            Unique pipeline identifier.
        schema:
            Tool JSON schema.  Defaults to the built-in schema.
        config:
            Engine configuration.  Defaults to ``SpeckitConfig()``.
        """
        if name in self._pipelines:
            raise ValueError(f"A pipeline named '{name}' is already registered")
        self._pipelines[name] = (
            schema or get_speckit_tool_schema(),
            config or SpeckitConfig(),
        )

    def get(self, name: str) -> tuple[dict[str, Any], SpeckitConfig]:
        """Retrieve a registered pipeline by name.

        Raises
        ------
        KeyError:
            If ``name`` is not registered.
        """
        if name not in self._pipelines:
            raise KeyError(f"No pipeline registered under '{name}'")
        return self._pipelines[name]

    def unregister(self, name: str) -> None:
        """Remove a registered pipeline.

        Raises
        ------
        KeyError:
            If ``name`` is not registered.
        """
        if name not in self._pipelines:
            raise KeyError(f"No pipeline registered under '{name}'")
        del self._pipelines[name]

    def list_schemas(self) -> list[dict[str, Any]]:
        """Return the JSON schemas for all registered pipelines."""
        return [schema for schema, _ in self._pipelines.values()]

    def __len__(self) -> int:
        return len(self._pipelines)