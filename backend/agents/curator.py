"""Curator agent: extracts learnings from a completed video and proposes skill updates."""
from __future__ import annotations
import json
from pathlib import Path
import anthropic
from tools.skill_diff import generate_diff

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"

SYSTEM = """\
You are a Manim knowledge curator. After a video is produced and approved by the user,
you extract the most valuable learnings from the process to improve the skill documentation.

You receive:
- The video outline
- QA notes for each scene (what issues were found and fixed)
- User feedback on the final video
- The current SKILL.md content

Your task:
1. Write a brief "learnings.md" summary (what went well, what errors occurred and how they were fixed,
   patterns to remember). Keep it under 300 words.
2. Propose targeted updates to ONE or TWO skill files if genuinely warranted:
   - Prefer updating "references/troubleshooting.md" to add new error→fix pairs found.
   - Only update SKILL.md if a new anti-pattern or rule is strongly justified.
   - Output the FULL updated content of each file you want to change.

Format:
--- LEARNINGS ---
<learnings.md content>

--- FILE: references/troubleshooting.md ---
<full updated content>

--- FILE: SKILL.md ---
<full updated content if needed, else omit this block>
"""


def run(
    client: anthropic.Anthropic,
    project_path: Path,
) -> dict:
    outline = (project_path / "outline.md").read_text(encoding="utf-8") if (project_path / "outline.md").exists() else ""
    feedback_path = project_path / "feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8")) if feedback_path.exists() else {}

    qa_notes = []
    for qa_file in sorted((project_path / "renders").glob("*/qa_notes.md")):
        qa_notes.append(f"### {qa_file.parent.name}\n{qa_file.read_text(encoding='utf-8')}")
    qa_text = "\n\n".join(qa_notes) or "No QA notes."

    skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    troubleshoot = (SKILL_ROOT / "references" / "troubleshooting.md").read_text(encoding="utf-8")

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=6000,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"OUTLINE:\n{outline}\n\n"
                    f"QA NOTES:\n{qa_text}\n\n"
                    f"USER FEEDBACK:\n{json.dumps(feedback, ensure_ascii=False, indent=2)}\n\n"
                    f"CURRENT SKILL.md:\n{skill_md}\n\n"
                    f"CURRENT troubleshooting.md:\n{troubleshoot}\n\n"
                    "Extract learnings and propose skill updates."
                ),
            }
        ],
    )
    raw = resp.content[0].text.strip()

    learnings_dir = project_path / "learnings"
    learnings_dir.mkdir(exist_ok=True)

    # Parse sections
    import re
    sections = re.split(r"---\s*(LEARNINGS|FILE:\s*[\w/.]+)\s*---", raw)
    patches = {}
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

    return {
        "learnings": learnings_text,
        "patches": {k: v["diff"] for k, v in patches.items()},
    }
