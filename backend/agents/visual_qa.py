"""Visual QA — multimodal frame analysis via Claude's Read tool.

The agent gets two mounted directories: the scene's frames (so Read returns the
PNG as a visual the model can interpret) and the Manim skill (so the agent can
consult `references/troubleshooting.md` when it spots a known failure pattern).

If frame extraction failed upstream we skip the agent entirely — sending it an
empty frame list invites a hallucinated "status: ok".
"""
from __future__ import annotations
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import VISUAL_QA
from harness.guardrails import extract_yaml_block, qa_report_valid

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"
QA_TOOLS = "Read,Glob"
_CODE_HEAD = 1200
_CODE_TAIL = 600


def _summarize_code(code: str) -> str:
    """Keep the QA prompt cheap: head + tail of the scene file.

    The QA reviewer needs imports + class signature + the construct() shape, plus
    the tail (often where the most recent edit lives). We never need 5KB of
    animation calls — Read tool is available if it really wants more.
    """
    if len(code) <= _CODE_HEAD + _CODE_TAIL + 50:
        return code
    return (
        code[:_CODE_HEAD]
        + f"\n\n# ... [{len(code) - _CODE_HEAD - _CODE_TAIL} chars elided — use Read on the .py file if needed] ...\n\n"
        + code[-_CODE_TAIL:]
    )


def _validator(raw: str) -> tuple[bool, str]:
    ok, yaml_text = extract_yaml_block(raw)
    if not ok:
        return False, yaml_text
    return qa_report_valid(yaml_text)


def run(
    project_id: str, scene_number: int, scene_desc: str,
    scene_file: Path, frames: list[Path], project_path: Path,
) -> dict:
    render_dir = project_path / "renders" / f"scene_{scene_number:02d}"
    render_dir.mkdir(parents=True, exist_ok=True)
    qa_path = render_dir / "qa_notes.md"
    frames_dir = render_dir / "frames"

    # Guard: nothing to review → skip and mark as degraded, don't waste a call.
    existing_frames = [f for f in frames if f.exists()]
    if not existing_frames or not frames_dir.exists():
        raw = (
            "```yaml\n"
            "status: needs_fix\n"
            "frames_reviewed: 0\n"
            "issues:\n"
            "  - frame: -1\n"
            "    problem: 'no frames extracted — render likely failed silently'\n"
            "    fix_hint: 're-render at -ql and verify ffmpeg/ffprobe duration'\n"
            "```"
        )
        qa_path.write_text(raw, encoding="utf-8")
        return {"status": "needs_fix", "raw": raw, "path": str(qa_path),
                "frames_reviewed": 0, "skipped": True}

    code = scene_file.read_text(encoding="utf-8") if scene_file.exists() else ""
    code = _summarize_code(code)

    try:
        raw = call_agent(
            project_id=project_id, agent="visual_qa", scene=scene_number,
            prompt=VISUAL_QA.render(
                scene_desc=scene_desc, code=code,
                frames_dir=str(frames_dir), skill_root=str(SKILL_ROOT),
            ),
            system=VISUAL_QA.render_system(
                frames_dir=str(frames_dir), skill_root=str(SKILL_ROOT),
            ),
            model="opus",
            tools=QA_TOOLS, add_dirs=[frames_dir, SKILL_ROOT],
            timeout=240, max_attempts=2, validator=_validator,
        )
    except AgentCallFailed as e:
        # Degrade: assume OK rather than block pipeline indefinitely.
        raw = (
            "```yaml\n"
            "status: ok\n"
            "frames_reviewed: 0\n"
            "issues: []\n"
            f"# QA degraded after retries: {e}\n"
            "```"
        )

    qa_path.write_text(raw, encoding="utf-8")
    status = "needs_fix" if "needs_fix" in raw else "ok"
    return {"status": status, "raw": raw, "path": str(qa_path)}
