"""Editor: renders each scene at HQ and concatenates.

Audio is no longer muxed here — every scene is a `VoiceoverScene` so the
rendered MP4 already contains a synchronized audio track. `concat_scenes` uses
ffmpeg's concat demuxer with `-c copy`, which preserves the embedded audio
streams as-is.
"""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from tools.concat_scenes import concat_scenes
from tools.scene_utils import get_scene_name


def run(
    scene_files: list[Path],
    project_path: Path,
    lang: str = "es",
) -> Path:
    final_dir = project_path / "final"
    final_dir.mkdir(exist_ok=True)
    renders_dir = project_path / "renders"

    hq_videos: list[Path] = []
    for i, scene_file in enumerate(scene_files):
        if not scene_file.exists():
            continue
        scene_name = get_scene_name(scene_file)
        render_dir = renders_dir / f"scene_{i + 1:02d}"
        render_dir.mkdir(parents=True, exist_ok=True)
        hq_video = render_dir / "final.mp4"

        result = subprocess.run(
            ["manim", "-qh", "--output_file", str(hq_video), str(scene_file), scene_name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            # Fall back to the low-quality preview if HQ render fails.
            preview = render_dir / "preview.mp4"
            if preview.exists():
                hq_video = preview
            else:
                continue
        hq_videos.append(hq_video)

    if not hq_videos:
        raise RuntimeError("No scenes rendered successfully.")

    output = final_dir / f"video_{lang}.mp4"
    if len(hq_videos) == 1:
        shutil.copy2(hq_videos[0], output)
    else:
        concat_scenes(hq_videos, output)
    return output
