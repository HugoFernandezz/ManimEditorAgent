"""Curator — extracts learnings + proposes skill updates as reviewable diffs.

The current skill files (SKILL.md + troubleshooting.md) are read with
`Path.read_text()` at call time and inlined into the prompt — no tools loop.
This still guarantees the agent sees the freshest content (any patch applied
earlier in the session is on disk).
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import CURATOR
from tools.skill_diff import generate_diff

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"

_SECTION_RE = re.compile(r"---\s*(LEARNINGS|FILE:\s*[\w/.]+)\s*---")


def _validator(raw: str) -> tuple[bool, str]:
    if "--- LEARNINGS ---" not in raw:
        return False, "missing --- LEARNINGS --- section"
    return True, "ok"


def _read_qa_notes(project_path: Path) -> str:
    notes = []
    for qa_file in sorted((project_path / "renders").glob("*/qa_notes.md")):
        notes.append(f"### {qa_file.parent.name}\n{qa_file.read_text(encoding='utf-8')}")
    return "\n\n".join(notes) or "No QA notes."


def run(project_id: str, project_path: Path) -> dict:
    outline_path = project_path / "outline.md"
    outline = outline_path.read_text(encoding="utf-8") if outline_path.exists() else ""

    feedback_path = project_path / "feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.exists() else {}

    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    troubleshooting_md = (SKILL_ROOT / "references" / "troubleshooting.md").read_text(encoding="utf-8")

    try:
        raw = call_agent(
            project_id=project_id, agent="curator",
            prompt=CURATOR.render(
                outline=outline,
                qa_notes=_read_qa_notes(project_path),
                feedback=json.dumps(feedback, ensure_ascii=False, indent=2),
                skill_md=skill_md,
                troubleshooting_md=troubleshooting_md,
            ),
            system=CURATOR.system,
            model="sonnet",
            tools=None,
            timeout=240, max_attempts=2, validator=_validator,
        )
    except AgentCallFailed:
        return {"learnings": "", "patches": {}}

    learnings_dir = project_path / "learnings"
    learnings_dir.mkdir(exist_ok=True)
    learnings_text, patches = _parse_curator_output(raw)

    if learnings_text:
        (learnings_dir / "notes.md").write_text(learnings_text, encoding="utf-8")
    all_diffs = "\n\n".join(
        f"### {k}\n```diff\n{v['diff']}\n```" for k, v in patches.items() if v["diff"]
    )
    if all_diffs:
        (learnings_dir / "skill_patch.diff").write_text(all_diffs, encoding="utf-8")

    return {"learnings": learnings_text, "patches": {k: v["diff"] for k, v in patches.items()}}


def _parse_curator_output(raw: str) -> tuple[str, dict[str, dict]]:
    """Split the agent's response into a learnings text and per-file patches."""
    sections = _SECTION_RE.split(raw)
    learnings_text = ""
    patches: dict[str, dict] = {}
    i = 0
    while i < len(sections):
        s = sections[i].strip()
        next_body = sections[i + 1].strip() if i + 1 < len(sections) else ""
        if s == "LEARNINGS":
            learnings_text = next_body
            i += 2
        elif s.startswith("FILE:"):
            file_rel = s[5:].strip()
            diff = generate_diff(file_rel, next_body)
            patches[file_rel] = {"new_content": next_body, "diff": diff}
            i += 2
        else:
            i += 1
    return learnings_text, patches
