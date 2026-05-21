"""Researcher agent: searches plugins.manim.community and the web for useful Manim plugins."""
from __future__ import annotations
import json
from pathlib import Path
from claude_runner import run_with_tools

SYSTEM = """\
You are a Manim research assistant. Search the Manim Community plugin registry
(https://plugins.manim.community/) and the web for Manim Community Edition plugins
relevant to the given video idea.

For each plugin found, return a JSON array with objects containing:
  name (pip package name), description (one sentence), repo (GitHub URL), relevance (why it helps).

Return ONLY a valid JSON array. If nothing relevant, return [].
Only include plugins you confirmed exist and are pip-installable.
"""


def run(idea: str, project_path: Path) -> list[dict]:
    response = run_with_tools(
        prompt=f"Video idea: {idea}\n\nSearch for relevant Manim plugins and return a JSON array.",
        system=SYSTEM,
        model="sonnet",
        tools="WebSearch,WebFetch",
        timeout=120,
    )
    start = response.find("[")
    end = response.rfind("]") + 1
    plugins: list[dict] = json.loads(response[start:end]) if start != -1 else []
    (project_path / "plugins_proposal.json").write_text(
        json.dumps(plugins, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return plugins
