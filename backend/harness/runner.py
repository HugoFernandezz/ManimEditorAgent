"""Resilient agent invocation: retry + backoff + telemetry + guardrails.

Wraps claude_runner.run_text / run_with_tools so every agent call gets:
  - exponential backoff retry on transient subprocess errors
  - duration / size metrics
  - optional output validator (compact errors back into prompt — 12-Factor #9)
  - structured events appended to the log
"""
from __future__ import annotations
import time
from pathlib import Path
from typing import Callable

from claude_runner import run_text, run_with_tools
from harness.events import AgentEvent
from harness.store import append_event
from harness.telemetry import measure, metric_event


Validator = Callable[[str], tuple[bool, str]]  # (raw_output) -> (ok, message_or_repair)


class AgentCallFailed(Exception):
    """All retries exhausted or validator rejected output beyond repair."""


def call_agent(
    *,
    project_id: str,
    agent: str,
    prompt: str,
    system: str,
    model: str = "sonnet",
    tools: str | None = None,
    add_dirs: list[Path] | None = None,
    timeout: int = 180,
    max_attempts: int = 3,
    validator: Validator | None = None,
    scene: int | None = None,
) -> str:
    """Invoke an agent with full harness instrumentation.

    Returns the raw text output. Raises AgentCallFailed if all attempts fail.
    Every call appends:
      - 1× agent.started (attempt=1) or agent.retry (attempt>1)
      - 1× metric.emitted (always, even on failure)
      - 1× agent.completed or agent.failed
      - 0+ guardrail.violated (one per failed validator pass)
    """
    last_error: str = ""
    for attempt in range(1, max_attempts + 1):
        kind = "agent.started" if attempt == 1 else "agent.retry"
        append_event(project_id, AgentEvent(
            kind=kind, agent=agent, scene=scene, attempt=attempt,
            payload={"model": model, "tools": tools, "previous_error": last_error or None},
        ))

        try:
            with measure(agent, model, scene) as m:
                m["input_chars"] = len(prompt) + len(system)
                if tools is None:
                    output = run_text(prompt=prompt, system=system, model=model, timeout=timeout)
                else:
                    output = run_with_tools(
                        prompt=prompt, system=system, model=model,
                        tools=tools, add_dirs=add_dirs or [], timeout=timeout,
                    )
                m["output_chars"] = len(output)
        except Exception as e:
            last_error = f"subprocess error: {e}"
            append_event(project_id, AgentEvent(
                kind="metric.emitted", agent=agent, scene=scene, attempt=attempt,
                payload={"outcome": "error", "error": last_error[:500]},
            ))
            if attempt < max_attempts:
                time.sleep(_backoff(attempt))
                continue
            append_event(project_id, AgentEvent(
                kind="agent.failed", agent=agent, scene=scene, attempt=attempt,
                payload={"reason": "subprocess_exhausted", "error": last_error[:500]},
            ))
            raise AgentCallFailed(last_error)

        append_event(project_id, metric_event(agent, scene, m))

        if validator is None:
            append_event(project_id, AgentEvent(
                kind="agent.completed", agent=agent, scene=scene, attempt=attempt,
                payload={"output_chars": len(output)},
            ))
            return output

        ok, msg = validator(output)
        if ok:
            append_event(project_id, AgentEvent(
                kind="agent.completed", agent=agent, scene=scene, attempt=attempt,
                payload={"output_chars": len(output), "validation": "passed"},
            ))
            return output

        # Validator rejected — 12-Factor #9: compact error into next prompt
        last_error = msg
        append_event(project_id, AgentEvent(
            kind="guardrail.violated", agent=agent, scene=scene, attempt=attempt,
            payload={"validator_error": msg[:300]},
        ))
        # Augment the prompt for the next attempt with the error feedback
        prompt = (
            f"{prompt}\n\n--- PREVIOUS ATTEMPT FAILED VALIDATION ---\n"
            f"Error: {msg}\nFix your output and respond again. Do not apologize."
        )
        if attempt < max_attempts:
            time.sleep(_backoff(attempt))

    append_event(project_id, AgentEvent(
        kind="agent.failed", agent=agent, scene=scene, attempt=max_attempts,
        payload={"reason": "validator_exhausted", "error": last_error[:500]},
    ))
    raise AgentCallFailed(last_error)


def _backoff(attempt: int) -> float:
    """Exponential backoff: 1s, 2s, 4s, capped at 10s."""
    return min(2 ** (attempt - 1), 10)
