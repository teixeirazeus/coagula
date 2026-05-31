"""
Deterministic Speckit execution engine built on top of Phidata.

The :class:`SpeckitEngine` encapsulates a single-task Phidata ``Agent`` that
is bound to a Pydantic response model.  This forces the underlying LLM to
produce structured, validated output — eliminating procedural hallucinations
and open-ended text generation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel

from coagula.exceptions import (
    ConfigurationError,
    ExecutionError,
    RetryExhaustedError,
)
from coagula.models import SpeckitConfig, SpeckitResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default instructions   (used when the user does not supply custom ones)
# ---------------------------------------------------------------------------

_DEFAULT_INSTRUCTIONS: dict[str, list[str]] = {
    "verbose": [
        (
            "1. Analyze 'data_source' based exclusively on 'business_objective'.  "
            "Do not add extraneous commentary."
        ),
        (
            "2. Do not ask questions.  If context is missing, assume the most "
            "conservative premise."
        ),
        (
            "3. Your only function is to populate the output schema perfectly.  "
            "Never mention that you are an AI or incapable of performing an action."
        ),
    ],
    "concise": [
        "1. Analyze input concisely.  One paragraph max for context_analysis.",
        "2. List only the essential steps in executed_steps (3 max).",
        "3. Output a direct final_decision.  No filler.",
        "4. Never ask questions.  Assume conservative defaults.",
    ],
    "technical": [
        "1. Analyze the input and produce ONLY the output schema.",
        "2. Put the primary deliverable (schema, code, config) in the 'details' field as structured JSON.",
        "3. Use context_analysis for a one-line summary only.",
        "4. List executed_steps as brief technical labels.",
        "5. final_decision must be a single actionable sentence.",
        "6. Never explain.  Never ask questions.  Populate the schema.",
    ],
}

# ---------------------------------------------------------------------------
# Lazy Phidata model imports
# ---------------------------------------------------------------------------


def _get_openai_chat() -> Any:
    try:
        from phi.model.openai import OpenAIChat
        return OpenAIChat
    except ImportError:
        return None


def _get_anthropic_chat() -> Any:
    try:
        from phi.model.anthropic import Claude
        return Claude
    except ImportError:
        return None


def _get_gemini_chat() -> Any:
    try:
        from phi.model.gemini import Gemini
        return Gemini
    except ImportError:
        return None


def _get_agent_class() -> Any:
    try:
        from phi.agent import Agent
        return Agent
    except ImportError:
        raise ConfigurationError(
            "phidata is not installed.  Run ``pip install phidata``."
        )


def _patch_for_openai_compatible(model_cls: Any) -> Any:
    """Patch OpenAIChat.format_message for OpenAI-compatible endpoints.

    Providers like DeepSeek, OpenRouter, Groq use OpenAI-compatible APIs
    but do not support the ``developer`` role (used by phidata >= 2.7).
    This patch forces ``map_system_to_developer=False`` when
    ``OPENAI_BASE_URL`` is set to a non-OpenAI endpoint.
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "").lower()
    if not base_url or "api.openai.com" in base_url:
        return model_cls

    try:
        original = model_cls.format_message

        def _patched_format(self: Any, message: Any, map_system_to_developer: bool = True) -> Any:
            return original(self, message, map_system_to_developer=False)

        model_cls.format_message = _patched_format
    except AttributeError:
        pass

    return model_cls


def _resolve_model_class(provider: str) -> Any:
    """Return the Phidata model class for the given provider string."""
    mapping: dict[str, Any] = {
        "openai": _get_openai_chat(),
        "anthropic": _get_anthropic_chat(),
        "gemini": _get_gemini_chat(),
    }
    cls = mapping.get(provider)
    if cls is None:
        raise ConfigurationError(
            f"Unsupported provider '{provider}'.  "
            f"Supported: {', '.join(sorted(mapping))}.  "
            f"Ensure the corresponding phidata extras are installed "
            f"(e.g. ``pip install 'phidata[openai]'``)."
        )

    if provider == "openai":
        cls = _patch_for_openai_compatible(cls)

    return cls


# ---------------------------------------------------------------------------
# SpeckitEngine
# ---------------------------------------------------------------------------


