"""Visual QA agent: reads rendered frames via Claude's Read tool and proposes fixes."""
from __future__ import annotations
from pathlib import Path
from claude_runner import run_with_tools

SYSTEM = """\
You are a visual quality-assurance reviewer for Manim animations.
You will be asked to read image files (frames from a rendered scene) using the Read tool.
Read each frame file provided, then analyse them for:
- Text/LaTeX overflow or clipping at screen edges
- MathTex elements overlapping other mobjects
- Poor color contrast against the background
- Objects misaligned or off-center
- Any rendering artifact or broken LaTeX

Respond with a YAML block:
```yaml
status: ok   # or needs_fix
issues:
  - frame: 3
    problem: "description"
    fix_hint: "concrete ManimCE API call suggestion"
```
If status is ok, issues must be empty.
Be concrete in fix_hint — give actual ManimCE API calls.
"""


def run(
    scene_number: int,
    scene_desc: str,
    scene_file: Path,
    frames: list[Path],
    project_path: Path,
) -> dict:
    render_dir = project_path / "renders" / f"scene_{scene_number:02d}"
    render_dir.mkdir(parents=True, exist_ok=True)
    qa_path = render_dir / "qa_notes.md"

    code = scene_file.read_text(encoding="utf-8") if scene_file.exists() else ""
    frame_list = "\n".join(f"- {f}" for f in frames[:6] if f.exists())

    prompt = (
        f"Scene description:\n{scene_desc}\n\n"
        f"Scene code:\n```python\n{code}\n```\n\n"
        f"Please read each of these frame image files using the Read tool and analyse them:\n{frame_list}\n\n"
        "After reading all frames, respond with the YAML quality report."
    )

    # add-dir for the frames directory so Read tool can access them
    frames_dir = render_dir / "frames"
    raw = run_with_tools(
        prompt=prompt,
        system=SYSTEM,
        model="opus",
        tools="Read",
        add_dirs=[frames_dir] if frames_dir.exists() else [],
        timeout=180,
    )
    qa_path.write_text(raw, encoding="utf-8")
    status = "needs_fix" if "needs_fix" in raw else "ok"
    return {"status": status, "raw": raw, "path": str(qa_path)}
