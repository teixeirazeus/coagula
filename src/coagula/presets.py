"""
SDD presets for coagula — Spec-Driven Development pipelines.

These presets follow the Spec Kit-inspired workflow:
  1. **constitution** — Project principles and guidelines
  2. **specify** — Requirements definition (what + why)
  3. **plan** — Technical implementation plan
  4. **tasks** — Task breakdown
  5. **analyze** — Cross-artifact consistency check

Usage
-----
.. code-block:: python

    from coagula.presets import register_sdd_presets
    from coagula import OrchestratorBridge

    bridge = OrchestratorBridge()
    register_sdd_presets(bridge)

    # Chain them together:
    results = bridge.chain(
        ["constitution", "specify", "plan", "tasks"],
        data_source="Build a photo album app...",
        business_objective="Create a photo organization application",
    )
"""

from __future__ import annotations

from typing import Any

from coagula.models import SpeckitConfig
from coagula.tools import SpeckitToolRegistry


def _register_pipeline(
    registry: SpeckitToolRegistry,
    name: str,
    description: str,
    config: SpeckitConfig | None = None,
    schema: dict[str, Any] | None = None,
) -> None:
    """Register a single SDD pipeline with a human-readable description."""
    registry.register(
        name=name,
        schema=schema,
        config=config,
        description=description,
    )


def register_constitution(registry: SpeckitToolRegistry) -> None:
    """Register the constitution pipeline.

    Defines project governing principles and development guidelines
    that guide all subsequent development phases.
    """
    _register_pipeline(
        registry,
        name="constitution",
        description=(
            "Define project governing principles and development guidelines. "
            "Output includes code quality standards, testing requirements, "
            "UX principles, and performance criteria."
        ),
        config=SpeckitConfig(
            output_mode="technical",
            instructions=[
                "1. Analyze the project requirements thoroughly.",
                "2. Define 5-8 governing principles covering: code quality, testing, UX, performance, security, maintainability.",
                "3. Put each principle in details['principles'] as a list of dicts with 'name' and 'description'.",
                "4. Summarize the overall approach in final_decision.",
                "5. Never ask questions. Assume conservative defaults.",
            ],
        ),
    )


def register_specify(registry: SpeckitToolRegistry) -> None:
    """Register the specify pipeline.

    Takes user requirements and produces a structured specification
    with user stories, acceptance criteria, and scope boundaries.
    """
    _register_pipeline(
        registry,
        name="specify",
        description=(
            "Transform user requirements into a structured specification. "
            "Output includes user stories, acceptance criteria, scope, "
            "and boundary definitions."
        ),
        config=SpeckitConfig(
            output_mode="technical",
            instructions=[
                "1. Analyze the requirements and extract core user needs.",
                "2. Define 3-6 user stories with acceptance criteria.",
                "3. Define scope boundaries (in scope / out of scope).",
                "4. Put user stories in details['stories'] as a list.",
                "5. Put scope in details['scope'] as dict with 'in' and 'out' lists.",
                "6. Summarize the feature in final_decision.",
            ],
        ),
    )


def register_plan(registry: SpeckitToolRegistry) -> None:
    """Register the plan pipeline.

    Creates a technical implementation plan from a specification,
    including technology choices, architecture, data model, and
    component design.
    """
    _register_pipeline(
        registry,
        name="plan",
        description=(
            "Create a technical implementation plan from a specification. "
            "Output includes tech stack decisions, architecture diagram, "
            "data model, component design, and API contracts."
        ),
        config=SpeckitConfig(
            output_mode="technical",
            instructions=[
                "1. Review the specification provided in data_source.",
                "2. Define the tech stack with rationale for each choice.",
                "3. Define the architecture: components, data flow, boundaries.",
                "4. Define the data model (entities, relationships, fields).",
                "5. Put tech stack in details['tech_stack'] as a list.",
                "6. Put architecture in details['architecture'] as a dict.",
                "7. Put data model in details['data_model'] as a list of entities.",
                "8. Summarize the plan in final_decision.",
            ],
        ),
    )


def register_tasks(registry: SpeckitToolRegistry) -> None:
    """Register the tasks pipeline.

    Breaks a technical implementation plan into actionable,
    ordered tasks that can be executed independently.
    """
    _register_pipeline(
        registry,
        name="tasks",
        description=(
            "Break down a technical plan into ordered, actionable tasks. "
            "Each task includes description, effort estimate, dependencies, "
            "and acceptance criteria."
        ),
        config=SpeckitConfig(
            output_mode="technical",
            instructions=[
                "1. Review the implementation plan provided in data_source.",
                "2. Break the work into 5-10 ordered tasks.",
                "3. Each task must have: name, description, effort (S/M/L), dependencies, and criteria.",
                "4. Put tasks in details['tasks'] as a list of dicts.",
                "5. Summarize total effort and timeline in final_decision.",
            ],
        ),
    )


def register_analyze(registry: SpeckitToolRegistry) -> None:
    """Register the analyze pipeline.

    Checks cross-artifact consistency between specification,
    plan, and tasks.  Identifies gaps, contradictions, and
    missing coverage.
    """
    _register_pipeline(
        registry,
        name="analyze",
        description=(
            "Check consistency across development artifacts "
            "(specification, plan, tasks). Identify gaps, "
            "contradictions, and missing coverage before implementation."
        ),
        config=SpeckitConfig(
            output_mode="technical",
            instructions=[
                "1. Review all provided artifacts (spec, plan, tasks).",
                "2. Check: do tasks cover all user stories?",
                "3. Check: is the plan consistent with the spec?",
                "4. List each issue with severity (low/medium/high).",
                "5. Put issues in details['issues'] as a list.",
                "6. Put overall assessment in details['assessment'].",
                "7. Recommend fix-or-proceed in final_decision.",
            ],
        ),
    )


def register_sdd_presets(
    registry: SpeckitToolRegistry,
    include: list[str] | None = None,
) -> list[str]:
    """Register all (or selected) SDD preset pipelines on a registry.

    Parameters
    ----------
    registry:
        The registry to register pipelines on.
    include:
        Subset of pipelines to register.  If ``None``, registers all.
        Options: ``constitution``, ``specify``, ``plan``, ``tasks``,
        ``analyze``.

    Returns
    -------
    List of registered pipeline names.
    """
    all_presets = {
        "constitution": register_constitution,
        "specify": register_specify,
        "plan": register_plan,
        "tasks": register_tasks,
        "analyze": register_analyze,
    }

    names = include or list(all_presets.keys())
    registered: list[str] = []
    for name in names:
        if name in all_presets:
            all_presets[name](registry)
            registered.append(name)
    return registered
