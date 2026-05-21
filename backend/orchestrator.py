"""Pipeline orchestrator — coordinates agents through the event-sourced harness.

Design:
- Every state transition is appended to the project's event log (events.jsonl).
- The orchestrator is a thin coordinator; retries/validation/metrics live in
  harness.runner. This file only owns sequencing and pause points.
- Pausable: on crash the event log on disk lets us resume from the last
  checkpoint (researcher_done, plugins_installed, scene_N_done, etc.).
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from events import PipelineEvent
from project_store import project_path, update_manifest, load_manifest
from harness.events import AgentEvent
from harness.store import append_event, load_log
from harness.graders import grade_video_exists, grade_video_playable, emit_grade

SKILL_ROOT = Path(__file__).parent.parent / ".agents" / "skills" / "manim"
CHECK_ENV = SKILL_ROOT / "scripts" / "check_env.py"
MAX_QA_CYCLES = 3

Emit = Callable[[PipelineEvent], None]


def _ws(emit: Emit, project_id: str, kind: str, **payload):
    """Mirror an event to the WebSocket using the legacy event vocabulary
    (for frontend back-compat) AND persist a richer AgentEvent to the log."""
    emit(PipelineEvent(kind=kind, project_id=project_id, payload=payload))


def run_pipeline(project_id: str, emit: Emit) -> None:
    """Stage 1: env check + researcher. Pauses for plugin approval."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.started",
                                            payload={"idea": manifest["idea"]}))
        update_manifest(project_id, {"status": "running"})
        _ws(emit, project_id, "pipeline_started")

        # 1. Env check (deterministic guardrail)
        result = subprocess.run([sys.executable, str(CHECK_ENV)], capture_output=True, text=True)
        if result.returncode != 0:
            msg = (result.stdout + result.stderr)[:500]
            append_event(project_id, AgentEvent(kind="pipeline.failed",
                                                payload={"reason": "env_check", "detail": msg}))
            update_manifest(project_id, {"status": "env_failed"})
            _ws(emit, project_id, "env_check_failed", message=msg)
            return
        _ws(emit, project_id, "env_check_ok", output=result.stdout)

        # 2. Researcher
        _ws(emit, project_id, "agent_started", agent="researcher")
        from agents import researcher
        plugins = researcher.run(project_id, manifest["idea"], proj)
        _ws(emit, project_id, "plugins_proposed", plugins=plugins)
        update_manifest(project_id, {"status": "awaiting_plugins", "plugins_proposal": plugins})
        append_event(project_id, AgentEvent(kind="pipeline.paused",
                                            payload={"reason": "awaiting_plugins"}))

    except Exception as e:
        append_event(project_id, AgentEvent(kind="pipeline.failed",
                                            payload={"reason": "unhandled", "error": str(e)}))
        update_manifest(project_id, {"status": "error", "error": str(e)})
        _ws(emit, project_id, "error", message=str(e))


