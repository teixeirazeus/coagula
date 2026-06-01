"""
Orchestrator integration bridge for coagula.

The :class:`OrchestratorBridge` acts as the glue between a conversational
orchestrator (e.g. Hermes, OpenClaw) and the deterministic
:class:`SpeckitEngine`.  It intercepts tool calls, routes them to the
appropriate pipeline, and formats the result back into the orchestrator's
context format.

Returns a :class:`BridgeResult` object which supports both attribute
access (``result.data.final_decision``) and dict-style access
(``result["data"]["final_decision"]``) for backward compatibility.
"""

from __future__ import annotations

import json
from typing import Any

from coagula.engine import SpeckitEngine
from coagula.exceptions import CoagulaError
from coagula.models import BridgeResult, SpeckitConfig, ToolCall
from coagula.tools import (
    SpeckitToolRegistry,
    validate_tool_arguments,
)


class OrchestratorBridge:
    """Generic adapter that bridges an orchestrator to one or more Speckit
    pipelines.

    Usage
    -----
    .. code-block:: python

        bridge = OrchestratorBridge()
        bridge.register_pipeline("data_analysis")

        # Inside the orchestrator's main loop:
        result = bridge.handle_tool_call(
            ToolCall(name=..., arguments=..., tool_call_id=...)
        )
        if result.success:
            print(result.data.final_decision)
        else:
            print(result.error)
    """

    def __init__(
        self,
        registry: SpeckitToolRegistry | None = None,
    ) -> None:
        self._registry = registry or SpeckitToolRegistry()
        self._engines: dict[str, SpeckitEngine] = {}

    # -- pipeline registration ----------------------------------------------

    def register_pipeline(
        self,
        name: str,
        schema: dict[str, Any] | None = None,
        config: SpeckitConfig | None = None,
    ) -> None:
        """Register a Speckit pipeline accessible by ``name``.

        Parameters
        ----------
        name:
            Unique pipeline identifier.
        schema:
            Tool JSON schema (defaults to the built-in schema).
        config:
            Engine configuration (defaults to ``SpeckitConfig()``).
        """
        self._registry.register(name=name, schema=schema, config=config)

    def unregister_pipeline(self, name: str) -> None:
        """Remove a previously registered pipeline."""
        self._registry.unregister(name)
        self._engines.pop(name, None)

    # -- tool-call handling -------------------------------------------------

    def handle_tool_call(
        self,
        tool_call: ToolCall,
        pipeline_name: str | None = None,
    ) -> BridgeResult:
        """Process an orchestrator tool call and return a structured result.

        This method:
        1. Looks up the pipeline by ``pipeline_name`` (defaults to the tool's
           ``name``).
        2. Validates ``tool_call.arguments`` against the pipeline schema.
        3. Executes the pipeline via :class:`SpeckitEngine`.
        4. Returns a :class:`BridgeResult`.

        The returned :class:`BridgeResult` supports both attribute access
        (``result.data.final_decision``) and dict-style access
        (``result["data"]``) for backward compatibility with existing code.

        Parameters
        ----------
        tool_call:
            The tool call from the orchestrator.
        pipeline_name:
            Explicit pipeline name.  If ``None``, uses ``tool_call.name``.

        Returns
        -------
        A :class:`BridgeResult` with either ``success=True`` and ``data``
        populated, or ``success=False`` and ``error`` populated.
        """
        name = pipeline_name or tool_call.name

        try:
            _, config, _ = self._registry.get(name)
        except KeyError:
            return BridgeResult(
                success=False,
                tool_call_id=tool_call.tool_call_id,
                error=(
                    f"Unknown pipeline '{name}'.  "
                    f"Available: {list(self._registry.list_schemas())}"
                ),
            )

        # Validate arguments
        try:
            validate_tool_arguments(tool_call)
        except CoagulaError as exc:
            return BridgeResult(
                success=False,
                tool_call_id=tool_call.tool_call_id,
                error=str(exc),
            )

        # Execute pipeline
        engine = self._get_or_create_engine(name, config)
        try:
            result = engine.run(
                data_source=tool_call.arguments.get("data_source", ""),
                business_objective=tool_call.arguments.get(
                    "business_objective", ""
                ),
            )
            return BridgeResult(
                success=True,
                tool_call_id=tool_call.tool_call_id,
                data=result,
            )
        except CoagulaError as exc:
            return BridgeResult(
                success=False,
                tool_call_id=tool_call.tool_call_id,
                error=f"Speckit execution failed: {exc}",
            )

    # -- context formatting helpers -----------------------------------------

    def chain(
        self,
        pipeline_names: list[str],
        data_source: str,
        business_objective: str,
    ) -> list[BridgeResult]:
        """Execute pipelines in sequence, passing results forward.

        Each pipeline's ``details`` dict is merged into the ``data_source``
        of the next pipeline.  This enables the Spec-Driven Development
        pattern: specify -> plan -> tasks -> implement.

        Parameters
        ----------
        pipeline_names:
            Ordered list of pipeline names to execute.
        data_source:
            Initial input for the first pipeline.
        business_objective:
            High-level goal shared across all pipelines.

        Returns
        -------
        A list of :class:`BridgeResult` objects, one per pipeline.
        All pipelines are executed even if one fails (the caller can
        inspect which step failed).
        """
        results: list[BridgeResult] = []
        current_data = data_source

        for name in pipeline_names:
            tc = ToolCall(
                name=name,
                arguments={
                    "data_source": current_data,
                    "business_objective": business_objective,
                },
                tool_call_id=f"chain_{name}_{len(results)}",
            )
            result = self.handle_tool_call(tc)
            results.append(result)

            # Pass details forward if available
            if result.success and result.data and hasattr(result.data, "details"):
                details = result.data.details
                if details:
                    current_data = (
                        f"{current_data}\n\n--- Previous step ({name}) output ---\n"
                        f"{details}"
                    )

        return results

    @staticmethod
    def format_as_tool_response(
        tool_call_id: str,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        """Format a result as a standard tool-response message.

        This is a convenience wrapper for orchestrators that expect a specific
        shape for tool responses in their message history.
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(content),
        }

    # -- internal -----------------------------------------------------------

    def _get_or_create_engine(
        self,
        name: str,
        config: SpeckitConfig,
    ) -> SpeckitEngine:
        """Return a cached or fresh engine for *name*."""
        if name not in self._engines:
            self._engines[name] = SpeckitEngine(config=config)
        return self._engines[name]
