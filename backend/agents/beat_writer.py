"""Beat Writer — turns the Planner's outline into per-scene beats.

A beat is the atom of voice↔animation synchronization. The Coder consumes one
`scene_NN.beats.json` file per scene and wraps each beat in a `with
self.voiceover(text=beat.text) as tracker:` block.

Skill content (narration.md + voiceover.py template) is inlined into the
prompt — no Read/Glob/Grep tool loop.

Output schema (per scene):
    [
      {"id": "1.1",
       "text": "...",
       "anim_hint": "Create the curve and dot",
       "duration_s_est": 4.5},
      ...
    ]
"""
from __future__ import annotations
import json
from pathlib import Path
from harness.runner import call_agent
from harness.prompts import BEAT_WRITER
from harness.guardrails import extract_json_array
from tools.format_context import get_planning_context

SKILL_ROOT = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"

_REQUIRED_BEAT_KEYS = ("id", "text", "anim_hint", "duration_s_est")


def _validator(raw: str) -> tuple[bool, str]:
    ok, parsed = extract_json_array(raw)
    if not ok:
        return False, str(parsed)
    if not isinstance(parsed, list) or not parsed:
        return False, "expected a non-empty JSON array"
    for i, scene_obj in enumerate(parsed):
        if not isinstance(scene_obj, dict):
            return False, f"scene entry {i} is not an object"
        if "scene" not in scene_obj or "beats" not in scene_obj:
            return False, f"scene entry {i} missing 'scene' or 'beats'"
        beats = scene_obj["beats"]
        if not isinstance(beats, list) or not (2 <= len(beats) <= 5):
            return False, f"scene {scene_obj.get('scene')} must have 2-5 beats (got {len(beats) if isinstance(beats, list) else 'non-list'})"
        for j, b in enumerate(beats):
            if not isinstance(b, dict):
                return False, f"scene {scene_obj.get('scene')} beat {j} is not an object"
            for key in _REQUIRED_BEAT_KEYS:
                if key not in b:
                    return False, f"scene {scene_obj.get('scene')} beat {j} missing key '{key}'"
            if not isinstance(b["text"], str) or not b["text"].strip():
                return False, f"scene {scene_obj.get('scene')} beat {j} has empty text"
    return True, "ok"


def run(
    project_id: str, outline: str, project_path: Path,
    lang: str = "es", fmt: str = "youtube", target_length: str = "60s",
) -> dict[int, Path]:
    """Generate beats.json for every scene in the outline.

    Returns a mapping {scene_number: Path to beats.json}.
    """
    beats_dir = project_path / "beats"
    beats_dir.mkdir(parents=True, exist_ok=True)

    voiceover_template = (SKILL_ROOT / "templates" / "voiceover.py").read_text(encoding="utf-8")

    # Let AgentCallFailed propagate — the orchestrator halts the pipeline
    # if beats can't be produced. Silently returning {} would let the Coder
    # run with no beats, producing a misleading "all green" UI state.
    #
    # Timeout 360s: structured JSON generation for 3-7 scenes × 2-5 beats with
    # Sonnet on a ~7KB prompt routinely hits 200+ seconds. 180s was too tight.
    raw = call_agent(
        project_id=project_id, agent="beat_writer",
        prompt=BEAT_WRITER.render(
            outline=outline, lang=lang,
            format_context=get_planning_context(fmt),
            target_length=target_length,
            voiceover_template=voiceover_template,
        ),
        system=BEAT_WRITER.system,
        model="sonnet",
        tools=None,
        timeout=360, max_attempts=3, validator=_validator,
    )

    _, parsed = extract_json_array(raw)
    written: dict[int, Path] = {}
    for scene_obj in parsed:
        scene_num = int(scene_obj["scene"])
        path = beats_dir / f"scene_{scene_num:02d}.beats.json"
        path.write_text(
            json.dumps(scene_obj["beats"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written[scene_num] = path
    return written
