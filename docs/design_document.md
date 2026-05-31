# Technical Architecture Document: Deterministic "Speckit" Agent Integration

## 1. Executive Summary

Autonomous AI agents often struggle with process adherence, frequently falling into loops, hallucinating steps, or unnecessarily requesting human validation when faced with ambiguity. The goal of this architecture is to solve this by abstracting standard operating procedures (SOPs)—referred to here as a "Speckit"—into a deterministic, highly reliable pipeline.

Instead of granting the primary conversational agent total autonomy over a complex workflow, the Speckit is encapsulated as an isolated, strictly typed micro-worker. This ensures execution predictability while maintaining the conversational flexibility of the main orchestrator.

## 2. High-Level Architecture

The system utilizes a **Supervisor-Worker** design pattern. It separates the conversational intelligence from the procedural execution.

- **The Orchestrator (Hermes):** Acts as the frontend supervisor. It handles natural language interactions, understands user intent, and decides _when_ to trigger the Speckit.
    
- **The Abstraction Layer (Tool Calling):** The Speckit is exposed to Hermes purely as a black-box function tool.
    
- **The Deterministic Engine (Phidata):** When triggered, Phidata takes over the execution. It acts as a single-task agent bound by strict data contracts (Pydantic), forcing the underlying LLM to follow the SOP step-by-step.
    
- **The Shared Inference Engine (API LLM):** Instead of relying on a local container, the system reuses the same LLM API connection (e.g., OpenAI, Anthropic, Gemini) utilized by the main orchestrator. This simplifies the infrastructure, reduces deployment weight, and ensures consistent reasoning quality across both the conversational and procedural layers.
    

## 3. Core Components & Data Flow

### 3.1. Tool Definition (Hermes Context)

Hermes must be provided with a strict JSON schema describing the tool. This prevents the orchestrator from attempting to execute the analysis itself.

JSON

```
{
  "name": "execute_speckit_data_pipeline",
  "description": "Executes the strict, automated Speckit data analysis SOP. Use this tool autonomously when a user requests analysis. DO NOT ask the user for procedural help. Gather the required parameters and trigger this function.",
  "parameters": {
    "type": "object",
    "properties": {
      "data_source": {
        "type": "string",
        "description": "Raw data, text, or context to be processed."
      },
      "business_objective": {
        "type": "string",
        "description": "The specific goal of the analysis."
      }
    },
    "required": ["data_source", "business_objective"]
  }
}
```

### 3.2. Strict Output Contracting (Pydantic)

To enforce reliability and prevent open-ended text generation that leads to human-in-the-loop requests, the expected output is strongly typed. If the LLM fails to match this schema, Phidata automatically handles validation errors and triggers internal retries.

Python

```
from pydantic import BaseModel, Field

class SpeckitResult(BaseModel):
    context_analysis: str = Field(description="Detailed analysis of the provided input data.")
    executed_steps: list[str] = Field(description="Strict list of validation steps performed according to the SOP.")
    final_decision: str = Field(description="Actionable conclusion based on business rules.")
    confidence_score: float = Field(description="Confidence level of the output (0.0 to 1.0).")
```

### 3.3. Phidata Task Execution (The Speckit Motor)

The worker agent is instantiated on demand. To optimize resources and maintain context, it utilizes the same LLM provider as the calling agent. Its system prompt strictly forbids conversational behavior and enforces the procedural guidelines.

Python

```
from phi.agent import Agent
from pydantic import BaseModel, Field
# Import the appropriate model provider matching Hermes (e.g., OpenAI, Anthropic, Gemini)
from phi.model.openai import OpenAIChat 

def run_speckit_pipeline(data_source: str, objective: str) -> dict:
    # Instantiating the deterministic worker using the shared cloud LLM
    speckit_agent = Agent(
        model=OpenAIChat(id="gpt-4o"), # Maps to the same model Hermes is using
        description="You are a deterministic data processing engine. You do not converse. You strictly follow the SOP.",
        instructions=[
            "1. Analyze 'data_source' based exclusively on 'objective'.",
            "2. Do not ask questions. If context is missing, assume the most conservative premise.",
            "3. Your only function is to populate the output schema perfectly."
        ],
        response_model=SpeckitResult, 
        show_tool_calls=False,
    )

    task_prompt = f"DATA: {data_source}\nOBJECTIVE: {objective}"
    response = speckit_agent.run(task_prompt)
    
    # Returns a validated, structured Python dictionary
    return response.content.model_dump()
```

_(Architectural Note: For advanced implementations, the existing initialized LLM client object from Hermes can be passed directly as an argument to `run_speckit_pipeline` to avoid redundant API initializations)._

### 3.4. Orchestrator Integration (The Bridge)

In the main execution loop, when Hermes yields a `tool_call`, the system intercepts it, executes the Phidata script, and returns the strictly formatted result to the conversational context.

Python

```
import json

# Inside the Hermes main execution loop
if tool_call.name == "execute_speckit_data_pipeline":
    
    # Extract arguments provided by Hermes
    args = json.loads(tool_call.arguments)
    
    # Execute the rigid SOP
    try:
        speckit_json_result = run_speckit_pipeline(
            data_source=args.get("data_source"),
            objective=args.get("business_objective")
        )
        
        # Append the successful execution back to Hermes' context
        append_to_hermes_context(
            role="tool", 
            tool_call_id=tool_call.id, 
            content=json.dumps(speckit_json_result)
        )
    except Exception as e:
        # Graceful degradation if the strict pipeline fails
        append_to_hermes_context(
            role="tool", 
            tool_call_id=tool_call.id, 
            content=f'{{"error": "Speckit execution failed: {str(e)}" }}'
        )
```

## 4. Key Advantages & Technical Considerations

- **Context Token Optimization:** By isolating the SOP execution, Hermes does not need to load the entire Speckit manual into its system prompt. This drastically reduces the token overhead per message, ensuring efficient processing.
    
- **Zero-Hallucination Routing:** The conversational agent (Hermes) never executes the steps; it merely triggers the tool. The actual steps are hardcoded into the Phidata instruction set and enforced by Pydantic, virtually eliminating procedural hallucinations.
    
- **Resilience via Structured Outputs:** By forcing the LLM to output JSON conforming to the Pydantic schema, the architecture prevents the agent from halting execution to request user input. Missing data is handled programmatically via conservative defaults defined in the instructions.
    
- **Infrastructure Simplicity & Cloud Scale:** By removing the local inference requirement, the architecture becomes lightweight and highly scalable. Using the same LLM API as the orchestrator streamlines API key management, consolidates billing, and guarantees that the deterministic worker possesses the exact same reasoning capabilities as the primary conversational agent.