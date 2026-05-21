"""Concatenate multiple scene videos into a single output using ffmpeg concat demuxer."""
from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path


def concat_scenes(scene_videos: list[str | Path], output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for v in scene_videos:
            # ffmpeg concat list requires forward slashes and escaped paths
            escaped = str(Path(v).resolve()).replace("\\", "/")
            f.write(f"file '{escaped}'\n")
        list_path = f.name

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    Path(list_path).unlink(missing_ok=True)
    return out
