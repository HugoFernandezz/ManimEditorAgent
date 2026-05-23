"""
Environment check for Manim. Run before any rendering.

Reports installed Manim flavor (CE / GL / both / none) and whether the system
dependencies Manim needs are reachable: ffmpeg, latex, dvisvgm, and pango.

Exit code:
    0 — all required tools present, at least one Manim flavor installed
    1 — something required is missing; details printed to stderr
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib import metadata


def check_python_package(name: str) -> str | None:
    """Return the installed version string, or None if not installed."""
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def check_binary(name: str) -> str | None:
    """Return the resolved binary path, or None if missing from PATH."""
    return shutil.which(name)


def get_binary_version(name: str, args: list[str]) -> str:
    try:
        out = subprocess.run(
            [name, *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        text = (out.stdout or out.stderr).strip().splitlines()
        return text[0] if text else "(version unknown)"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return f"(error: {exc})"


def main() -> int:
    print("=" * 60)
    print("Manim environment check")
    print("=" * 60)

    # --- Manim flavor ---
    manim_ce = check_python_package("manim")
    manim_gl = check_python_package("manimgl")
    voiceover = check_python_package("manim-voiceover")

    print("\n[Python packages]")
    print(f"  manim (CE)        : {manim_ce or 'NOT INSTALLED'}")
    print(f"  manimgl (GL)      : {manim_gl or 'NOT INSTALLED'}")
    # manim-voiceover is auto-installed by the pipeline (orchestrator step 3b),
    # so a missing package here is informational — the pipeline will fix it.
    print(f"  manim-voiceover   : {voiceover or 'not installed (auto-installed at run-time)'}")

    # --- System binaries ---
    print("\n[System binaries]")
    required_bins = {
        "ffmpeg": ["-version"],
        "latex": ["--version"],
        "dvisvgm": ["--version"],
    }
    missing_required = []
    for binary, version_args in required_bins.items():
        path = check_binary(binary)
        if path:
            ver = get_binary_version(binary, version_args)
            print(f"  {binary:10s}: OK    {path}   {ver}")
        else:
            print(f"  {binary:10s}: MISSING")
            missing_required.append(binary)

    # --- Pango (via Python binding) ---
    pango = check_python_package("manimpango")
    print(f"\n[Text rendering]")
    print(f"  manimpango        : {pango or 'NOT INSTALLED'}")

    # --- Verdict ---
    print("\n" + "=" * 60)
    problems = []
    if not (manim_ce or manim_gl):
        problems.append("No Manim flavor installed. Run: pip install manim   (or:  pip install manimgl)")
    if missing_required:
        problems.append(f"Missing system binaries: {', '.join(missing_required)}")
    if not pango:
        problems.append("manimpango missing. Run: pip install manimpango")

    if problems:
        print("STATUS: NOT READY")
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        print("\nSee references/troubleshooting.md for OS-specific install commands.")
        return 1

    flavors = []
    if manim_ce:
        flavors.append(f"ManimCE {manim_ce}")
    if manim_gl:
        flavors.append(f"ManimGL {manim_gl}")
    print(f"STATUS: READY — {' and '.join(flavors)}")
    if manim_ce and manim_gl:
        print("Both flavors installed. Decide which to use based on imports or ask the user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
