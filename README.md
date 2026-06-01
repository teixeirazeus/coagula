# Coagula

![Coagula Logo](docs/logo.png)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](#)
[![Tests](https://img.shields.io/badge/tests-65%20passing-green.svg)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](#)

**Deterministic pipeline abstraction for AI agents.**  Turn SOPs into
strictly typed, validated pipelines.  CLI + Python API.

Coagula encapsulates standard operating procedures (SOPs) — "Speckits" —
into deterministic micro-workers.  The orchestrator (Hermes, etc.) decides
*when* to run a Speckit; Coagula executes it step-by-step and returns a
validated Pydantic model.

## Features

- **Strict data contracts** — Inputs and outputs validated with Pydantic.
- **Multi-provider** — OpenAI, Anthropic, Gemini, or any OpenAI-compatible
  (DeepSeek, OpenRouter, Groq).
- **Output modes** — `verbose`, `concise`, or `technical` (programmatic).
- **Custom response models** — Any `BaseModel` subclass per pipeline.
- **Automatic retries** — Configurable retry on validation failure.
- **Async** — `await engine.arun(...)` for async orchestrators.
- **Typed BridgeResult** — `handle_tool_call()` returns a typed result
  with both attribute and dict-style access.
- **Auto-patch for OpenAI-compatible** — No manual monkey-patching needed.
- **CLI + Python API** — Run pipelines from terminal or integrate.

## Quick Start

### 1. Install

```bash
pip install coagula

# For development:
pip install -e ".[dev]"
```

### 2. Set your API key

```bash
export OPENAI_API_KEY="sk-...">

# For OpenAI-compatible providers (DeepSeek, OpenRouter, Groq):
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export OPENAI_API_KEY="sk-..."
```

### 3. Install phidata extras

```bash
pip install 'phidata[openai]'   # for OpenAI
pip install 'phidata[anthropic]' # for Anthropic
pip install 'phidata[gemini]'    # for Gemini
```

### 4. CLI usage

```bash
# Verbose mode (default) — full analysis + steps + decision
coagula --data-source "Q3 revenue: $12.4M, COGS: $7.1M" \
        --objective "Determine profitability"

# Technical mode — structured output, minimal prose
coagula -d "Define a CLI tool..." -o "Architecture plan" --mode technical --json

# Concise mode — shorter output
coagula -d "data..." -o "analyze" --mode concise

# Custom provider
coagula -p openai -m deepseek-v4-flash -d "..." -o "..." --json
```

### 5. Python API

```python
from coagula import OrchestratorBridge, ToolCall

bridge = OrchestratorBridge()
bridge.register_pipeline("data_analysis")

tool_call = ToolCall(
    name="data_analysis",
    arguments={
        "data_source": "Q3 revenue: $12.4M, COGS: $7.1M.",
        "business_objective": "Determine profitability.",
    },
    tool_call_id="call_abc123",
)

result = bridge.handle_tool_call(tool_call)

# Typed access (recommended)
if result.success:
    print(f"Decision: {result.data.final_decision}")
    print(f"Confidence: {result.data.confidence_score}")
else:
    print(f"Pipeline failed: {result.error}")

# Dict-style access (backward compatible)
sr = result["result"]  # -> model_dump()
print(sr["final_decision"])
```

## Output Modes

| Mode | Flag | Use Case | Behavior |
|------|------|----------|----------|
| `verbose` (default) | *(none)* | Human reading | Full analysis, detailed steps, long decision |
| `concise` | `--mode concise` | Quick summaries | Short analysis, 3 steps max, direct decision |
| `technical` | `--mode technical` | Programmatic use | Minimal prose, structured data in `details` field |

## Custom Response Models

Each pipeline can use a different output schema:

```python
from pydantic import BaseModel
from coagula import SpeckitEngine, SpeckitConfig

class MySchema(BaseModel):
    command: str
    args: list[str]

engine = SpeckitEngine(config=SpeckitConfig(
    response_model=MySchema,
    output_mode="technical",
))
result = engine.run(data_source="...", business_objective="...")
# result is MySchema, not SpeckitResult
print(result.command, result.args)
```

## Rich Output with details

In `technical` mode, the `details` field holds arbitrary structured data:

```python
from coagula import SpeckitEngine, SpeckitConfig

engine = SpeckitEngine(config=SpeckitConfig(
    output_mode="technical",
    instructions=[
        "Put the JSON schema in details['schema']",
        "Put the task list in details['tasks']",
    ],
))
result = engine.run(data_source="...", business_objective="...")
if result.details:
    print(result.details.get("schema"))
    print(result.details.get("tasks"))
```

## Async Execution

```python
result = await engine.arun(data_source="...", business_objective="...")
```

Returns the same model type (SpeckitResult or custom).

## Hermes / Agent Integration

```python
from coagula import OrchestratorBridge, ToolCall, get_speckit_tool_schema

# Expose the tool schema to your orchestrator
schema = get_speckit_tool_schema()

bridge = OrchestratorBridge()
bridge.register_pipeline("execute_speckit_data_pipeline")

def on_tool_call(name, arguments, tool_call_id):
    tc = ToolCall(name=name, arguments=arguments, tool_call_id=tool_call_id)
    result = bridge.handle_tool_call(tc)
    if result.success:
        return OrchestratorBridge.format_as_tool_response(
            tool_call_id=tool_call_id,
            content=result.data.model_dump(),
        )
    else:
        return {"role": "tool", "tool_call_id": tool_call_id,
                "content": f'{{"error": "{result.error}"}}'}
```

## Multi-Provider Setup

### OpenAI (default)
```bash
export OPENAI_API_KEY="sk-...```

### Anthropic
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
pip install 'phidata[anthropic]'
coagula -p anthropic -m claude-opus-4 -d "..." -o "..."
```

### OpenAI-compatible (DeepSeek, OpenRouter, Groq)
Coagula auto-detects `OPENAI_BASE_URL` and patches phidata to avoid
the unsupported `developer` role.  No manual monkey-patching needed.

```bash
export OPENAI_API_KEY="sk-....port OPENAI_BASE_URL="https://api.deepseek.com/v1"
pip install 'phidata[openai]'
coagula -p openai -m deepseek-v4-flash -d "..." -o "..."
```

**Note:** Default model_id is `gpt-4o`.  Always set `--model` or
`config.model_id` for non-OpenAI providers.

## CLI Reference

```
coagula --data-source <text> --objective <text> [options]

Options:
  -d, --data-source TEXT    Raw data to analyze (required)
  -o, --objective TEXT      Business objective / goal (required)
  -p, --provider TEXT       LLM provider (default: openai)
  -m, --model TEXT          Model ID (default: gpt-4o)
  -r, --max-retries INT     Max retries on failure (default: 3)
  --mode TEXT               Output mode: verbose, concise, technical
  --details                 Show the details field in output
  --register NAME           Register pipeline under a custom name
  -l, --list-pipelines      List registered pipelines
  --json                    Output as JSON
  -h, --help                Show this help

Environment variables:
  OPENAI_API_KEY            Required for openai provider
  ANTHROPIC_API_KEY         Required for anthropic provider
  GEMINI_API_KEY            Required for gemini provider
  OPENAI_BASE_URL           Set for OpenAI-compatible providers
```

## Configuration

```python
from coagula import SpeckitConfig, SpeckitEngine

config = SpeckitConfig(
    provider="openai",              # any provider string
    model_id="gpt-4o",              # model ID for the provider
    max_retries=3,                  # 0-10 retries on failure
    output_mode="verbose",          # verbose | concise | technical
    response_model=SpeckitResult,   # custom BaseModel subclass
    instructions=[                  # custom SOP instructions
        "1. Analyze data_source based on business_objective.",
        "2. Do not ask questions. Assume conservative defaults.",
    ],
)

engine = SpeckitEngine(config=config)
result = engine.run(data_source="...", business_objective="...")
```

## Models

```python
class SpeckitResult(BaseModel):
    context_analysis: str
    executed_steps: list[str]
    final_decision: str
    confidence_score: float       # 0.0 to 1.0
    details: dict[str, Any] | None

class SpeckitConfig(BaseModel):
    provider: str                # any string (was Literal)
    model_id: str                # default: gpt-4o
    max_retries: int             # 0-10, default 3
    instructions: list[str] | None
    output_mode: Literal["verbose", "concise", "technical"]
    response_model: type[BaseModel] | None  # default: SpeckitResult

class BridgeResult(BaseModel):
    success: bool
    tool_call_id: str
    data: BaseModel | None       # SpeckitResult or custom model
    error: str | None
```

## Error Handling

```python
from coagula.exceptions import (
    CoagulaError,          # Base — catch-all
    ValidationError,       # Bad input data
    ExecutionError,        # LLM failure
    ConfigurationError,    # Missing provider/module
    RetryExhaustedError,   # All retries exhausted
)
```

In `BridgeResult`, errors are **never raised as exceptions**.  Check
`result.success` and `result.error` instead.

## Development

```bash
make dev      # pip install -e ".[dev]"
make test     # pytest (65 tests)
make mypy     # strict type check
make ci       # all of the above
make clean    # remove caches and build artifacts
```

## Architecture

```
┌─────────────────┐     Tool Call      ┌─────────────────────┐
│   Orchestrator  │ ──────────────────> │   OrchestratorBridge │
│  (Hermes, etc.) │                     │                      │
│                 │ <────────────────── │  ┌─────────────────┐ │
└─────────────────┘   JSON result       │  │ SpeckitEngine   │ │
                                         │  │ (Phidata Agent) │ │
                                         │  └─────────────────┘ │
                                         └─────────────────────┘
```

| Module | Responsibility |
|--------|---------------|
| `models` | Pydantic contracts (SpeckitResult, BridgeResult, SpeckitConfig) |
| `engine` | Phidata execution engine with retry, async, auto-patch |
| `tools` | JSON schema generation + pipeline registry |
| `bridge` | Orchestrator integration adapter |
| `exceptions` | Type-safe error hierarchy |
| `__main__` | CLI entrypoint |

## Pitfalls

1. **phidata extras**: `pip install 'phidata[openai]'` (or anthropic/gemini).
   Coagula lazy-imports and raises `ConfigurationError` if missing.
2. **OpenAI-compatible model IDs**: Default is `gpt-4o`.  Set `--model` for
   non-OpenAI providers (e.g. `deepseek-v4-flash` for DeepSeek).
3. **Hermes schema sanitizer**: Avoid `allOf` in tool schemas.  Use
   `description` fields instead.
4. **Engine caching**: Bridge caches engines by pipeline name.  Call
   `unregister_pipeline()` before re-registering with a different config.
5. **Mypy**: Run as `python -m mypy -p coagula` (not `mypy src/coagula`).

## License

MIT
