"""Graders: deterministic + LLM-as-judge.

Anthropic: "Choose deterministic graders where possible, LLM where necessary."
Each grader returns a Grade — never raises.

Three grader tiers (Anthropic taxonomy):
  1. CODE-BASED:  fast, reproducible, narrow signal
  2. MODEL-BASED: LLM-as-judge for nuanced quality
  3. HUMAN:       handled separately via the UI review flow
"""
from __future__ import annotations
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from harness.events import AgentEvent
from harness.store import append_event


@dataclass(frozen=True)
class Grade:
    grader: str
    passed: bool
    score: float        # 0.0–1.0 (partial credit, per Anthropic)
    details: str
    cost_ms: int = 0


# ── Code-based graders ─────────────────────────────────────────────────────

def grade_outline_structure(outline_md: str) -> Grade:
    """Deterministic: outline has the right shape."""
    import re
    scenes = re.findall(r"(?im)^#{1,3}\s*(escena|scene)\s*\d+", outline_md)
    n = len(scenes)
    if n == 0:
        return Grade("outline_structure", False, 0.0, "no scene headers found")
    if n < 3:
        return Grade("outline_structure", False, n / 3, f"only {n} scenes (need ≥3)")
    if n > 7:
        return Grade("outline_structure", True, 0.7, f"{n} scenes (>7, agent verbose)")
    return Grade("outline_structure", True, 1.0, f"{n} scenes")


def grade_scene_renderable(scene_file: Path, scene_name: str) -> Grade:
    """Run render_verify.py — the ultimate test of code correctness."""
    skill_root = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"
    verify = skill_root / "scripts" / "render_verify.py"
    import time
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(verify), str(scene_file), scene_name],
        capture_output=True, text=True, timeout=180,
    )
    cost = int((time.perf_counter() - t0) * 1000)
    if result.returncode == 0:
        return Grade("scene_renderable", True, 1.0, "rendered ok", cost_ms=cost)
    err = (result.stderr or result.stdout)[:300]
    return Grade("scene_renderable", False, 0.0, f"render failed: {err}", cost_ms=cost)


def grade_video_exists(video_path: Path) -> Grade:
    if not video_path.exists():
        return Grade("video_exists", False, 0.0, f"missing: {video_path}")
    size_mb = video_path.stat().st_size / 1_000_000
    if size_mb < 0.1:
        return Grade("video_exists", False, 0.2, f"file too small ({size_mb:.2f}MB)")
    return Grade("video_exists", True, 1.0, f"{size_mb:.1f}MB")


def grade_video_playable(video_path: Path) -> Grade:
    """ffprobe sanity check — has video stream + duration > 1s."""
    if not video_path.exists():
        return Grade("video_playable", False, 0.0, "file missing")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1", str(video_path)],
        capture_output=True, text=True,
    )
    text = result.stdout
    if "codec_type=video" not in text:
        return Grade("video_playable", False, 0.2, "no video stream")
    try:
        duration = float([l.split("=")[1] for l in text.splitlines() if "duration=" in l][0])
    except (IndexError, ValueError):
        duration = 0
    if duration < 1.0:
        return Grade("video_playable", False, 0.4, f"too short: {duration:.1f}s")
    return Grade("video_playable", True, 1.0, f"playable, {duration:.1f}s")


# ── LLM-as-judge ───────────────────────────────────────────────────────────

JUDGE_SYSTEM = """You are an impartial grader for AI-generated Manim educational videos.
You receive the original idea, the scene outline, and rubric criteria.
Score each criterion 0–1 (1 = perfect, 0 = absent). Be strict but fair.

Output ONLY a valid JSON object: {"scores": {"<criterion>": 0.0-1.0, ...}, "comment": "<one sentence>"}
No prose, no markdown."""


def grade_outline_quality_llm(idea: str, outline: str, project_id: str) -> Grade:
    """LLM-as-judge: pedagogical quality of the outline."""
    from harness.runner import call_agent, AgentCallFailed
    from harness.guardrails import extract_json_object
    rubric = [
        "matches_idea (does the outline address the user's idea?)",
        "progressive (do scenes build on each other?)",
        "concrete (are visual descriptions specific, not vague?)",
        "factual (are mathematical claims correct?)",
    ]
    prompt = f"""IDEA: {idea}

OUTLINE:
{outline}

CRITERIA: {rubric}

Score 0-1 per criterion. Output JSON only."""
    try:
        raw = call_agent(
            project_id=project_id, agent="grader.outline_quality",
            prompt=prompt, system=JUDGE_SYSTEM, model="sonnet",
            timeout=60, max_attempts=2,
            validator=lambda r: (extract_json_object(r)[0], "invalid json"),
        )
    except AgentCallFailed as e:
        return Grade("outline_quality_llm", False, 0.5, f"judge failed: {e}")

    ok, parsed = extract_json_object(raw)
    if not ok or "scores" not in parsed:
        return Grade("outline_quality_llm", False, 0.5, "malformed judge output")
    scores = parsed["scores"]
    avg = sum(scores.values()) / max(len(scores), 1)
    return Grade(
        "outline_quality_llm",
        avg >= 0.6,
        avg,
        f"{parsed.get('comment', '')} | scores={scores}",
    )


# ── Pipeline grading orchestration ──────────────────────────────────────────

def emit_grade(project_id: str, agent: str, scene: int | None, grade: Grade) -> None:
    """Persist a grade into the event log."""
    kind = "grader.passed" if grade.passed else "grader.failed"
    append_event(project_id, AgentEvent(
        kind=kind, agent=agent, scene=scene,
        payload={
            "grader": grade.grader,
            "score": grade.score,
            "details": grade.details,
            "cost_ms": grade.cost_ms,
        },
    ))
