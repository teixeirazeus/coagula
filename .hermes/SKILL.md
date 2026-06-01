---
name: coagula
title: Coagula — Deterministic Speckit Pipelines
description: Encapsulate SOPs into deterministic pipelines. CLI, Python API, Hermes/swarm integration. SDD presets, chain workflow, output modes, auto-patch for OpenAI-compatible APIs, async, BridgeResult, custom response models.
category: software-development
---

# Coagula — Agent Guide

Coagula turns standard operating procedures (SOPs) into deterministic
pipelines called Speckits.  Use for architecture decisions, data analysis,
code review, and Spec-Driven Development (SDD) workflows.

## Repository

/Users/zeus/Documents/codes/coagula
Published on PyPI: pip install coagula
GitHub: https://github.com/teixeirazeus/coagula

## Quick Start

### CLI

```bash
# Verbose mode (default) — full analysis + steps + decision
coagula -d "Q3 revenue: $12.4M" -o "Determine profitability"

# Technical mode — structured data, minimal prose
coagula -d "reqs..." -o "Define schema" --mode technical --json

# Concise mode — shorter output
coagula -d "data..." -o "analyze" --mode concise

# Custom provider (auto-patches phidata for DeepSeek/OpenRouter/Groq)
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
coagula -p openai -m deepseek-v4-flash -d "..." -o "..."

# SDD chain workflow — multi-step spec-driven development
coagula --chain constitution specify plan tasks \
  -d "Build a photo app" -o "Create a photo organization app"

# List available SDD presets
coagula --list-presets
```

### Python API

```python
from coagula import OrchestratorBridge, ToolCall

bridge = OrchestratorBridge()
bridge.register_pipeline("analyze")
result = bridge.handle_tool_call(ToolCall(
    name="analyze",
    arguments={"data_source": "...", "business_objective": "..."},
    tool_call_id="call_001",
))

if result.success:
    print(result.data.final_decision)  # typed attribute access
else:
    print(result.error)

# Dict-style backward compatibility
sr = result["result"]  # -> data.model_dump()
print(sr["final_decision"])
```

## Features

| Feature | Description |
|---------|-------------|
| **SDD Presets** | 5 built-in pipelines: constitution, specify, plan, tasks, analyze |
| **Chain workflow** | Execute pipelines in sequence, passing details forward |
| **Output modes** | verbose (default), concise, technical |
| **Custom response_model** | Any BaseModel subclass per pipeline |
| **BridgeResult** | Typed result with both attribute and dict-style access |
| **Async** | await engine.arun() for async orchestrators |
| **Auto-patch** | Auto-patches phidata for OpenAI-compatible APIs |
| **Provider as string** | Any provider name accepted (no more Literal lock-in) |
| **Registry enrichment** | describe(), list_descriptions() for discovery |
| **details field** | Arbitrary structured data alongside standard analysis |
| **Multi-provider** | OpenAI, Anthropic, Gemini, DeepSeek, OpenRouter, Groq |
| **Automatic retries** | Configurable retry on Pydantic validation failure |

## SDD Presets & Chain

Coagula ships with 5 pre-built Spec-Driven Development pipelines:

| Preset | Description |
|--------|-------------|
| `constitution` | Project governing principles and development guidelines |
| `specify` | Structured requirements with user stories and acceptance criteria |
| `plan` | Technical implementation plan with tech stack and architecture |
| `tasks` | Ordered actionable tasks with effort estimates and dependencies |
| `analyze` | Cross-artifact consistency check |

Register all presets:

```python
from coagula import OrchestratorBridge, register_sdd_presets

bridge = OrchestratorBridge()
register_sdd_presets(bridge._registry)
```

Execute them as a chained workflow:

```python
results = bridge.chain(
    ["constitution", "specify", "plan", "tasks"],
    data_source="Build a photo album app with drag-and-drop albums...",
    business_objective="Create a photo organization application",
)
for name, r in zip(["constitution", "specify", "plan", "tasks"], results):
    print(f"{name}: {'OK' if r.success else f'FAILED: {r.error}'}")
```

Each step passes its `details` field as context to the next step.
The CLI equivalent:

```bash
coagula --chain constitution specify plan tasks \
  -d "Build a photo app" -o "Create a photo app"
```

Selective registration:

```python
register_sdd_presets(bridge._registry, include=["specify", "plan", "tasks"])
```

## Registry Enrichment

Each pipeline now carries a description for discoverability:

```python
# Describe a specific pipeline
info = bridge._registry.describe("specify")
print(info["description"])  # "Transform user requirements..."
print(info["schema"])       # tool JSON schema
print(info["config"])       # serialized SpeckitConfig

# List all registered pipelines
for entry in bridge._registry.list_descriptions():
    print(f"  {entry['name']}: {entry['description']}")
```

When registering custom pipelines:

```python
registry.register(
    name="code_review",
    description="Review source code for bugs, security issues, and code quality.",
    config=SpeckitConfig(provider="anthropic", output_mode="technical"),
)
```

## Python API

### Engine with custom response model

```python
from pydantic import BaseModel
from coagula import SpeckitEngine, SpeckitConfig

class ReviewResult(BaseModel):
    issues: list[str]
    score: int
    recommendation: str

engine = SpeckitEngine(config=SpeckitConfig(
    provider="anthropic",
    model_id="claude-sonnet-4",
    response_model=ReviewResult,
    output_mode="technical",
    instructions=[
        "Review the provided code. List all issues.",
        "Put critical bugs in details['critical'].",
    ],
))
result = engine.run(data_source="# source code...", business_objective="Find bugs")
# result is ReviewResult, not SpeckitResult
print(result.issues, result.score)
```

