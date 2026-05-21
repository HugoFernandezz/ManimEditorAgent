"""Generate a unified diff of proposed changes to skill files."""
from __future__ import annotations
import difflib
from pathlib import Path


SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"


def generate_diff(file_rel: str, new_content: str) -> str:
    """Return a unified diff string between the current skill file and new_content."""
    target = SKILL_ROOT / file_rel
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_rel}",
            tofile=f"b/{file_rel}",
        )
    )
    return "".join(diff_lines)


def apply_hunk(file_rel: str, hunk_patch: str) -> None:
    """Apply a single unified-diff hunk to the skill file."""
    target = SKILL_ROOT / file_rel
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    # Parse the hunk and apply it line-by-line
    result_lines = _apply_patch(original.splitlines(keepends=True), hunk_patch)
    target.write_text("".join(result_lines), encoding="utf-8")


def _apply_patch(original: list[str], patch: str) -> list[str]:
    lines = patch.splitlines(keepends=True)
    result = list(original)
    offset = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("@@"):
            # Parse @@ -start,count +start,count @@
            import re
            m = re.search(r"-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?", line)
            if not m:
                i += 1
                continue
            orig_start = int(m.group(1)) - 1
            i += 1
            pos = orig_start + offset
            removes, adds = [], []
            while i < len(lines) and not lines[i].startswith("@@"):
                l = lines[i]
                if l.startswith("-"):
                    removes.append(l[1:])
                elif l.startswith("+"):
                    adds.append(l[1:])
                i += 1
            result[pos : pos + len(removes)] = adds
            offset += len(adds) - len(removes)
        else:
            i += 1
    return result
