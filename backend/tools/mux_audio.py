"""Mux a video file with an audio WAV using ffmpeg."""
from __future__ import annotations
import subprocess
from pathlib import Path


def mux_audio(video_path: str | Path, audio_path: str | Path, output_path: str | Path) -> Path:
    video = Path(video_path)
    audio = Path(audio_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not audio.exists() or audio.stat().st_size == 0:
        # No audio — just copy video
        import shutil
        shutil.copy2(video, out)
        return out

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video),
            "-i", str(audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out
