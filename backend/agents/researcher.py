"""Researcher agent: searches plugins.manim.community and the web for useful Manim plugins."""
from __future__ import annotations
import json
from pathlib import Path
import anthropic

SYSTEM = """\
You are a Manim research assistant. Given a video idea, search the Manim Community plugin registry
(https://plugins.manim.community/) and the general web for Manim Community Edition plugins
that would help produce the best animation for this specific topic.

For each plugin you find that seems relevant:
- name: pip package name
- description: one sentence on what it adds
- repo: GitHub URL
- relevance: why it helps for this specific idea

Return a JSON array of plugin objects. If nothing relevant is found, return an empty array [].
Only include plugins you are confident exist and are installable via pip.
"""


def run(client: anthropic.Anthropic, idea: str, project_path: Path) -> list[dict]:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Video idea: {idea}\n\nFind relevant Manim plugins."}],
    )
    raw = response.content[0].text.strip()
    # Extract JSON from the response
    start = raw.find("[")
    end = raw.rfind("]") + 1
    plugins = json.loads(raw[start:end]) if start != -1 else []
    (project_path / "plugins_proposal.json").write_text(
        json.dumps(plugins, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return plugins
