"""Planner — outline of 3-7 scenes from the idea.

Skill content (SKILL.md and optionally 3b1b-style.md) is read with
`Path.read_text()` and inlined into the prompt, so the agent runs without
the Read/Glob/Grep tool loop. This cuts token usage by ~5-10x compared to
the previous agentic version that fetched files via tool calls.
"""
from __future__ import annotations
from pathlib import Path
from harness.runner import call_agent
from harness.prompts import PLANNER
from harness.graders import grade_outline_structure, grade_outline_quality_llm, emit_grade

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"


def _structural_validator(raw: str) -> tuple[bool, str]:
    if len(raw) < 200:
        return False, "outline too short"
    if not any(k in raw for k in ("Scene", "Escena", "scene", "escena")):
        return False, "no scene markers in outline"
    return True, "ok"


def _maybe_3b1b_style(idea: str) -> str:
    """Include the 3Blue1Brown style guide only when the idea mentions it."""
    lower = idea.lower()
    if "3b1b" not in lower and "3blue1brown" not in lower and "blue1brown" not in lower:
        return ""
    style_path = SKILL_ROOT / "references" / "3b1b-style.md"
    if not style_path.exists():
        return ""
    return (
        "\n\n--- SKILL: references/3b1b-style.md ---\n"
        + style_path.read_text(encoding="utf-8")
    )


def run(
    project_id: str, idea: str, project_path: Path,
    lang: str = "es", audience: str = "general", target_length: str = "60s",
    plugin_context: str = "",
) -> str:
    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    style_section = _maybe_3b1b_style(idea)

    outline = call_agent(
        project_id=project_id, agent="planner",
        prompt=PLANNER.render(
            plugin_context=plugin_context,
            idea=idea, lang=lang, audience=audience, target_length=target_length,
            skill_md=skill_md, style_section=style_section,
        ),
        system=PLANNER.system,
        model="sonnet",
        tools=None,
        timeout=180, max_attempts=3, validator=_structural_validator,
    )
    (project_path / "outline.md").write_text(outline, encoding="utf-8")

    g1 = grade_outline_structure(outline)
    emit_grade(project_id, "planner", None, g1)
    if g1.passed:
        g2 = grade_outline_quality_llm(idea, outline, project_id)
        emit_grade(project_id, "planner", None, g2)
    return outline
