"""Planner agent: produces the scene outline from the video idea."""
from __future__ import annotations
from pathlib import Path
from claude_runner import run_text

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"

SYSTEM = """\
You are a Manim video planner. Turn a video idea into a structured outline of 3-7 scenes
that a Manim animator can implement one by one.

Each scene entry must include: scene number, title, duration estimate (seconds),
visual description, and the key mathematical/conceptual moment to highlight.
Verify any formulas or facts. Write in the specified language.
Output a Markdown document — one section per scene, no JSON.
Keep total duration within the target length.
"""


def run(
    idea: str,
    project_path: Path,
    lang: str = "es",
    audience: str = "general",
    target_length: str = "60s",
) -> str:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    prompt = (
        f"Skill context:\n{skill}\n\n"
        f"Video idea: {idea}\n"
        f"Language: {lang}\n"
        f"Audience: {audience}\n"
        f"Target length: {target_length}\n\n"
        "Write the scene outline."
    )
    outline = run_text(prompt, system=SYSTEM, model="sonnet", timeout=120)
    (project_path / "outline.md").write_text(outline, encoding="utf-8")
    return outline
