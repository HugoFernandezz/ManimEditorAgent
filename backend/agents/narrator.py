"""Narrator agent: writes voiceover script and synthesizes audio per scene."""
from __future__ import annotations
import re
from pathlib import Path
from claude_runner import run_text
from tools.tts_adapter import synthesize

SYSTEM = """\
You are a science communicator writing voiceover scripts for Manim explainer videos.
Given the full outline and scene durations, write a narration script segmented by scene.
Each scene block must fit within the scene's duration (words ≈ duration_s × 2.5 for Spanish).

Output format — one block per scene, separated by "--- SCENE N ---":
--- SCENE 1 ---
<narration text>
--- SCENE 2 ---
...

Write in the specified language. Be clear, engaging, and concise.
"""


def run(
    outline: str,
    scene_durations: list[float],
    project_path: Path,
    lang: str = "es",
    voice_profile: str | None = None,
    tts_backend: str = "stub",
) -> list[Path]:
    audio_dir = project_path / "audio"
    audio_dir.mkdir(exist_ok=True)

    duration_info = "\n".join(f"Scene {i+1}: {d:.1f}s" for i, d in enumerate(scene_durations))
    prompt = (
        f"Outline:\n{outline}\n\n"
        f"Scene durations:\n{duration_info}\n\n"
        f"Language: {lang}\n\n"
        "Write the segmented narration script."
    )
    script = run_text(prompt, system=SYSTEM, model="sonnet", timeout=120)
    (audio_dir / "script.txt").write_text(script, encoding="utf-8")

    blocks = re.split(r"---\s*SCENE\s+\d+\s*---", script)
    blocks = [b.strip() for b in blocks if b.strip()]

    wav_paths = []
    for i, text in enumerate(blocks):
        out = audio_dir / f"scene_{i+1:02d}.wav"
        synthesize(text, out, lang=lang, voice_profile=voice_profile, backend=tts_backend)
        wav_paths.append(out)
    return wav_paths
