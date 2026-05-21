"""Pluggable TTS interface. Default backend: silent stub.

To add a real backend, implement a function matching the signature:
    def synthesize(text: str, output_path: Path, lang: str, voice_profile: str | None) -> None
and register it in BACKENDS.
"""
from __future__ import annotations
from pathlib import Path
import wave
import struct


def _silent_stub(text: str, output_path: Path, lang: str, voice_profile: str | None) -> None:
    """Write a 1-second silent WAV so the pipeline never blocks on missing TTS."""
    sample_rate = 22050
    duration_s = max(1, len(text.split()) // 3)  # rough estimate
    num_samples = sample_rate * duration_s
    with wave.open(str(output_path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * num_samples, *([0] * num_samples)))


BACKENDS: dict[str, callable] = {
    "stub": _silent_stub,
    # "xtts": _xtts_backend,   # add when ready
    # "f5":   _f5_backend,
    # "piper": _piper_backend,
}


def synthesize(
    text: str,
    output_path: str | Path,
    lang: str = "es",
    voice_profile: str | None = None,
    backend: str = "stub",
) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fn = BACKENDS.get(backend, _silent_stub)
    fn(text, out, lang, voice_profile)
    return out
