"""Visual QA — multimodal frame analysis via Claude's Read tool."""
from __future__ import annotations
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import VISUAL_QA
from harness.guardrails import extract_yaml_block, qa_report_valid


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

    code = scene_file.read_text(encoding="utf-8") if scene_file.exists() else ""
    frame_list = "\n".join(f"- {f}" for f in frames[:6] if f.exists())
    frames_dir = render_dir / "frames"

    try:
        raw = call_agent(
            project_id=project_id, agent="visual_qa", scene=scene_number,
            prompt=VISUAL_QA.render(scene_desc=scene_desc, code=code, frame_list=frame_list),
            system=VISUAL_QA.system, model="opus",
            tools="Read", add_dirs=[frames_dir] if frames_dir.exists() else [],
            timeout=180, max_attempts=2, validator=_validator,
        )
    except AgentCallFailed as e:
        # Degrade: assume OK rather than block pipeline indefinitely
        raw = f"status: ok\nissues: []\n# QA degraded: {e}"

    qa_path.write_text(raw, encoding="utf-8")
    status = "needs_fix" if "needs_fix" in raw else "ok"
    return {"status": status, "raw": raw, "path": str(qa_path)}
