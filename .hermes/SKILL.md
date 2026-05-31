---
name: coagula
title: Coagula — Deterministic Speckit Pipelines
description: Encapsulate SOPs into deterministic pipelines with Pydantic + Phidata. CLI, Python API, Hermes/swarm integration. Features: rich output, technical mode, multi-provider.
category: software-development
---

# Coagula — Agent Guide

Coagula turns standard operating procedures (SOPs) into deterministic
pipelines called **Speckits**.  Use when a task has fixed steps and needs
structured output — financial analysis, data review, rule-based decisions,
architecture planning.

## Repository

/Users/zeus/Documents/codes/coagula

## CLI Quick Start

```bash
# Verbose mode (default) — full analysis + steps + decision
coagula -d "Q3 revenue: $12.4M, COGS: $7.1M" -o "Determine profitability"

# Technical mode — minimal prose, populate details field
coagula -d "requirements..." -o "Define schema" --mode technical --json

# Concise mode — shorter output
coagula -d "data..." -o "Analyze" --mode concise

# Show details field too
coagula -d "..." -o "..." --mode technical --details

# Custom provider
coagula -p anthropic -m claude-opus-4 -d "..." -o "..."

# JSON for scripting
coagula -d "..." -o "..." --json | jq '.final_decision'
```

## Python API

### Rich output with details

```python
from coagula import SpeckitEngine, SpeckitConfig

engine = SpeckitEngine(config=SpeckitConfig(
    provider="openai",
    model_id="gpt-4o",
    output_mode="technical",  # verbose | concise | technical
))

result = engine.run(
    data_source="Build a CLI tool: create, list, delete projects",
    business_objective="Define architecture, schema, and 3 tasks",
)

# Standard fields
print(f"Decision: {result.final_decision}")
print(f"Steps: {result.executed_steps}")

# Rich structured data (technical mode populates this)
if result.details:
    print(f"Schema: {result.details.get('schema')}")
    print(f"Tasks: {result.details.get('tasks')}")
```

### Bridge with custom pipeline

```python
from coagula import OrchestratorBridge, ToolCall, SpeckitConfig

bridge = OrchestratorBridge()
bridge.register_pipeline("code_review", config=SpeckitConfig(
    provider="anthropic",
    model_id="claude-opus-4",
    output_mode="technical",
    instructions=[
        "Review the source code provided in data_source.",
        "Put issues in details['issues'] as a list of dicts.",
        "Put suggestions in details['suggestions'].",
    ],
))

result = bridge.handle_tool_call(ToolCall(
    name="code_review",
    arguments={"data_source": "# full source code...", "business_objective": "Find bugs"},
    tool_call_id="review_001",
))
```

## Hermes Integration

### As a tool call

```python
from coagula import OrchestratorBridge, ToolCall, get_speckit_tool_schema

# Expose schema to Hermes
schema = get_speckit_tool_schema()

# In tool call handler:
bridge = OrchestratorBridge()
bridge.register_pipeline("execute_speckit_data_pipeline", config=SpeckitConfig(
    output_mode="technical",  # get structured data
))

def on_tool_call(name, arguments, tool_call_id):
    tc = ToolCall(name=name, arguments=arguments, tool_call_id=tool_call_id)
    result = bridge.handle_tool_call(tc)
    if "error" in result:
        return {"role": "tool", "tool_call_id": tool_call_id,
                "content": f'{{"error": "{result["error"]}"}}'}
    return OrchestratorBridge.format_as_tool_response(
        tool_call_id=tool_call_id, content=result["result"],
    )
```

### As a delegated sub-agent

```python
# Use delegate_task to run Coagula in an isolated agent
result = await delegate_task(
    goal="Run Coagula to analyze the data",
    context=f"Use coagula CLI: coagula -d '{data}' -o '{objective}' --mode technical --json",
    toolsets=["terminal"],
)
```

## Swarm / Multi-Agent Usage

Multiple pipelines registered on the same bridge — each agent calls
its own:

