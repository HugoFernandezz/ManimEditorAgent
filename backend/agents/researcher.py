"""Researcher agent — searches plugins.manim.community for the video idea.

Refactored to use the harness layer:
  - Versioned prompt (harness.prompts.RESEARCHER)
  - call_agent with retry + backoff + validator (harness.runner)
  - Structured guardrail on output (harness.guardrails.plugins_proposal_valid)
  - All events persisted to the project event log (harness.store)

The agent file itself stays tiny — that's the point.
"""
from __future__ import annotations
import json
from pathlib import Path

from harness.runner import call_agent, AgentCallFailed
from harness.guardrails import extract_json_array, plugins_proposal_valid
from harness.prompts import RESEARCHER


def _validator(raw: str) -> tuple[bool, str]:
    ok, parsed = extract_json_array(raw)
    if not ok:
        return False, str(parsed)
    return plugins_proposal_valid(parsed)


def run(project_id: str, idea: str, project_path: Path) -> list[dict]:
    try:
        raw = call_agent(
            project_id=project_id,
            agent="researcher",
            prompt=RESEARCHER.render(idea=idea),
            system=RESEARCHER.system,
            model="sonnet",
            tools="WebSearch,WebFetch",
            timeout=120,
            max_attempts=3,
            validator=_validator,
        )
    except AgentCallFailed:
        # Researcher is non-critical — degrade gracefully to empty plugin list
        (project_path / "plugins_proposal.json").write_text("[]", encoding="utf-8")
        return []

    _, plugins = extract_json_array(raw)
    (project_path / "plugins_proposal.json").write_text(
        json.dumps(plugins, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return plugins
