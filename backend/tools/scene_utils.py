"""Shared helpers for working with Manim scene files."""
from __future__ import annotations
import re
from pathlib import Path

_SCENE_CLASS_RE = re.compile(r"class\s+(Scene\w*)\s*\(")


def get_scene_name(scene_file: Path) -> str:
    """Return the first `class SceneXxx(` name found in the file, or 'Scene'."""
    if not scene_file.exists():
        return "Scene"
    m = _SCENE_CLASS_RE.search(scene_file.read_text(encoding="utf-8"))
    return m.group(1) if m else "Scene"
