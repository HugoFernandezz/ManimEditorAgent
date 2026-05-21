"""Editor agent: renders final HQ video per scene, muxes audio, concatenates."""
from __future__ import annotations
import subprocess
from pathlib import Path
from tools.mux_audio import mux_audio
from tools.concat_scenes import concat_scenes

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"


def _get_scene_name(scene_file: Path) -> str:
    """Extract the Scene class name from the file."""
    import re
    text = scene_file.read_text(encoding="utf-8")
    m = re.search(r"class\s+(Scene\w*)\s*\(", text)
    return m.group(1) if m else "Scene"


def run(
    scene_files: list[Path],
    audio_files: list[Path],
    project_path: Path,
    lang: str = "es",
) -> Path:
    final_dir = project_path / "final"
    final_dir.mkdir(exist_ok=True)
    renders_dir = project_path / "renders"

    muxed_videos = []
    for i, scene_file in enumerate(scene_files):
        if not scene_file.exists():
            continue
        scene_name = _get_scene_name(scene_file)
        render_dir = renders_dir / f"scene_{i + 1:02d}"
        hq_video = render_dir / "final.mp4"
        render_dir.mkdir(parents=True, exist_ok=True)

        # Render at high quality
        result = subprocess.run(
            ["manim", "-qh", "--output_file", str(hq_video), str(scene_file), scene_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Fall back to low quality preview if HQ fails
            preview = render_dir / "preview.mp4"
            if preview.exists():
                hq_video = preview
            else:
                continue

        # Mux with audio
        audio = audio_files[i] if i < len(audio_files) else None
        muxed = render_dir / "muxed.mp4"
        if audio and audio.exists():
            mux_audio(hq_video, audio, muxed)
        else:
            import shutil
            shutil.copy2(hq_video, muxed)
        muxed_videos.append(muxed)

    if not muxed_videos:
        raise RuntimeError("No scenes rendered successfully.")

    output = final_dir / f"video_{lang}.mp4"
    if len(muxed_videos) == 1:
        import shutil
        shutil.copy2(muxed_videos[0], output)
    else:
        concat_scenes(muxed_videos, output)

    return output