class SpeckitEngine:
    """Deterministic Speckit pipeline execution engine.

    The engine instantiates a Phidata ``Agent`` on every ``run()`` call,
    ensuring a clean context for each execution.

    Parameters
    ----------
    config:
        Engine configuration (provider, model ID, retries, mode, response model).
    """

    def __init__(self, config: SpeckitConfig | None = None) -> None:
        self._config = config or SpeckitConfig()

    # -- public API ---------------------------------------------------------

    @property
    def config(self) -> SpeckitConfig:
        """Return the current engine configuration."""
        return self._config

    def run(
        self,
        data_source: str,
        business_objective: str,
    ) -> SpeckitResult | BaseModel:
        """Execute the Speckit pipeline against the given inputs (sync).

        Parameters
        ----------
        data_source:
            Raw data, text, or context to be processed.
        business_objective:
            The specific goal of the analysis.

        Returns
        -------
        A validated model instance.  The type is determined by
        ``config.response_model`` (defaults to ``SpeckitResult``).

        Raises
        ------
        ExecutionError:
            If the underlying LLM call fails irrecoverably.
        RetryExhaustedError:
            If the engine exhausts all internal retries.
        """
        return self._run_loop(data_source, business_objective)

    async def arun(
        self,
        data_source: str,
        business_objective: str,
    ) -> SpeckitResult | BaseModel:
        """Execute the Speckit pipeline against the given inputs (async).

        Same as :meth:`run` but uses ``await agent.arun()``.  Use this
        when integrating with async orchestrators to avoid blocking.

        Parameters
        ----------
        data_source:
            Raw data, text, or context to be processed.
        business_objective:
            The specific goal of the analysis.

        Returns
        -------
        A validated model instance.  The type is determined by
        ``config.response_model`` (defaults to ``SpeckitResult``).
        """
        return await self._arun_loop(data_source, business_objective)

    # -- internal: sync run --------------------------------------------------

    def _run_loop(self, data_source: str, business_objective: str) -> SpeckitResult | BaseModel:
        """Internal sync execution loop with retries."""
        agent = self._build_agent()
        task_prompt = f"DATA: {data_source}\nOBJECTIVE: {business_objective}"

        last_error: Exception | None = None
        remaining = self._config.max_retries
        response_model_cls: type[BaseModel] = self._config.response_model or SpeckitResult

        while remaining >= 0:
            try:
                response = agent.run(task_prompt)
                result: BaseModel = response.content
                if not isinstance(result, response_model_cls):
                    raise ExecutionError(
                        f"Expected {response_model_cls.__name__}, "
                        f"got {type(result).__name__}"
                    )
                logger.info(
                    "Pipeline succeeded (attempt %d/%d)",
                    self._config.max_retries - remaining + 1,
                    self._config.max_retries + 1,
                )
                return result
            except Exception as exc:
                last_error = exc
                remaining -= 1
                logger.warning(
                    "Pipeline attempt failed (%d remaining): %s",
                    remaining, exc,
                )

        raise RetryExhaustedError(
            f"Speckit pipeline failed after {self._config.max_retries} retries.  "
            f"Last error: {last_error}"
        ) from last_error

    # -- internal: async run -------------------------------------------------

    async def _arun_loop(self, data_source: str, business_objective: str) -> SpeckitResult | BaseModel:
        """Internal async execution loop with retries."""
        agent = self._build_agent()
        task_prompt = f"DATA: {data_source}\nOBJECTIVE: {business_objective}"

        last_error: Exception | None = None
        remaining = self._config.max_retries
        response_model_cls: type[BaseModel] = self._config.response_model or SpeckitResult

        while remaining >= 0:
            try:
                response = await agent.arun(task_prompt)
                result: BaseModel = response.content
                if not isinstance(result, response_model_cls):
                    raise ExecutionError(
                        f"Expected {response_model_cls.__name__}, "
                        f"got {type(result).__name__}"
                    )
                logger.info(
                    "Pipeline succeeded (attempt %d/%d)",
                    self._config.max_retries - remaining + 1,
                    self._config.max_retries + 1,
                )
                return result
            except Exception as exc:
                last_error = exc
                remaining -= 1
                logger.warning(
                    "Pipeline attempt failed (%d remaining): %s",
                    remaining, exc,
                )

        raise RetryExhaustedError(
            f"Speckit pipeline failed after {self._config.max_retries} retries.  "
            f"Last error: {last_error}"
        ) from last_error

    # -- internal helpers ---------------------------------------------------

    def _build_agent(self) -> Any:
        """Construct a fresh Phidata ``Agent`` per the current config."""
        model_cls = _resolve_model_class(self._config.provider)
        agent_cls = _get_agent_class()

        if self._config.instructions is not None:
            instructions = self._config.instructions
        else:
            instructions = _DEFAULT_INSTRUCTIONS.get(
                self._config.output_mode,
                _DEFAULT_INSTRUCTIONS["verbose"],
            )

        response_model = self._config.response_model or SpeckitResult

        agent = agent_cls(
            model=model_cls(id=self._config.model_id),
            description=(
                "You are a deterministic data processing engine.  "
                "You do not converse.  You strictly follow the SOP."
            ),
            instructions=instructions,
            response_model=response_model,
            show_tool_calls=False,
        )
        return agent
