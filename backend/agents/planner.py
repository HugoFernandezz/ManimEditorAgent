"""Planner — outline of 3-7 scenes from the idea."""
from __future__ import annotations
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import PLANNER
from harness.graders import grade_outline_structure, grade_outline_quality_llm, emit_grade

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"


def _structural_validator(raw: str) -> tuple[bool, str]:
    """Quick structural check inside the retry loop — keeps bad outputs out
    of the grading stage, where they'd waste a judge call."""
    if len(raw) < 200:
        return False, "outline too short"
    if "Scene" not in raw and "Escena" not in raw and "scene" not in raw and "escena" not in raw:
        return False, "no scene markers in outline"
    return True, "ok"


def run(
    project_id: str, idea: str, project_path: Path,
    lang: str = "es", audience: str = "general", target_length: str = "60s",
) -> str:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    outline = call_agent(
        project_id=project_id, agent="planner",
        prompt=PLANNER.render(skill=skill, idea=idea, lang=lang,
                              audience=audience, target_length=target_length),
        system=PLANNER.system, model="sonnet",
        timeout=120, max_attempts=3, validator=_structural_validator,
    )
    (project_path / "outline.md").write_text(outline, encoding="utf-8")

    # Cascade graders (Anthropic): cheap deterministic first, then expensive LLM judge
    g1 = grade_outline_structure(outline)
    emit_grade(project_id, "planner", None, g1)
    if g1.passed:
        g2 = grade_outline_quality_llm(idea, outline, project_id)
        emit_grade(project_id, "planner", None, g2)
    return outline
