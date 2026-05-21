"""Curator — extracts learnings + proposes skill updates as reviewable diffs."""
from __future__ import annotations
import json
import re
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import CURATOR
from tools.skill_diff import generate_diff

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"


def _validator(raw: str) -> tuple[bool, str]:
    if "--- LEARNINGS ---" not in raw:
        return False, "missing --- LEARNINGS --- section"
    return True, "ok"


def run(project_id: str, project_path: Path) -> dict:
    outline = (project_path / "outline.md").read_text(encoding="utf-8") if (project_path / "outline.md").exists() else ""
    feedback_path = project_path / "feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.exists() else {}
    qa_notes = []
    for qa_file in sorted((project_path / "renders").glob("*/qa_notes.md")):
        qa_notes.append(f"### {qa_file.parent.name}\n{qa_file.read_text(encoding='utf-8')}")

    skill_md     = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    troubleshoot = (SKILL_ROOT / "references" / "troubleshooting.md").read_text(encoding="utf-8")

    try:
        raw = call_agent(
            project_id=project_id, agent="curator",
            prompt=CURATOR.render(
                outline=outline, qa_notes="\n\n".join(qa_notes) or "No QA notes.",
                feedback=json.dumps(feedback, ensure_ascii=False, indent=2),
                skill_md=skill_md, troubleshoot=troubleshoot,
            ),
            system=CURATOR.system, model="sonnet",
            timeout=180, max_attempts=2, validator=_validator,
        )
    except AgentCallFailed:
        return {"learnings": "", "patches": {}}

    learnings_dir = project_path / "learnings"
    learnings_dir.mkdir(exist_ok=True)

    sections = re.split(r"---\s*(LEARNINGS|FILE:\s*[\w/.]+)\s*---", raw)
    patches: dict[str, dict] = {}
    learnings_text = ""
    i = 0
    while i < len(sections):
        s = sections[i].strip()
        if s == "LEARNINGS" and i + 1 < len(sections):
            learnings_text = sections[i + 1].strip()
            i += 2
        elif s.startswith("FILE:") and i + 1 < len(sections):
            file_rel = s[5:].strip()
            new_content = sections[i + 1].strip()
            diff = generate_diff(file_rel, new_content)
            patches[file_rel] = {"new_content": new_content, "diff": diff}
            i += 2
        else:
            i += 1

    if learnings_text:
        (learnings_dir / "notes.md").write_text(learnings_text, encoding="utf-8")
    all_diffs = "\n\n".join(
        f"### {k}\n```diff\n{v['diff']}\n```" for k, v in patches.items() if v["diff"]
    )
    if all_diffs:
        (learnings_dir / "skill_patch.diff").write_text(all_diffs, encoding="utf-8")

    return {"learnings": learnings_text, "patches": {k: v["diff"] for k, v in patches.items()}}
