"""Coder agent: writes a Manim Scene file for a given scene description."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path
from claude_runner import run_text

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


SYSTEM = """\
You are an expert ManimCE animator. Write clean, correct Manim Community Edition Python scenes.
Follow every rule in the provided skill context, especially the anti-patterns list.
Use the template as your starting point — modify it, do not write from scratch.
Output ONLY the Python code — no explanation, no markdown fences.
The class name must be exactly the SceneName specified.
"""


def run(
    scene_number: int,
    scene_desc: str,
    outline: str,
    project_path: Path,
    scene_name: str | None = None,
) -> tuple[Path, str]:
    skill_ctx = _skill_context()
    template = _pick_template(scene_desc)
    if scene_name is None:
        scene_name = f"Scene{scene_number:02d}"

    scene_file = project_path / "scenes" / f"scene_{scene_number:02d}.py"

    code = _generate(skill_ctx, template, scene_desc, outline, scene_name)
    scene_file.write_text(code, encoding="utf-8")

    for attempt in range(1, MAX_FIX_CYCLES + 1):
        ok, error_msg = _render_verify(scene_file, scene_name)
        if ok:
            return scene_file, "ok"
        if attempt == MAX_FIX_CYCLES:
            break
        code = _fix(skill_ctx, code, error_msg, scene_name)
        scene_file.write_text(code, encoding="utf-8")

    return scene_file, "failed"


def _generate(skill_ctx, template, scene_desc, outline, scene_name) -> str:
    prompt = (
        f"SKILL CONTEXT:\n{skill_ctx}\n\n"
        f"TEMPLATE TO ADAPT:\n{template}\n\n"
        f"FULL OUTLINE (context):\n{outline}\n\n"
        f"SCENE DESCRIPTION:\n{scene_desc}\n\n"
        f"SceneName: {scene_name}\n\n"
        "Write the complete scene .py file."
    )
    return _strip_fences(run_text(prompt, system=SYSTEM, model="opus", timeout=180))


def _fix(skill_ctx, code, error_msg, scene_name) -> str:
    prompt = (
        f"SKILL CONTEXT (troubleshooting):\n{skill_ctx}\n\n"
        f"CURRENT CODE:\n{code}\n\n"
        f"RENDER ERROR:\n{error_msg}\n\n"
        f"SceneName must remain: {scene_name}\n\n"
        "Fix the code. Output only the corrected Python."
    )
    return _strip_fences(run_text(prompt, system=SYSTEM, model="opus", timeout=180))


def _render_verify(scene_file: Path, scene_name: str) -> tuple[bool, str]:
    import sys
    result = subprocess.run(
        [sys.executable, str(RENDER_VERIFY), str(scene_file), scene_name],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, ""
    return False, (result.stdout + result.stderr).strip()


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:python)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()