### Rich output with details

```python
engine = SpeckitEngine(config=SpeckitConfig(
    output_mode="technical",
    instructions=["Put the JSON schema in details['schema']",
                  "Put tasks in details['tasks'] as a list"],
))
result = engine.run(data_source="...", business_objective="...")
if result.details:
    print(result.details.get("schema"))
    print(result.details.get("tasks"))
```

### Async

```python
result = await engine.arun(data_source="...", business_objective="...")
```

## Hermes Integration

```python
from coagula import OrchestratorBridge, ToolCall, get_speckit_tool_schema

# Expose schema
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
    return {"role": "tool", "tool_call_id": tool_call_id,
            "content": f'{{"error": "{result.error}"}}'}
```

As a delegated sub-agent:

```python
result = await delegate_task(
    goal="Run Coagula SDD chain for the project",
    context="Use coagula CLI: coagula --chain specify plan tasks ... --mode technical --json",
    toolsets=["terminal"],
)
```

## Provider Setup

### OpenAI (default)
```bash
export OPENAI_API_KEY=*** pip install 'phidata[openai]'
coagula -p openai -m gpt-4o -d "..." -o "..."
```

### Anthropic
```bash
export ANTHROPIC_API_KEY="sk-a...pip install 'phidata[anthropic]'
coagula -p anthropic -m claude-sonnet-4 -d "..." -o "..."
```

### OpenAI-compatible (DeepSeek, OpenRouter, Groq)
Coagula auto-patches phidata when OPENAI_BASE_URL is set to a non-OpenAI
endpoint.  No manual monkey-patching required.

```bash
export OPENAI_API_KEY=*** OPENAI_BASE_URL="https://api.deepseek.com/v1"
pip install 'phidata[openai]'
coagula -p openai -m deepseek-v4-flash -d "..." -o "..."
```

**Important:** Default model_id is `gpt-4o`.  Always override via `--model`
for non-OpenAI providers.  Known DeepSeek models: deepseek-v4-flash, deepseek-v4-pro.

## Output Modes

| Mode | Flag | Use Case | Behavior |
|------|------|----------|----------|
| verbose (default) | *(none)* | Human reading | Full analysis, detailed steps, long decision |
| concise | --mode concise | Quick summaries | Short analysis, 3 steps max, direct decision |
| technical | --mode technical | Programmatic | Minimal prose, structured data in details field |

## Models

```python
class SpeckitResult(BaseModel):
    context_analysis: str
    executed_steps: list[str]
    final_decision: str
    confidence_score: float       # 0.0 to 1.0
    details: dict[str, Any] | None

class SpeckitConfig(BaseModel):
    provider: str                 # any string (was Literal)
    model_id: str                 # default: gpt-4o
    max_retries: int              # 0-10, default 3
    instructions: list[str] | None
    output_mode: Literal["verbose", "concise", "technical"]
    response_model: type[BaseModel] | None  # default: SpeckitResult

class BridgeResult(BaseModel):
    success: bool
    tool_call_id: str
    data: BaseModel | None        # SpeckitResult or custom model
    error: str | None
    # __getitem__ for dict-style compat: result["result"] -> model_dump()
```

## Error Handling

```python
from coagula.exceptions import (
    CoagulaError,          # Base
    ValidationError,       # Bad input data
    ExecutionError,        # LLM failure
    ConfigurationError,    # Missing provider/module
    RetryExhaustedError,   # All retries exhausted
)
```

BridgeResult returns errors as structured objects, not exceptions.
Check `result.success` and `result.error`.

## Usage Patterns

**Pattern 1: SDD chain workflow.** Use --chain for multi-step development.
Constitution -> specify -> plan -> tasks covers the full spec-driven cycle.

**Pattern 2: One concern per call.** Run Coagula once for architecture,
once for code review, once for test plan.  Each call has a focused objective.

**Pattern 3: Feed source code as data_source.** For code reviews and audits,
pass the full source.  Coagula analyzes what exists before recommending changes.

**Pattern 4: Pin the details field.** In instructions, tell the LLM exactly
what structured data to put in details:
```
instructions=[
    "Put the JSON schema in details['schema']",
    "Put implementation tasks in details['tasks'] as a list",
]
```

**Pattern 5: Always use --json for scripting.** Pipe Coagula output to jq
or parse it programmatically when consumed by other agents.

**Pattern 6: Save Coagula evidence.** Create COAGULA_EVIDENCE.md alongside
generated artifacts to document what was decided and why.

## Pitfalls

1. **phidata extras**: `pip install 'phidata[openai]'` (or anthropic/gemini).
   Coagula lazy-imports and raises ConfigurationError if missing.
2. **Default model_id is gpt-4o**: Always override for non-OpenAI providers.
3. **Hermes schema sanitizer**: Avoid allOf in tool schemas.  Use description fields.
4. **Engine caching**: Bridge caches engines by pipeline name.  Call
   unregister_pipeline() before re-registering with a different config.
5. **Mypy**: Run as `python -m mypy -p coagula`.

## Test Suite

```bash
make dev      # pip install -e ".[dev]"
make test     # pytest, 65 tests
make mypy     # strict type check, 8 modules
make ci       # all of the above
```
