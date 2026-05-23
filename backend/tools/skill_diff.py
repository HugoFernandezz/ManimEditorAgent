"""Generate and apply unified diffs for skill files.

The previous applier ignored context lines (" "-prefixed), which meant any
non-trivial hunk produced wrong output. We now walk the hunk line-by-line and
honour the unified-diff semantics correctly.
"""
from __future__ import annotations
import difflib
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"

_HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")


def generate_diff(file_rel: str, new_content: str) -> str:
    """Return a unified diff string between the current skill file and new_content."""
    target = SKILL_ROOT / file_rel
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{file_rel}",
        tofile=f"b/{file_rel}",
    ))


def apply_hunk(file_rel: str, hunk_patch: str) -> None:
    """Apply a unified-diff patch to the skill file. Writes in place."""
    target = SKILL_ROOT / file_rel
    original = target.read_text(encoding="utf-8") if target.exists() else ""
    patched = _apply_patch(original.splitlines(keepends=True), hunk_patch)
    target.write_text("".join(patched), encoding="utf-8")


def _apply_patch(original: list[str], patch: str) -> list[str]:
    """Apply a unified diff (possibly multi-hunk) to `original`.

    Walks each hunk in source order, building the result line-by-line:
      ' '  context   → take from original, advance both pointers
      '-'  removed   → skip in original, advance source pointer only
      '+'  added     → emit, do NOT advance source pointer
      '\\' no-newline marker → ignore
    """
    lines = patch.splitlines(keepends=True)
    result: list[str] = []
    src = 0           # next unread line in `original`
    i = 0
    while i < len(lines):
        header = _HUNK_HEADER_RE.match(lines[i])
        if not header:
            i += 1
            continue
        hunk_src_start = int(header.group(1))
        # difflib uses 1-indexed; "0" means insertion before line 1.
        target_src = max(hunk_src_start - 1, 0)
        # Copy original lines up to the start of this hunk.
        if target_src > src:
            result.extend(original[src:target_src])
            src = target_src
        i += 1
        # Consume hunk body until next header or end.
        while i < len(lines) and not lines[i].startswith("@@"):
            line = lines[i]
            i += 1
            if not line or line.startswith("\\"):   # "\ No newline at end of file"
                continue
            tag, body = line[0], line[1:]
            if tag == " ":
                # Context: must match the source. Skip src forward defensively
                # (don't trust the line content — diff may have different EOLs).
                if src < len(original):
                    result.append(original[src])
                    src += 1
            elif tag == "-":
                src += 1                            # drop from source
            elif tag == "+":
                result.append(body)                 # insert into target
            # Any other prefix (blank line in malformed patch) — skip silently.
    # Tail: append everything after the last hunk.
    if src < len(original):
        result.extend(original[src:])
    return result
