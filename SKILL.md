---
name: coagula
description: Deterministic Speckit pipeline abstraction — SOPs as typed micro-workers. CLI, Python API, Hermes bridge, multi-provider (OpenAI/Anthropic/Gemini), auto-retry on validation failure.
category: software-development
---

# Coagula Skill — For Hermes Agents

Coagula transforms Standard Operating Procedures (SOPs) into deterministic pipelines called **Speckits**. The orchestrator (Hermes, etc.) decides *when* to execute, Coagula ensures *how* to execute — no deviation, no procedural hallucination, no asking for help.

## Installation

```bash
pip install coagula
# or in dev:
pip install -e "/Users/zeus/Documents/codes/coagula"
```

API Key required (at least one):

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export GEMINI_API_KEY="..."
```

## CLI — Direct Usage

Quick analysis without writing code:

```bash
coagula --data-source "Revenue: 12.4M, COGS: 7.1M" \
        --objective "Is the company profitable?"
```

Options:

- `-d / --data-source` — Raw data to analyze (required)
- `-o / --objective` — Analysis objective (required)
- `-p / --provider` — Provider: `openai` (default), `anthropic`, `gemini`
- `-m / --model` — Model: `gpt-4o`, `claude-opus-4`, etc.
- `-r / --max-retries` — Retries on failure (default: 3)
- `--json` — JSON output for piping
- `--register NAME` — Register pipeline with custom name
- `--list-pipelines` — List registered pipelines

Example with JSON:

```bash
coagula -d "Q3: 12.4M revenue, 7.1M COGS" -o "Profit margin" --json | jq '.final_decision'
```

## Python API

### Basic Usage

```python
from coagula import SpeckitEngine, SpeckitConfig

engine = SpeckitEngine(config=SpeckitConfig(
    provider="openai",
    model_id="gpt-4o",
    max_retries=3,
))

result = engine.run(
    data_source="Q3 revenue: $12.4M. COGS: $7.1M.",
    business_objective="Determine profitability.",
)

# result is a Pydantic-validated SpeckitResult
print(result.final_decision)    # "The company is profitable..."
print(result.confidence_score)  # 0.95
print(result.context_analysis)  # Detailed analysis
print(result.executed_steps)    # ["step 1", "step 2"]
```

### OrchestratorBridge — For integrating with Hermes

Register one or more pipelines and handle tool calls:

```python
from coagula import OrchestratorBridge, ToolCall, get_speckit_tool_schema

bridge = OrchestratorBridge()
bridge.register_pipeline("financial_analysis")
bridge.register_pipeline("contract_review")

# Get the JSON schema to expose to the orchestrator
schema = get_speckit_tool_schema()
# schema["name"] = "execute_speckit_data_pipeline"
# schema["parameters"]["required"] = ["data_source", "business_objective"]

# When the orchestrator calls the tool:
tool_call = ToolCall(
    name="financial_analysis",
    arguments={
        "data_source": "content extracted by the orchestrator",
        "business_objective": "what the user wants to know",
    },
    tool_call_id="call_001",
)

resultado = bridge.handle_tool_call(tool_call)

if "error" in resultado:
    # Failed — report to orchestrator
    resposta = {"role": "tool", "content": str(resultado["error"])}
else:
    # Success — structured result
    resposta = {
        "role": "tool",
        "tool_call_id": "call_001",
        "content": json.dumps(resultado["result"]),
    }
```

### Custom config with SOP instructions

```python
from coagula import OrchestratorBridge, SpeckitConfig

config = SpeckitConfig(
    provider="anthropic",
    model_id="claude-sonnet-4",
    max_retries=5,
    instructions=[
        "1. Extract all numbers from the data_source.",
        "2. Calculate net margin = (revenue - costs) / revenue.",
        "3. If margin < 0, classify as 'Loss'.",
        "4. Populate the SpeckitResult schema rigorously.",
    ],
)

bridge = OrchestratorBridge()
bridge.register_pipeline("financial_analysis", config=config)
```

### Pipeline Registry — Multiple SOPs

```python
from coagula import SpeckitToolRegistry, SpeckitConfig

registry = SpeckitToolRegistry()
registry.register("financial_analysis", config=SpeckitConfig(provider="openai"))
registry.register("contract_review", config=SpeckitConfig(provider="anthropic"))

# List all available schemas
for schema in registry.list_schemas():
    print(schema["name"], schema["description"][:50])
```

### Multiple pipelines in the same bridge

```python
bridge = OrchestratorBridge()

# Pipeline 1: financial analysis with OpenAI
cfg1 = SpeckitConfig(provider="openai", model_id="gpt-4o")
bridge.register_pipeline("financial_analysis", config=cfg1)

