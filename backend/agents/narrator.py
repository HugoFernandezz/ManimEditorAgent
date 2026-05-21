"""Narrator — voiceover script segmented per scene + TTS synthesis."""
from __future__ import annotations
import re
from pathlib import Path
from harness.runner import call_agent, AgentCallFailed
from harness.prompts import NARRATOR
from tools.tts_adapter import synthesize


def _validator(raw: str) -> tuple[bool, str]:
    if "--- SCENE" not in raw:
        return False, "missing '--- SCENE N ---' markers"
    n_blocks = len(re.findall(r"---\s*SCENE\s+\d+\s*---", raw))
    if n_blocks < 1:
        return False, f"found {n_blocks} scene blocks"
    return True, "ok"


def run(
    project_id: str, outline: str, scene_durations: list[float],
    project_path: Path, lang: str = "es",
    voice_profile: str | None = None, tts_backend: str = "stub",
) -> list[Path]:
    audio_dir = project_path / "audio"
    audio_dir.mkdir(exist_ok=True)
    duration_info = "\n".join(f"Scene {i+1}: {d:.1f}s" for i, d in enumerate(scene_durations))

    try:
        script = call_agent(
            project_id=project_id, agent="narrator",
            prompt=NARRATOR.render(outline=outline, durations=duration_info, lang=lang),
            system=NARRATOR.system, model="sonnet",
            timeout=120, max_attempts=3, validator=_validator,
        )
    except AgentCallFailed:
        # Degrade: silent audio for every scene
        script = "\n".join(f"--- SCENE {i+1} ---\n[narration unavailable]" for i in range(len(scene_durations)))

    (audio_dir / "script.txt").write_text(script, encoding="utf-8")

    blocks = [b.strip() for b in re.split(r"---\s*SCENE\s+\d+\s*---", script) if b.strip()]
    wav_paths = []
    for i, text in enumerate(blocks):
        out = audio_dir / f"scene_{i+1:02d}.wav"
        synthesize(text, out, lang=lang, voice_profile=voice_profile, backend=tts_backend)
        wav_paths.append(out)
    return wav_paths
