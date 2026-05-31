"""
coagula — Deterministic Speckit pipeline abstraction for AI agent integration.

Coagula encapsulates standard operating procedures (SOPs) — "Speckits" — into
strictly typed, deterministic micro-workers.  It follows a Supervisor-Worker
design pattern:

- The **orchestrator** (e.g. Hermes, OpenClaw) handles natural-language
  interaction and decides *when* to trigger a Speckit.
- The **coagula engine** takes over execution, forcing the underlying LLM to
  follow the SOP step-by-step and returning a strongly-typed result.

Key modules
-----------
- ``models`` — Pydantic data contracts (SpeckitResult, ToolCall, SpeckitConfig)
- ``engine`` — Deterministic Phidata-based execution engine
- ``tools`` — Tool schema generation and registry
- ``bridge`` — Orchestrator integration adapters
- ``exceptions`` — Type-safe error hierarchy
"""

from coagula.models import SpeckitResult, ToolCall, SpeckitConfig, BridgeResult
from coagula.engine import SpeckitEngine
from coagula.tools import SpeckitToolRegistry, get_speckit_tool_schema
from coagula.bridge import OrchestratorBridge
from coagula.exceptions import (
    CoagulaError,
    ValidationError,
    ExecutionError,
    ConfigurationError,
    RetryExhaustedError,
)

__all__ = [
    "SpeckitResult",
    "ToolCall",
    "SpeckitConfig",
    "BridgeResult",
    "SpeckitEngine",
    "SpeckitToolRegistry",
    "get_speckit_tool_schema",
    "OrchestratorBridge",
    "CoagulaError",
    "ValidationError",
    "ExecutionError",
    "ConfigurationError",
    "RetryExhaustedError",
]