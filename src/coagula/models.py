"""
Strict data contracts for coagula Speckit pipelines.

Every piece of data that flows through the system is validated by Pydantic at
the boundary.  This guarantees that the orchestrator receives well-formed
results and that the engine can rely on its inputs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SpeckitResult(BaseModel):
    """The validated output produced by a Speckit pipeline execution.

    Parameters
    ----------
    context_analysis:
        Detailed analysis of the provided input data.
    executed_steps:
        Strict list of validation steps performed according to the SOP.
    final_decision:
        Actionable conclusion based on business rules.
    confidence_score:
        Confidence level of the output, clamped to ``[0.0, 1.0]``.
    details:
        Optional free-form structured data for rich output.  Pipelines can
        put arbitrary JSON-compatible data here (e.g. schemas, tables,
        code snippets) without modifying the base model.
    """

    context_analysis: str = Field(
        ...,
        description="Detailed analysis of the provided input data.",
        min_length=1,
    )
    executed_steps: list[str] = Field(
        ...,
        description="Strict list of validation steps performed according to the SOP.",
        min_length=1,
    )
    final_decision: str = Field(
        ...,
        description="Actionable conclusion based on business rules.",
        min_length=1,
    )
    confidence_score: float = Field(
        ...,
        description="Confidence level of the output (0.0 to 1.0).",
        ge=0.0,
        le=1.0,
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional structured data for rich output.  "
            "Arbitrary JSON-compatible content per pipeline."
        ),
    )

    @field_validator("executed_steps")
    @classmethod
    def _ensure_non_empty_steps(
        cls, value: list[str]
    ) -> list[str]:
        if any(not step.strip() for step in value):
            raise ValueError("All executed steps must be non-empty strings")
        return value


class ToolCall(BaseModel):
    """Represents a tool-call payload from an orchestrator (e.g. Hermes).

    Attributes
    ----------
    name:
        The name of the tool being invoked.
    arguments:
        The raw keyword arguments for the tool (usually parsed from JSON).
    tool_call_id:
        Unique identifier for this tool call, used to correlate the response.
    """

    name: str = Field(..., description="Name of the tool being invoked.")
    arguments: dict[str, Any] = Field(
        ..., description="Keyword arguments for the tool."
    )
    tool_call_id: str = Field(
        ...,
        description="Unique identifier used to correlate the tool response.",
    )


class SpeckitConfig(BaseModel):
    """Configuration for a :class:`SpeckitEngine` instance.

    Attributes
    ----------
    provider:
        The LLM provider to use (``\"openai\"``, ``\"anthropic\"``, ``\"gemini\"``,
        or any string).  Unknown providers are resolved at runtime and raise
        ``ConfigurationError`` if the corresponding phidata extra is missing.
    model_id:
        The model identifier (e.g. ``\"gpt-4o\"``, ``\"claude-3-opus-20240229\"``).
    max_retries:
        Maximum number of internal retries on Pydantic validation failure.
    instructions:
        Custom instruction overrides for the worker agent.  If not provided,
        the engine uses a sensible default set.
    output_mode:
        Controls verbosity of the pipeline response.
    response_model:
        Custom Pydantic model class for the pipeline output.  Defaults to
        :class:`SpeckitResult`.  Set this to any ``BaseModel`` subclass to
        define a different output contract per pipeline.
    """

    provider: str = Field(
        default="openai",
        description="LLM provider to use.",
    )
    model_id: str = Field(
        default="gpt-4o",
        description="Model identifier string.",
        min_length=1,
    )
    max_retries: int = Field(
        default=3,
        description="Maximum internal retries on validation failure.",
        ge=0,
        le=10,
    )
    instructions: list[str] | None = Field(
        default=None,
        description="Custom instruction overrides for the worker agent.",
    )
    output_mode: Literal["verbose", "concise", "technical"] = Field(
        default="verbose",
        description="Controls verbosity: verbose, concise, or technical.",
    )
    response_model: type[BaseModel] | None = Field(
        default=None,
        description=(
            "Custom Pydantic model for pipeline output.  "
            "Defaults to SpeckitResult when None."
        ),
        exclude=True,
    )


class BridgeResult(BaseModel):
    """Typed result from :class:`OrchestratorBridge.handle_tool_call`.

    Supports both attribute access (``result.data.final_decision``) and
    dict-style access (``result[\"data\"][\"final_decision\"]``) via
    :meth:`__getitem__` for backward compatibility with existing code
    that expected a raw dict.

    Attributes
    ----------
    success:
        Whether the pipeline executed successfully.
    tool_call_id:
        The correlating tool call identifier.
    data:
        The validated result model (e.g. :class:`SpeckitResult` or a
        custom response model).  ``None`` when ``success`` is False.
    error:
        Error message.  ``None`` when ``success`` is True.
    """

    success: bool = Field(..., description="Whether execution succeeded.")
    tool_call_id: str = Field(
        ..., description="Tool call identifier for correlation."
    )
    data: BaseModel | None = Field(
        default=None,
        description="Validated result model on success.",
    )
    error: str | None = Field(
        default=None,
        description="Error message on failure.",
    )

    def __getitem__(self, key: str) -> Any:
        """Dict-style access for backward compatibility.

        Allows ``result[\"tool_call_id\"]`` and ``result[\"result\"]``
        (which maps to ``data``) and ``result[\"error\"]``.
        """
        if key == "result":
            if self.data is None:
                raise KeyError("No data available (pipeline failed)")
            return self.data.model_dump()
        return getattr(self, key)
