"""Planner agent: produces the scene outline from the video idea."""
from __future__ import annotations
from pathlib import Path
import anthropic

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"

SYSTEM = """\
You are a Manim video planner. Your job is to turn a video idea into a clear, structured outline
of 3-7 scenes that a Manim animator can implement one by one.

Rules:
- Each scene entry must have: scene number, title, duration estimate (seconds), visual description,
  and the mathematical/conceptual key moment to highlight.
- Verify any formulas or facts mentioned.
- Write in the language specified (default: Spanish).
- Output a Markdown document — no JSON, just clear prose sections per scene.
- Keep total duration within the target length.
"""


def run(
    client: anthropic.Anthropic,
    idea: str,
    project_path: Path,
    lang: str = "es",
    audience: str = "general",
    target_length: str = "60s",
) -> str:
    skill_content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Skill context:\n{skill_content}\n\n"
                    f"Video idea: {idea}\n"
                    f"Language: {lang}\n"
                    f"Audience: {audience}\n"
                    f"Target length: {target_length}\n\n"
                    "Write the scene outline."
                ),
            }
        ],
    )
    outline = response.content[0].text.strip()
    (project_path / "outline.md").write_text(outline, encoding="utf-8")
    return outline
