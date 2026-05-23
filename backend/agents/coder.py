"""Coder — writes ManimCE VoiceoverScene files from a beats spec.

The skill files (SKILL.md, api-cheatsheet.md, voiceover.py template,
narration.md, troubleshooting.md) are read with `Path.read_text()` and inlined
into the prompt — no Read/Glob/Grep tool loop. Compared to the previous
agentic version (which Read each file via tool calls, re-paying the system
prompt every turn) this is ~5-10x cheaper per scene.

Each scene receives the beats.json produced by the Beat Writer. The Coder must
emit exactly one `with self.voiceover(text=beat.text) as tracker:` block per
beat, in order. This is enforced by `voiceover_scene_well_formed` BEFORE we
spend a render attempt.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from harness.runner import call_agent
from harness.prompts import CODER_GENERATE, CODER_FIX, CODER_REVISE
from harness.guardrails import voiceover_scene_well_formed
from harness.graders import grade_scene_renderable, emit_grade
from tools.scene_utils import get_scene_name

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"
MAX_FIX_CYCLES = 2


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```(?:python)?\n?", "", text.strip())
    return re.sub(r"\n?```$", "", text).strip()


def _make_validator(expected_beats: int | None):
    def _v(raw: str) -> tuple[bool, str]:
        return voiceover_scene_well_formed(_strip_fences(raw), expected_beats)
    return _v


def _structure_validator(raw: str) -> tuple[bool, str]:
    return voiceover_scene_well_formed(_strip_fences(raw), expected_beats=None)


def _load_beats(beats_file: Path | None) -> tuple[str, int]:
    if beats_file and beats_file.exists():
        try:
            data = json.loads(beats_file.read_text(encoding="utf-8"))
            count = len(data) if isinstance(data, list) else 1
            return json.dumps(data, ensure_ascii=False, indent=2), count
        except json.JSONDecodeError:
            pass
    fallback = [{"id": "1.1", "text": "Animation without narration.",
                 "anim_hint": "The full scene as described.", "duration_s_est": 5.0}]
    return json.dumps(fallback, ensure_ascii=False, indent=2), 1


def _read_skill_files() -> dict[str, str]:
    """Read all skill files the Coder needs. Cached per process via lru_cache."""
    return _SKILL_CACHE


def _build_skill_cache() -> dict[str, str]:
    return {
        "skill_md": (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8"),
        "cheatsheet_md": (SKILL_ROOT / "references" / "api-cheatsheet.md").read_text(encoding="utf-8"),
        "troubleshooting_md": (SKILL_ROOT / "references" / "troubleshooting.md").read_text(encoding="utf-8"),
        "narration_md": (SKILL_ROOT / "references" / "narration.md").read_text(encoding="utf-8"),
        "voiceover_template": (SKILL_ROOT / "templates" / "voiceover.py").read_text(encoding="utf-8"),
    }


# Loaded lazily at first call so a missing file surfaces a clean error.
_SKILL_CACHE: dict[str, str] | None = None


def _skill() -> dict[str, str]:
    global _SKILL_CACHE
    if _SKILL_CACHE is None:
        _SKILL_CACHE = _build_skill_cache()
    return _SKILL_CACHE


def _maybe_3b1b_style(text: str) -> str:
    """Include 3Blue1Brown palette guide only when the scene mentions it."""
    lower = text.lower()
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
    project_id: str, scene_number: int, scene_desc: str,
    outline: str, project_path: Path, scene_name: str | None = None,
    plugin_context: str = "", lang: str = "es",
    beats_file: Path | None = None,
) -> tuple[Path, str]:
    if scene_name is None:
        scene_name = f"Scene{scene_number:02d}"
    scene_file = project_path / "scenes" / f"scene_{scene_number:02d}.py"
    scene_file.parent.mkdir(parents=True, exist_ok=True)
    beats_json, expected_beats = _load_beats(beats_file)
    skill = _skill()
    style_section = _maybe_3b1b_style(scene_desc + " " + outline)

    raw = call_agent(
        project_id=project_id, agent="coder", scene=scene_number,
        prompt=CODER_GENERATE.render(
            plugin_context=plugin_context,
            lang=lang, outline=outline, scene_desc=scene_desc,
            scene_name=scene_name, beats_json=beats_json,
            style_section=style_section,
            **skill,
        ),
        system=CODER_GENERATE.render_system(scene_name=scene_name, lang=lang),
        model="opus",
        tools=None,
        timeout=240, max_attempts=3, validator=_make_validator(expected_beats),
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
        current = scene_file.read_text(encoding="utf-8")
        fixed = call_agent(
            project_id=project_id, agent="coder.fix", scene=scene_number,
            prompt=CODER_FIX.render(
                code=current, error_msg=grade.details, scene_name=scene_name,
                troubleshooting_md=skill["troubleshooting_md"],
                cheatsheet_md=skill["cheatsheet_md"],
            ),
            system=CODER_FIX.system,
            model="opus",
            tools=None,
            timeout=240, max_attempts=2, validator=_structure_validator,
        )
        scene_file.write_text(_strip_fences(fixed), encoding="utf-8")
    return scene_file, "failed"


def revise(
    project_id: str, scene_number: int, scene_file: Path,
    feedback: str, project_path: Path,
    lang: str = "es", plugin_context: str = "",
    beats_file: Path | None = None,
) -> tuple[Path, str]:
    """User-driven revision: apply free-text feedback, keep beats intact."""
    scene_name = get_scene_name(scene_file)
    current_code = scene_file.read_text(encoding="utf-8") if scene_file.exists() else ""
    beats_json, expected_beats = _load_beats(beats_file)
    skill = _skill()

    fixed = call_agent(
        project_id=project_id, agent="coder.revise", scene=scene_number,
        prompt=CODER_REVISE.render(
            plugin_context=plugin_context,
            lang=lang, scene_name=scene_name, beats_json=beats_json,
            current_code=current_code, user_feedback=feedback,
            skill_md=skill["skill_md"],
            troubleshooting_md=skill["troubleshooting_md"],
            cheatsheet_md=skill["cheatsheet_md"],
        ),
        system=CODER_REVISE.render_system(scene_name=scene_name, lang=lang),
        model="opus",
        tools=None,
        timeout=240, max_attempts=2, validator=_make_validator(expected_beats),
    )
    scene_file.write_text(_strip_fences(fixed), encoding="utf-8")

    for cycle in range(1, MAX_FIX_CYCLES + 1):
        grade = grade_scene_renderable(scene_file, scene_name)
        emit_grade(project_id, "coder.revise", scene_number, grade)
        if grade.passed:
            return scene_file, "ok"
        if cycle == MAX_FIX_CYCLES:
            break
        current = scene_file.read_text(encoding="utf-8")
        fixed = call_agent(
            project_id=project_id, agent="coder.fix", scene=scene_number,
            prompt=CODER_FIX.render(
                code=current, error_msg=grade.details, scene_name=scene_name,
                troubleshooting_md=skill["troubleshooting_md"],
                cheatsheet_md=skill["cheatsheet_md"],
            ),
            system=CODER_FIX.system,
            model="opus",
            tools=None,
            timeout=240, max_attempts=2, validator=_structure_validator,
        )
        scene_file.write_text(_strip_fences(fixed), encoding="utf-8")
    return scene_file, "failed"


def fix_with_feedback(project_id: str, scene_file: Path, qa_notes: str, scene_number: int) -> None:
    """Used by orchestrator's QA cycle to apply visual feedback to a scene.

    The outer QA loop iterates already, so retry once here at most.
    """
    scene_name = get_scene_name(scene_file)
    current = scene_file.read_text(encoding="utf-8")
    skill = _skill()
    fixed = call_agent(
        project_id=project_id, agent="coder.fix", scene=scene_number,
        prompt=CODER_FIX.render(
            code=current,
            error_msg=f"Visual QA feedback:\n{qa_notes}", scene_name=scene_name,
            troubleshooting_md=skill["troubleshooting_md"],
            cheatsheet_md=skill["cheatsheet_md"],
        ),
        system=CODER_FIX.system,
        model="opus",
        tools=None,
        timeout=240, max_attempts=1, validator=_structure_validator,
    )
    scene_file.write_text(_strip_fences(fixed), encoding="utf-8")
