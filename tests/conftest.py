"""Shared fixtures and test data for the coagula test suite."""

from __future__ import annotations

from typing import Any

import pytest

from coagula.models import (
    SpeckitConfig,
    SpeckitResult,
    ToolCall,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_DATA_SOURCE: str = (
    "Q3 revenue: $12.4M.  Cost of goods sold: $7.1M.  "
    "Operating expenses: $3.2M.  Net income: $2.1M."
)

SAMPLE_BUSINESS_OBJECTIVE: str = (
    "Determine whether the company is profitable and calculate the "
    "net profit margin."
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_speckit_result() -> SpeckitResult:
    """Return a fully-populated, valid ``SpeckitResult``."""
    return SpeckitResult(
        context_analysis=(
            "The company reported $12.4M in revenue with $7.1M COGS, "
            "$3.2M operating expenses, and $2.1M net income."
        ),
        executed_steps=[
            "Verify that revenue exceeds total costs.",
            "Calculate net profit margin.",
        ],
        final_decision=(
            "The company is profitable with a net profit margin of 16.9%."
        ),
        confidence_score=0.95,
    )


@pytest.fixture
def valid_tool_call() -> ToolCall:
    """Return a valid ``ToolCall`` matching the default pipeline schema."""
    return ToolCall(
        name="execute_speckit_data_pipeline",
        arguments={
            "data_source": SAMPLE_DATA_SOURCE,
            "business_objective": SAMPLE_BUSINESS_OBJECTIVE,
        },
        tool_call_id="call_abc123",
    )


@pytest.fixture
def invalid_tool_call() -> ToolCall:
    """Return a ``ToolCall`` missing required arguments."""
    return ToolCall(
        name="execute_speckit_data_pipeline",
        arguments={"data_source": SAMPLE_DATA_SOURCE},
        tool_call_id="call_def456",
    )


@pytest.fixture
def default_config() -> SpeckitConfig:
    """Return a default ``SpeckitConfig``."""
    return SpeckitConfig()


@pytest.fixture
def custom_config() -> SpeckitConfig:
    """Return a ``SpeckitConfig`` with custom values."""
    return SpeckitConfig(
        provider="anthropic",
        model_id="claude-3-opus-20240229",
        max_retries=5,
        instructions=[
            "You are a financial analyst engine.",
            "Always double-check calculations.",
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_run_response(
    result: SpeckitResult,
) -> Any:
    """Create a mock "RunResponse"-like object for testing.

    Phidata's ``Agent.run()`` returns a ``RunResponse`` whose ``.content``
    is the validated Pydantic model.  This helper mimics that interface.
    """
    from types import SimpleNamespace

    return SimpleNamespace(content=result)