# Pipeline 2: legal review with Anthropic
cfg2 = SpeckitConfig(provider="anthropic", model_id="claude-sonnet-4")
bridge.register_pipeline("legal_review", config=cfg2)

# Pipeline 3: priority classification with Gemini
cfg3 = SpeckitConfig(provider="gemini", model_id="gemini-2.0-flash")
bridge.register_pipeline("priority_classification", config=cfg3)

# Each pipeline is a different tool call
tc1 = ToolCall(name="financial_analysis", arguments={...}, tool_call_id="c1")
tc2 = ToolCall(name="legal_review", arguments={...}, tool_call_id="c2")

r1 = bridge.handle_tool_call(tc1)
r2 = bridge.handle_tool_call(tc2)
```

## Integration with Hermes

### How to expose Coagula as a Hermes tool

1. In the Hermes code or in a skill, import Coagula
2. Get the schema with `get_speckit_tool_schema()`
3. Inject the schema into the Hermes tool registry
4. In the tool_call handler, call `bridge.handle_tool_call()`

Example Hermes skill using Coagula:

```python
# my_analysis_skill.py
from coagula import OrchestratorBridge, ToolCall, get_speckit_tool_schema

_bridge = OrchestratorBridge()
_bridge.register_pipeline("execute_speckit_data_pipeline")

def get_tool_schemas():
    """Returns schemas for Hermes to register."""
    return [get_speckit_tool_schema()]

def handle_tool_call(name, arguments, tool_call_id):
    """Handler called by Hermes when the tool is invoked."""
    tc = ToolCall(name=name, arguments=arguments, tool_call_id=tool_call_id)
    return _bridge.handle_tool_call(tc)
```

### How a Hermes agent decides to use Coagula

When the user asks for data analysis, numbers, metrics, or anything that requires structured processing:

1. **Extract** the relevant data from the conversation/context
2. **Define** the business_objective clearly
3. **Invoke** Coagula via tool call with these parameters
4. **Use** the structured result (`final_decision`, `confidence_score`) in your response

Do NOT try to perform the analysis yourself in the prompt — delegate to Coagula. It has automatic retry, Pydantic validation, and does not hallucinate steps.

## For Swarms / Multiple Agents

Each agent can have its own bridge or share one:

```python
# Shared bridge — all agents use the same pipelines
shared_bridge = OrchestratorBridge()
shared_bridge.register_pipeline("financial_analysis")
shared_bridge.register_pipeline("contract_review")

# Agent A
def analyst_agent(user_input):
    tc = ToolCall(name="financial_analysis", arguments={...}, tool_call_id="a1")
    return shared_bridge.handle_tool_call(tc)

# Agent B
def reviewer_agent(doc):
    tc = ToolCall(name="contract_review", arguments={...}, tool_call_id="b1")
    return shared_bridge.handle_tool_call(tc)

# Orchestrator collects results from both
result_a = analyst_agent(user_input)
result_b = reviewer_agent(document)
# Combine, compare, decide
```

## Tips and Best Practices

- **Always validate the result** — check if `"error"` is present before using
- **Use `--json` in CLI** for piping with jq, scripts, or other agents
- **Customize the instructions** — vague instructions produce vague results. The more specific the SOP, the better the result
- **Provider consistency** — using the same provider as the orchestrator reduces latency and simplifies API keys
- **Descriptive pipeline names** — `financial_analysis` > `pipe1` — this helps the orchestrator choose the right tool
- **max_retries=0** for cases where fast failure is better than retrying (timeout-sensitive)
- **max_retries=5+** for pipelines processing critical data where persistence pays off

## Project Structure

```
/Users/zeus/Documents/codes/coagula/
├── SKILL.md              ← this file
├── Makefile              ← make test / make mypy / make ci
├── .env.example          ← env vars template
├── pyproject.toml        ← build + deps + entrypoint
├── src/coagula/
│   ├── __init__.py       ← public exports
│   ├── __main__.py       ← CLI (coagula --data-source ...)
│   ├── models.py         ← Pydantic contracts
│   ├── engine.py         ← Phidata execution engine
│   ├── tools.py          ← Schema generation + registry
│   ├── bridge.py         ← Orchestrator adapter
│   └── exceptions.py     ← Error hierarchy
├── tests/
│   ├── conftest.py       ← Fixtures + helpers
│   ├── test_models.py    ← 9 tests
│   ├── test_engine.py    ← 7 tests
│   ├── test_tools.py     ← 10 tests
│   └── test_bridge.py    ← 8 tests
└── docs/
    └── design_document.md