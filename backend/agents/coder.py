"""Coder — writes ManimCE scene file, with embedded verify+fix loop."""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import CODER_GENERATE, CODER_FIX
from harness.guardrails import python_code_well_formed
from harness.graders import grade_scene_renderable, emit_grade

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"
RENDER_VERIFY = SKILL_ROOT / "scripts" / "render_verify.py"
MAX_FIX_CYCLES = 3


def _skill_context() -> str:
    return "\n\n---\n\n".join([
        (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8"),
        (SKILL_ROOT / "references" / "api-cheatsheet.md").read_text(encoding="utf-8"),
        (SKILL_ROOT / "references" / "troubleshooting.md").read_text(encoding="utf-8"),
    ])


def _pick_template(scene_desc: str) -> str:
    desc = scene_desc.lower()
    if any(k in desc for k in ["3d", "surface", "parametric", "three"]):
        tpl = "threed.py"
    elif any(k in desc for k in ["equation", "formula", "latex", "derive", "proof"]):
        tpl = "math.py"
    else:
        tpl = "basic.py"
    return (SKILL_ROOT / "templates" / tpl).read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:python)?\n?", "", text.strip())
    return re.sub(r"\n?```$", "", text).strip()


def _code_validator(raw: str) -> tuple[bool, str]:
    code = _strip_fences(raw)
    return python_code_well_formed(code)


def run(
    project_id: str, scene_number: int, scene_desc: str,
    outline: str, project_path: Path, scene_name: str | None = None,
) -> tuple[Path, str]:
    skill_ctx = _skill_context()
    template = _pick_template(scene_desc)
    if scene_name is None:
        scene_name = f"Scene{scene_number:02d}"
    scene_file = project_path / "scenes" / f"scene_{scene_number:02d}.py"

    # Generate
    raw = call_agent(
        project_id=project_id, agent="coder", scene=scene_number,
        prompt=CODER_GENERATE.render(
            skill_ctx=skill_ctx, template=template, outline=outline,
            scene_desc=scene_desc, scene_name=scene_name,
        ),
        system=CODER_GENERATE.system, model="opus",
        timeout=180, max_attempts=3, validator=_code_validator,
    )
    scene_file.write_text(_strip_fences(raw), encoding="utf-8")

    # Verify + fix loop (embedded grader — Anthropic verification loops)
    for cycle in range(1, MAX_FIX_CYCLES + 1):
        grade = grade_scene_renderable(scene_file, scene_name)
        emit_grade(project_id, "coder", scene_number, grade)
        if grade.passed:
            return scene_file, "ok"
        if cycle == MAX_FIX_CYCLES:
            break
        # Compact error into next prompt (12-Factor #9)
        current = scene_file.read_text(encoding="utf-8")
        fixed = call_agent(
            project_id=project_id, agent="coder.fix", scene=scene_number,
            prompt=CODER_FIX.render(
                skill_ctx=skill_ctx, code=current,
                error_msg=grade.details, scene_name=scene_name,
            ),
            system=CODER_FIX.system, model="opus",
            timeout=180, max_attempts=2, validator=_code_validator,
        )
        scene_file.write_text(_strip_fences(fixed), encoding="utf-8")
    return scene_file, "failed"


# Backward compat alias (used by orchestrator._apply_qa_fix in legacy code path)
def fix_with_feedback(project_id: str, scene_file: Path, qa_notes: str, scene_number: int) -> None:
    skill_ctx = _skill_context()
    scene_name = _extract_scene_name(scene_file)
    current = scene_file.read_text(encoding="utf-8")
    fixed = call_agent(
        project_id=project_id, agent="coder.fix", scene=scene_number,
        prompt=CODER_FIX.render(
            skill_ctx=skill_ctx, code=current,
            error_msg=f"Visual QA feedback:\n{qa_notes}", scene_name=scene_name,
        ),
        system=CODER_FIX.system, model="opus",
        timeout=180, max_attempts=2, validator=_code_validator,
    )
    scene_file.write_text(_strip_fences(fixed), encoding="utf-8")


def _extract_scene_name(scene_file: Path) -> str:
    m = re.search(r"class\s+(Scene\w*)\s*\(", scene_file.read_text(encoding="utf-8"))
    return m.group(1) if m else "Scene"
