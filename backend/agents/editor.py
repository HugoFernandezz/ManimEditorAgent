"""Editor: renders each scene at HQ and concatenates.

Audio is no longer muxed here — every scene is a `VoiceoverScene` so the
rendered MP4 already contains a synchronized audio track. `concat_scenes` uses
ffmpeg's concat demuxer with `-c copy`, which preserves the embedded audio
streams as-is.
"""
from __future__ import annotations
import shutil
import subprocess
import time
from pathlib import Path
from tools.concat_scenes import concat_scenes
from tools.scene_utils import get_scene_name
from harness import debug_log


def run(
    scene_files: list[Path],
    project_path: Path,
    lang: str = "es",
    project_id: str = "",
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

        cmd = ["manim", "-qh", "--output_file", str(hq_video), str(scene_file), scene_name]
        debug_log.info(project_id, f"Render HQ  scene={i + 1}  →  {hq_video.name}")
        t0 = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True)
        debug_log.subprocess_result(project_id, f"manim -qh scene {i + 1}", cmd, result,
                                    time.perf_counter() - t0)

        if result.returncode != 0:
            preview = render_dir / "preview.mp4"
            if preview.exists():
                debug_log.warning(project_id,
                    f"HQ render failed for scene {i + 1}, falling back to preview.mp4")
                hq_video = preview
            else:
                debug_log.warning(project_id,
                    f"HQ render failed for scene {i + 1} and no preview exists — skipping")
                continue
        hq_videos.append(hq_video)

    if not hq_videos:
        debug_log.error(project_id, "No scenes rendered successfully — editor cannot produce final video")
        raise RuntimeError("No scenes rendered successfully.")

    output = final_dir / f"video_{lang}.mp4"
    if len(hq_videos) == 1:
        shutil.copy2(hq_videos[0], output)
    else:
        debug_log.info(project_id, f"Concatenating {len(hq_videos)} HQ scenes → {output}")
        concat_scenes(hq_videos, output)

    debug_log.info(project_id, f"Final video written: {output}  ({output.stat().st_size // 1024} KB)")
    return output
