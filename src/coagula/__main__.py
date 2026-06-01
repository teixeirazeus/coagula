"""CLI entrypoint for coagula — run a Speckit pipeline from the command line.

Usage:

    # Run with default (OpenAI GPT-4o, verbose mode)
    coagula --data-source "Q3 revenue: $12.4M" --objective "Determine profitability"

    # Technical mode — minimal prose, structured details
    coagula -d "..." -o "..." --mode technical --json

    # Concise mode
    coagula -d "..." -o "..." --mode concise

    # Run with a different provider
    coagula -d "..." -o "..." --provider anthropic --model claude-opus-4

    # Register a custom pipeline
    coagula --register my_pipeline -d "..." -o "..."

    # List registered pipelines
    coagula --list-pipelines

Environment variables:
    OPENAI_API_KEY      Required when provider is "openai"
    ANTHROPIC_API_KEY   Required when provider is "anthropic"
    GEMINI_API_KEY      Required when provider is "gemini"
    OPENAI_BASE_URL     Set for OpenAI-compatible providers (DeepSeek, etc.)
"""

from __future__ import annotations

import json
import sys
from typing import Any

from coagula.bridge import OrchestratorBridge
from coagula.models import SpeckitConfig, ToolCall


def _parse_args(args: list[str]) -> dict[str, Any]:
    """Minimal argument parser (no external deps)."""
    opts: dict[str, Any] = {}
    i = 0
    while i < len(args):
        if args[i] in ("--data-source", "-d"):
            i += 1
            opts["data_source"] = args[i]
        elif args[i] in ("--objective", "-o"):
            i += 1
            opts["business_objective"] = args[i]
        elif args[i] in ("--provider", "-p"):
            i += 1
            opts["provider"] = args[i]
        elif args[i] in ("--model", "-m"):
            i += 1
            opts["model_id"] = args[i]
        elif args[i] in ("--max-retries", "-r"):
            i += 1
            opts["max_retries"] = int(args[i])
        elif args[i] in ("--mode",):
            i += 1
            mode = args[i].lower()
            if mode not in ("verbose", "concise", "technical"):
                print(f"Error: invalid mode '{mode}'. Use verbose, concise, or technical.", file=sys.stderr)
                sys.exit(1)
            opts["output_mode"] = mode
        elif args[i] == "--register":
            i += 1
            opts["register"] = args[i]
        elif args[i] in ("--list-pipelines", "-l"):
            opts["list_pipelines"] = True
        elif args[i] in ("--help", "-h"):
            opts["help"] = True
        elif args[i] == "--json":
            opts["json_output"] = True
        elif args[i] == "--details":
            opts["show_details"] = True
        elif args[i] in ("--chain",):
            opts["chain"] = []
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                opts["chain"].append(args[i])
                i += 1
            continue
        elif args[i] in ("--list-presets",):
            opts["list_presets"] = True
        i += 1
    return opts


def _print_help() -> None:
    print(__doc__)


def _display_result(sr: dict[str, Any], json_output: bool, show_details: bool) -> None:
    """Display a SpeckitResult to stdout."""
    if json_output:
        output = dict(sr)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    print("=== Speckit Result ===")
    print(f"  Analysis:    {sr['context_analysis'][:150]}{'...' if len(sr['context_analysis']) > 150 else ''}")
    print(f"  Steps:       {len(sr['executed_steps'])} step(s)")
    for step in sr["executed_steps"]:
        print(f"    - {step}")
    print(f"  Decision:    {sr['final_decision']}")
    print(f"  Confidence:  {sr['confidence_score']:.0%}")

    if show_details and sr.get("details"):
        print(f"\n  --- Details ---")
        detail_str = json.dumps(sr["details"], indent=2, ensure_ascii=False)
        for line in detail_str.splitlines():
            print(f"  {line}")

    print("======================")


def main() -> None:
    opts = _parse_args(sys.argv[1:])

    if opts.get("help"):
        _print_help()
        sys.exit(0)

    provider = opts.get("provider", "openai")
    model_id = opts.get("model_id")
    max_retries = opts.get("max_retries", 3)
    json_output = opts.get("json_output", False)
    show_details = opts.get("show_details", False)

    bridge = OrchestratorBridge()
    pipeline_name = opts.get("register", "default")

    # Build config
    config_kwargs: dict[str, Any] = {
        "provider": provider,
        "max_retries": max_retries,
    }
    if model_id:
        config_kwargs["model_id"] = model_id
    if opts.get("output_mode"):
        config_kwargs["output_mode"] = opts["output_mode"]
    config = SpeckitConfig(**config_kwargs)

    bridge.register_pipeline(pipeline_name, config=config)

    if opts.get("list_pipelines"):
        schemas = bridge._registry.list_schemas()
        for s in schemas:
            print(f"  - {s['name']}: {s['description'][:60]}...")
        sys.exit(0)

    if opts.get("list_presets"):
        from coagula.presets import register_sdd_presets
        # Show available presets without registering
        print("Available SDD presets (use --chain to run):")
        print("  constitution  - Project principles and guidelines")
        print("  specify       - Requirements specification")
        print("  plan          - Technical implementation plan")
        print("  tasks         - Task breakdown")
        print("  analyze       - Cross-artifact consistency check")
        print("\nExample:")
        print("  coagula --chain constitution specify plan tasks \\")
        print("    -d 'Build a photo app...' -o 'Create a photo app'")
        sys.exit(0)

    # Handle chain
    chain_pipelines = opts.get("chain")
    if chain_pipelines:
        data_source = opts.get("data_source", "")
        business_objective = opts.get("business_objective", "")
        if not data_source or not business_objective:
            print("Error: --data-source and --objective are required with --chain", file=sys.stderr)
            sys.exit(1)

        # Register SDD presets
        from coagula.presets import register_sdd_presets
        register_sdd_presets(bridge._registry, include=chain_pipelines)

        results = bridge.chain(chain_pipelines, data_source, business_objective)
        for i, (name, r) in enumerate(zip(chain_pipelines, results)):
            print(f"\n=== Step {i+1}: {name} ===")
            if r.success:
                print(f"  Result: success")
                if json_output:
                    print(json.dumps(r.data.model_dump() if r.data else {}, indent=2))
                else:
                    _display_result(r.data.model_dump() if r.data else {}, json_output, show_details)
            else:
                print(f"  Result: FAILED")
                print(f"  Error: {r.error}")
        sys.exit(0 if all(r.success for r in results) else 1)

    data_source = opts.get("data_source", "")
    business_objective = opts.get("business_objective", "")

    if not data_source or not business_objective:
        print("Error: --data-source and --objective are required (see --help)")
        sys.exit(1)

    tool_call = ToolCall(
        name=pipeline_name,
        arguments={
            "data_source": data_source,
            "business_objective": business_objective,
        },
        tool_call_id="cli_call_001",
    )

    result = bridge.handle_tool_call(tool_call)

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    if result.data is None:
        print("Error: pipeline returned no data", file=sys.stderr)
        sys.exit(1)

    _display_result(result.data.model_dump(), json_output, show_details)


if __name__ == "__main__":
    main()
