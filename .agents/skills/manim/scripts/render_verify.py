"""
Render a Manim scene at low quality + last-frame-only, parse stderr, and report.

Usage:
    python render_verify.py <file.py> <SceneName> [--gl]

Behaviour:
    - Default: runs `manim -ql --save_last_frame <file> <Scene>` (ManimCE).
    - With --gl: runs `manimgl -l -w <file> <Scene>` (ManimGL).
    - On success: prints the path to the generated frame/video.
    - On failure: categorises the error using known patterns and points to
      the relevant section of references/troubleshooting.md.

Designed to be the inner loop of the manim skill. Use it during iteration
instead of full-quality renders.

Exit codes:
    0 — render succeeded
    1 — render failed
    2 — invalid arguments / file not found
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


# Error patterns. Order matters — first match wins.
ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"File `?standalone\.cls'? not found", re.I),
        "LaTeX missing 'standalone' package",
        "Install texlive-latex-extra (Linux), MacTeX, or use MiKTeX Console to add 'standalone'. See troubleshooting #1.",
    ),
    (
        re.compile(r"latex error|! LaTeX Error|! Package|! Undefined control sequence", re.I),
        "LaTeX syntax / package error",
        "Check the .log file Manim mentioned. Often a missing raw string r\"...\" or an undefined macro. See troubleshooting #2.",
    ),
    (
        re.compile(r"No module named ['\"]?manimpango['\"]?", re.I),
        "manimpango not installed",
        "pip install --upgrade manimpango. On Linux you may need libpango1.0-dev. See troubleshooting #3.",
    ),
    (
        re.compile(r"ffmpeg.*not found|No such file or directory: ['\"]?ffmpeg", re.I),
        "ffmpeg missing",
        "Install ffmpeg and ensure it is on PATH. See troubleshooting #4.",
    ),
    (
        re.compile(r"cairo|libcairo", re.I),
        "Cairo native library issue",
        "Install libcairo2-dev (Linux) / brew install cairo (macOS) / reinstall pycairo. See troubleshooting #5.",
    ),
    (
        re.compile(r"AttributeError.*animate|name 'ShowCreation' is not defined|name 'Create' is not defined", re.I),
        "Wrong Manim flavor for the imports",
        "Imports use one flavor (CE or GL) but you ran the other CLI. Match `from manim import *` ↔ `manim`, `from manimlib import *` ↔ `manimgl`. See troubleshooting #10.",
    ),
    (
        re.compile(r"Mobject.*not on screen|not in the scene", re.I),
        "Mobject not added or out of frame",
        "Did you self.add() it? Is it inside the default frame (x ±7.11, y ±4)? See troubleshooting #8.",
    ),
    (
        re.compile(r"command not found.*manim|'manim' is not recognized", re.I),
        "manim CLI not on PATH (Windows / venv issue)",
        "Use: python -m manim <args>. See troubleshooting #11.",
    ),
    (
        re.compile(r"ValueError: zero-size array", re.I),
        "Empty range in plot()",
        "t_range is empty or function returns NaN/inf. Check the range bounds. See troubleshooting #13.",
    ),
    (
        re.compile(r"No module named ['\"]?manim_voiceover", re.I),
        "manim-voiceover not installed",
        "pip install 'manim-voiceover[gtts]' (or another provider). See references/narration.md.",
    ),
]


def categorise(stderr: str, stdout: str) -> tuple[str, str] | None:
    blob = (stderr or "") + "\n" + (stdout or "")
    for pattern, label, fix in ERROR_PATTERNS:
        if pattern.search(blob):
            return label, fix
    return None


def find_output_artifact(file_path: Path, scene: str, gl: bool) -> Path | None:
    """Heuristic: find the rendered file under media/."""
    stem = file_path.stem
    media = file_path.parent / "media"
    if not media.exists():
        return None

    if gl:
        candidates = list((media / "videos").rglob(f"*{scene}*"))
    else:
        # ManimCE save_last_frame writes a .png under media/images/<stem>/<Scene>.png
        candidates = list((media / "images" / stem).rglob(f"{scene}*.png"))
        if not candidates:
            candidates = list((media / "videos").rglob(f"{scene}*.mp4"))

    if not candidates:
        return None
    # Most recent
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage: python render_verify.py <file.py> <SceneName> [--gl]", file=sys.stderr)
        return 2

    file_arg = Path(argv[1]).resolve()
    scene = argv[2]
    gl = "--gl" in argv[3:]

    if not file_arg.exists():
        print(f"File not found: {file_arg}", file=sys.stderr)
        return 2

    if gl:
        cmd = ["manimgl", str(file_arg), scene, "-l", "-w"]
    else:
        cmd = ["manim", "-ql", "--save_last_frame", str(file_arg), scene]

    print(f"$ {' '.join(cmd)}\n")

    try:
        proc = subprocess.run(
            cmd,
            cwd=file_arg.parent,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        print(f"ERROR: '{cmd[0]}' not found on PATH. Did you install Manim?", file=sys.stderr)
        print("  Try: pip install manim    (or:  pip install manimgl)", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("ERROR: render timed out after 300s. Reduce scene complexity for the verify step.", file=sys.stderr)
        return 1

    if proc.returncode == 0:
        artifact = find_output_artifact(file_arg, scene, gl)
        print("RESULT: OK")
        if artifact:
            print(f"  Output: {artifact}")
        else:
            print("  (could not auto-locate output file; check media/ folder)")
        return 0

    # Failed
    print("RESULT: FAILED", file=sys.stderr)
    print("\n--- stderr (last 30 lines) ---", file=sys.stderr)
    print("\n".join((proc.stderr or "").splitlines()[-30:]), file=sys.stderr)

    diagnosis = categorise(proc.stderr, proc.stdout)
    print("\n--- diagnosis ---", file=sys.stderr)
    if diagnosis:
        label, fix = diagnosis
        print(f"  Category: {label}", file=sys.stderr)
        print(f"  Fix:      {fix}", file=sys.stderr)
    else:
        print("  No known pattern matched. Read the stderr above carefully and consult references/troubleshooting.md.", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