```python
bridge = OrchestratorBridge()
bridge.register_pipeline("finance", config=SpeckitConfig(provider="openai", output_mode="verbose"))
bridge.register_pipeline("contract", config=SpeckitConfig(provider="anthropic", output_mode="technical"))
bridge.register_pipeline("data_val", config=SpeckitConfig(provider="gemini", output_mode="concise"))

# Agent A -> "finance", Agent B -> "contract", Agent C -> "data_val"
```

### Async

```python
result = await engine.arun(data_source="...", business_objective="...")
```

Same as run() but non-blocking.  Use with async orchestrators.

## Provider Setup for OpenAI-Compatible APIs (DeepSeek, OpenRouter, Groq)

Coagula auto-patches phidata when `OPENAI_BASE_URL` is set to a
non-OpenAI endpoint.  It forces `map_system_to_developer=False` to
avoid the ``developer`` role that these providers don't support.

```bash
export OPENAI_API_KEY="sk-deepseek-key..."
export OPENAI_BASE_URL="https://api.deepseek.com/v1"

coagula -d "data" -o "analyze" --provider openai --model deepseek-chat
```

The provider in config is still ``"openai"`` — only the base URL changes.

## Output Modes

| Mode | Use Case | Behavior |
|------|----------|----------|
| `verbose` (default) | Human reading | Full analysis, detailed steps, long decision |
| `concise` | Quick summaries | Short analysis, 3 steps max, direct decision |
| `technical` | Programmatic consumption | Minimal prose, structured data in `details` field |

## Usage Patterns (Practical)

**Pattern 1: Iterative refinement.** Don't ask everything in one call.
Run Coagula once for architecture, once for code review, once for
testing plan.  Each call gets fresh context and a focused objective.

**Pattern 2: Feed source code as data_source.** For code reviews or
architecture audits, pass the full current source in data_source.
Coagula analyzes what exists before recommending changes.

**Pattern 3: Pin the details field.** In technical mode, your
instructions should tell the LLM exactly what to put in `details`:

```
instructions=[
    "Put the JSON schema in details['schema']",
    "Put the implementation plan in details['tasks'] as a list",
]
```

**Pattern 4: Validate with `--json`.** Always pass `--json` when
piping Coagula output to other tools or agents.  The structured
JSON is easier to parse than the formatted text.

## Models

```python
class SpeckitResult(BaseModel):
    context_analysis: str              # Analysis of input
    executed_steps: list[str]          # SOP steps performed
    final_decision: str                # Actionable conclusion
    confidence_score: float            # 0.0 to 1.0
    details: dict[str, Any] | None     # Rich structured data

class SpeckitConfig(BaseModel):
    provider: str                        # any string (was Literal)
    model_id: str                        # default: gpt-4o
    max_retries: int                     # 0-10, default 3
    instructions: list[str] | None
    output_mode: Literal["verbose", "concise", "technical"]
    response_model: type[BaseModel] | None  # default: SpeckitResult

class BridgeResult(BaseModel):
    success: bool
    tool_call_id: str
    data: BaseModel | None              # SpeckitResult or custom
    error: str | None
```

## Error Handling

```python
from coagula.exceptions import (
    CoagulaError,          # Base
    ValidationError,       # Bad input
    ExecutionError,        # LLM failure
    ConfigurationError,    # Missing provider/module
    RetryExhaustedError,   # All retries used
)
```

In the bridge, errors are returned as dicts with key ``"error"`` —
never raised as exceptions.  The orchestrator (an LLM) needs text,
not tracebacks.

## Pitfalls

1. **phidata extras**: `pip install 'phidata[openai]'` (or anthropic/gemini).
   Coagula lazy-imports and raises ConfigurationError if missing.
2. **OpenAI-compatible APIs**: Set `OPENAI_BASE_URL`.  Coagula auto-patches
   the role mapping.  No manual monkey-patching needed.
3. **Hermes schema sanitizer**: Avoid `allOf` in tool schemas.  Use
   `description` fields instead.
4. **Engine caching**: Bridge caches engines by pipeline name.  Call
   `unregister_pipeline()` before re-registering with a different config.
5. **Mypy**: Run as `python -m mypy -p coagula`.

## Test Suite

```bash
make dev
make test     # pytest, 65 tests
make mypy     # strict type check
make ci       # all
```
