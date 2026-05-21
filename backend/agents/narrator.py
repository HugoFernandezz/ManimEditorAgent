"""Narrator agent: writes voiceover script and synthesizes audio per scene."""
from __future__ import annotations
from pathlib import Path
import anthropic
from tools.tts_adapter import synthesize

SYSTEM = """\
You are a science communicator writing voiceover scripts for Manim explainer videos.

Given the full outline and the rendered scene durations, write a narration script segmented by scene.
Each scene block must fit within the scene's duration (words ≈ duration_s × 2.5 for Spanish).

Output format — one block per scene, separated by "--- SCENE N ---":
--- SCENE 1 ---
<narration text for scene 1>
--- SCENE 2 ---
...

Write in the specified language. Be clear, engaging, and concise.
"""


def run(
    client: anthropic.Anthropic,
    outline: str,
    scene_durations: list[float],
    project_path: Path,
    lang: str = "es",
    voice_profile: str | None = None,
    tts_backend: str = "stub",
) -> list[Path]:
    audio_dir = project_path / "audio"
    audio_dir.mkdir(exist_ok=True)

    duration_info = "\n".join(
        f"Scene {i + 1}: {d:.1f}s" for i, d in enumerate(scene_durations)
    )

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Outline:\n{outline}\n\n"
                    f"Scene durations:\n{duration_info}\n\n"
                    f"Language: {lang}\n\n"
                    "Write the segmented narration script."
                ),
            }
        ],
    )
    script = resp.content[0].text.strip()
    (audio_dir / "script.txt").write_text(script, encoding="utf-8")

    # Split and synthesize per scene
    import re
    blocks = re.split(r"---\s*SCENE\s+\d+\s*---", script)
    blocks = [b.strip() for b in blocks if b.strip()]

    wav_paths = []
    for i, text in enumerate(blocks):
        out = audio_dir / f"scene_{i + 1:02d}.wav"
        synthesize(text, out, lang=lang, voice_profile=voice_profile, backend=tts_backend)
        wav_paths.append(out)

    return wav_paths
