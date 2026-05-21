"""Extract N evenly-spaced frames from a video as PNG files using ffmpeg."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path


def extract_frames(video_path: str | Path, output_dir: str | Path, n: int = 6) -> list[Path]:
    video = Path(video_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Get duration with ffprobe
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        capture_output=True,
        text=True,
    )
    duration = float(probe.stdout.strip() or "0")
    if duration == 0:
        # Single-frame video or image — just copy last frame
        out_path = out / "frame_0001.png"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video), "-frames:v", "1", str(out_path)],
            check=True, capture_output=True,
        )
        return [out_path]

    fps_expr = f"1/{max(duration / n, 1)}"
    pattern = str(out / "frame_%04d.png")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video),
            "-vf", f"fps={fps_expr}",
            pattern,
        ],
        check=True,
        capture_output=True,
    )
    return sorted(out.glob("frame_*.png"))


if __name__ == "__main__":
    frames = extract_frames(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 6)
    for f in frames:
        print(f)
