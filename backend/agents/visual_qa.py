"""Visual QA agent: reads rendered frames + scene code and proposes fixes."""
from __future__ import annotations
import base64
from pathlib import Path
import anthropic

SYSTEM = """\
You are a visual quality-assurance reviewer for Manim animations.
You receive screenshots (frames) from a rendered scene plus the scene's outline description and code.

Analyse the frames carefully for:
- Text/LaTeX overflow or clipping at screen edges
- MathTex/Tex elements overlapping each other or other mobjects
- Poor color contrast against the background
- Objects placed with magic numbers that look off-center or misaligned
- Missing pauses (scene feels rushed)
- Any rendering artifact, broken LaTeX, or visual glitch

Respond with a YAML block like this:
```yaml
status: ok   # or needs_fix
issues:
  - frame: 3
    problem: "description"
    fix_hint: "concrete Manim code suggestion"
```

If status is ok, the issues list must be empty.
Be concrete in fix_hint — give actual ManimCE API calls, not vague advice.
"""


def run(
    client: anthropic.Anthropic,
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

    # Build multimodal content
    content: list = [
        {"type": "text", "text": f"Scene description:\n{scene_desc}\n\nScene code:\n```python\n{code}\n```\n\nFrames:"},
    ]
    for i, frame in enumerate(frames[:6]):  # cap at 6
        if frame.exists():
            img_data = base64.standard_b64encode(frame.read_bytes()).decode()
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": img_data},
            })
            content.append({"type": "text", "text": f"(frame {i + 1})"})

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    raw = resp.content[0].text.strip()
    qa_path.write_text(raw, encoding="utf-8")

    status = "needs_fix" if "needs_fix" in raw else "ok"
    return {"status": status, "raw": raw, "path": str(qa_path)}