def run_pipeline_after_plugins(project_id: str, approved_plugins: list[str], emit: Emit) -> None:
    """Stage 2: plugins → planner → per-scene loop → narrator → editor.
    Pauses for human review of the final video."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "plugins"}))

        # 3. Install plugins
        if approved_plugins:
            from tools.plugin_installer import install_plugin
            results = {}
            for pkg in approved_plugins:
                res = install_plugin(pkg)
                results[pkg] = res
                append_event(project_id, AgentEvent(
                    kind="tool.completed", agent="plugin_installer",
                    payload={"package": pkg, **res},
                ))
                _ws(emit, project_id, "log", message=f"Plugin {pkg}: {res['status']}")
            update_manifest(project_id, {"plugins": results})
        _ws(emit, project_id, "plugins_installed")

        # 4. Planner
        _ws(emit, project_id, "agent_started", agent="planner")
        from agents import planner
        outline = planner.run(
            project_id, manifest["idea"], proj,
            lang=manifest.get("lang", "es"),
            audience=manifest.get("audience", "general"),
            target_length=manifest.get("target_length", "60s"),
        )
        _ws(emit, project_id, "outline_ready", outline=outline)
        update_manifest(project_id, {"status": "planning_done"})

        # 5. Per-scene loop
        scene_entries = _parse_scenes(outline)
        scene_files: list[Path] = []
        scene_durations: list[float] = []

        for i, scene_desc in enumerate(scene_entries, start=1):
            _ws(emit, project_id, "scene_started", scene=i, description=scene_desc[:200])

            from agents import coder, visual_qa
            _ws(emit, project_id, "agent_started", agent="coder", scene=i)
            scene_file, code_status = coder.run(project_id, i, scene_desc, outline, proj)
            scene_files.append(scene_file)

            if code_status == "failed":
                _ws(emit, project_id, "render_failed", scene=i,
                    message="Max fix cycles reached")
                scene_durations.append(5.0)
                continue
            _ws(emit, project_id, "render_ok", scene=i)

            preview_mp4, duration = _render_preview(scene_file, i, proj)
            scene_durations.append(duration)
            frames = _extract_frames(preview_mp4, i, proj)
            _ws(emit, project_id, "frames_extracted", scene=i, count=len(frames))

            # Visual QA cycle — embedded verification loop
            for cycle in range(1, MAX_QA_CYCLES + 1):
                _ws(emit, project_id, "agent_started",
                    agent="visual_qa", scene=i, cycle=cycle)
                qa = visual_qa.run(project_id, i, scene_desc, scene_file, frames, proj)
                if qa["status"] == "ok":
                    _ws(emit, project_id, "qa_ok", scene=i)
                    break
                _ws(emit, project_id, "qa_issue",
                    scene=i, cycle=cycle, notes=qa["raw"][:500])
                if cycle == MAX_QA_CYCLES:
                    _ws(emit, project_id, "qa_degraded", scene=i)
                    break
                _ws(emit, project_id, "agent_started",
                    agent="coder", scene=i, phase="qa_fix")
                coder.fix_with_feedback(project_id, scene_file, qa["raw"], i)
                preview_mp4, duration = _render_preview(scene_file, i, proj)
                scene_durations[i - 1] = duration
                frames = _extract_frames(preview_mp4, i, proj)

        # 6. Narrator
        _ws(emit, project_id, "agent_started", agent="narrator")
        from agents import narrator
        audio_files = narrator.run(
            project_id, outline, scene_durations, proj,
            lang=manifest.get("lang", "es"),
            voice_profile=manifest.get("voice_profile"),
            tts_backend=manifest.get("tts_backend", "stub"),
        )
        _ws(emit, project_id, "narration_ready")

        # 7. Editor (no LLM)
        _ws(emit, project_id, "agent_started", agent="editor")
        from agents import editor
        final_video = editor.run(scene_files, audio_files, proj,
                                 lang=manifest.get("lang", "es"))
        # Output graders (deterministic — fast)
        emit_grade(project_id, "editor", None, grade_video_exists(final_video))
        emit_grade(project_id, "editor", None, grade_video_playable(final_video))
        _ws(emit, project_id, "edit_done", video=str(final_video))
        update_manifest(project_id, {"status": "awaiting_review",
                                     "final_video": str(final_video)})
        append_event(project_id, AgentEvent(kind="pipeline.paused",
                                            payload={"reason": "awaiting_review"}))

    except Exception as e:
        append_event(project_id, AgentEvent(kind="pipeline.failed",
                                            payload={"reason": "unhandled", "error": str(e)}))
        update_manifest(project_id, {"status": "error", "error": str(e)})
        _ws(emit, project_id, "error", message=str(e))


def run_curator(project_id: str, emit: Emit) -> None:
    proj = project_path(project_id)
    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "review"}))
        _ws(emit, project_id, "agent_started", agent="curator")
        from agents import curator
        result = curator.run(project_id, proj)
        _ws(emit, project_id, "curator_done",
            learnings=result.get("learnings", "")[:300],
            patches=list(result.get("patches", {}).keys()))
        update_manifest(project_id, {"status": "curated"})
        append_event(project_id, AgentEvent(kind="pipeline.completed", payload={}))
    except Exception as e:
        append_event(project_id, AgentEvent(kind="pipeline.failed",
                                            payload={"reason": "curator", "error": str(e)}))
        _ws(emit, project_id, "error", message=str(e))


def can_resume(project_id: str) -> tuple[bool, str]:
    """Inspect the event log to determine if a crashed pipeline can be resumed."""
    log = load_log(project_id)
    if log.is_terminal():
        return False, "pipeline already terminal"
    if not log.events:
        return False, "no prior state"
    last = log.events[-1]
    return True, f"last event: {last.kind} (agent={last.agent})"


# --- Helpers (unchanged) ---

def _parse_scenes(outline: str) -> list[str]:
    parts = re.split(r"(?m)^#{1,3}\s*[Ss]cena?\s*\d+", outline)
    scenes = [p.strip() for p in parts if p.strip()]
    return scenes if scenes else [outline]


def _render_preview(scene_file: Path, scene_num: int, proj: Path) -> tuple[Path, float]:
    scene_name = _get_scene_name(scene_file)
    render_dir = proj / "renders" / f"scene_{scene_num:02d}"
    render_dir.mkdir(parents=True, exist_ok=True)
    out = render_dir / "preview.mp4"
    subprocess.run(
        ["manim", "-ql", "--output_file", str(out), str(scene_file), scene_name],
        capture_output=True, text=True,
    )
    return out, _probe_duration(out)


def _extract_frames(video: Path, scene_num: int, proj: Path) -> list[Path]:
    from tools.extract_frames import extract_frames
    frames_dir = proj / "renders" / f"scene_{scene_num:02d}" / "frames"
    try:
        return extract_frames(video, frames_dir, n=6)
    except Exception:
        return []


def _probe_duration(video: Path) -> float:
    if not video.exists():
        return 5.0
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 5.0


def _get_scene_name(scene_file: Path) -> str:
    text = scene_file.read_text(encoding="utf-8")
    m = re.search(r"class\s+(Scene\w*)\s*\(", text)
    return m.group(1) if m else "Scene"
