"""Pipeline orchestrator — coordinates agents through the event-sourced harness.

Design:
- Every state transition is appended to the project's event log (events.jsonl).
- The orchestrator is a thin coordinator; retries/validation/metrics live in
  harness.runner. This file only owns sequencing and pause points.
- Scene rendering is parallelized (ThreadPoolExecutor, max 4 workers).
  Each scene is reviewed independently by the user before final render.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from events import PipelineEvent
from project_store import (
    project_path, update_manifest, load_manifest,
    init_scene_states, update_scene_state, get_all_scene_states, all_scenes_approved,
)
from harness.events import AgentEvent
from harness.store import append_event, load_log
from harness.graders import grade_video_exists, grade_video_playable, emit_grade
from agents import researcher, planner, beat_writer, coder, visual_qa, editor, curator
from tools.plugin_installer import install_plugin, ensure_installed
from tools.plugin_context import build_plugin_context
from tools.extract_frames import extract_frames as _extract_frames_tool
from tools.scene_utils import get_scene_name as _get_scene_name
from harness.runner import set_stream_emit
import claude_runner

SKILL_ROOT = Path(__file__).parent.parent / ".agents" / "skills" / "manim"
CHECK_ENV = SKILL_ROOT / "scripts" / "check_env.py"
MAX_QA_CYCLES = 2
MAX_SCENE_WORKERS = 4

Emit = Callable[[PipelineEvent], None]


# ── Cooperative cancellation ────────────────────────────────────────────────
# /stop sets a per-project flag and kills the active `claude` subprocesses.
# The orchestrator checks the flag at every step boundary and raises early.

class PipelineCancelled(Exception):
    """Raised when the user has requested the pipeline to stop."""


_cancel_lock = threading.Lock()
_cancel_flags: dict[str, threading.Event] = {}


def _flag(project_id: str) -> threading.Event:
    with _cancel_lock:
        ev = _cancel_flags.get(project_id)
        if ev is None:
            ev = threading.Event()
            _cancel_flags[project_id] = ev
        return ev


def request_cancel(project_id: str, *, wait_secs: float = 1.5) -> int:
    """Signal the orchestrator to stop and kill in-flight subprocesses.

    Sets the cancel flag, kills tracked `claude` subprocesses, then waits
    briefly so orphaned worker threads can reach their except-handler and
    record their death as 'superseded' (instead of pisar the manifest).
    After the wait, the flag is cleared so a new pipeline can start cleanly.

    Returns the number of subprocesses killed.
    """
    flag = _flag(project_id)
    flag.set()
    killed = claude_runner.kill_for_project(project_id)
    if killed > 0 and wait_secs > 0:
        time.sleep(wait_secs)
    # Reset for the next run. Threads that arrive *after* this point will
    # see flag=cleared and fall through to the normal error path; in
    # practice the subprocess.communicate() return is near-instantaneous
    # after kill, so 1.5s is enough headroom.
    flag.clear()
    return killed


def clear_cancel(project_id: str) -> None:
    with _cancel_lock:
        _cancel_flags.pop(project_id, None)


def _check_cancel(project_id: str) -> None:
    if _flag(project_id).is_set():
        raise PipelineCancelled(f"Pipeline detenido por el usuario ({project_id})")


def _handle_pipeline_exception(project_id: str, emit: Emit, exc: Exception, reason: str) -> None:
    """Common handler for the broad except Exception branches.

    If the cancel flag is set, this run was killed externally by a newer
    /stop or /resume. We log a `pipeline.failed{reason=superseded}` but DO
    NOT touch the manifest — the new owner has already updated status.
    Otherwise, this is a genuine error and we mark the project as such.
    """
    if _flag(project_id).is_set():
        append_event(project_id, AgentEvent(
            kind="pipeline.failed",
            payload={"reason": "superseded", "from": reason, "error": str(exc)[:300]},
        ))
        return
    append_event(project_id, AgentEvent(
        kind="pipeline.failed",
        payload={"reason": reason, "error": str(exc)[:500]},
    ))
    update_manifest(project_id, {"status": "error", "error": str(exc)})
    _ws(emit, project_id, "error", message=str(exc))


def _ws(emit: Emit, project_id: str, kind: str, **payload):
    """Emit a WebSocket event AND append a log entry."""
    emit(PipelineEvent(kind=kind, project_id=project_id, payload=payload))


# ── Stage 1: env check + researcher ─────────────────────────────────────────

def run_pipeline(project_id: str, emit: Emit) -> None:
    """Stage 1: env check + researcher. Pauses for plugin approval."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_stream_line)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.started",
                                            payload={"idea": manifest["idea"]}))
        update_manifest(project_id, {"status": "running"})
        _ws(emit, project_id, "pipeline_started")

        # 1. Env check
        result = subprocess.run([sys.executable, str(CHECK_ENV)], capture_output=True, text=True)
        if result.returncode != 0:
            msg = (result.stdout + result.stderr)[:500]
            append_event(project_id, AgentEvent(kind="pipeline.failed",
                                                payload={"reason": "env_check", "detail": msg}))
            update_manifest(project_id, {"status": "env_failed"})
            _ws(emit, project_id, "env_check_failed", message=msg)
            return
        _ws(emit, project_id, "env_check_ok", output=result.stdout)

        # 2. Researcher (optional — user can skip from the start-video form)
        if manifest.get("skip_research"):
            _ws(emit, project_id, "log", message="Investigación de plugins omitida por el usuario — saltando al Planner")
            append_event(project_id, AgentEvent(
                kind="pipeline.resumed",
                payload={"after": "researcher_skipped"},
            ))
            update_manifest(project_id, {
                "status": "running",
                "plugins_proposal": [],
                "plugins": {},
            })
            # Skip the awaiting_plugins gate entirely — go straight to stage 2
            # with no approved plugins. manim-voiceover is still auto-installed.
            run_pipeline_after_plugins(project_id, approved_plugins=[], emit=emit)
            return

        _ws(emit, project_id, "agent_started", agent="researcher")
        _check_cancel(project_id)
        plugins = researcher.run(project_id, manifest["idea"], proj)
        _ws(emit, project_id, "plugins_proposed", plugins=plugins)
        update_manifest(project_id, {"status": "awaiting_plugins", "plugins_proposal": plugins})
        append_event(project_id, AgentEvent(kind="pipeline.paused",
                                            payload={"reason": "awaiting_plugins"}))

    except PipelineCancelled as e:
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        _handle_pipeline_exception(project_id, emit, e, "unhandled")


# ── Stage 2: planner → beats → parallel scene rendering ─────────────────────

def run_pipeline_after_plugins(project_id: str, approved_plugins: list[str], emit: Emit) -> None:
    """Stage 2: plugins → planner → beat_writer → parallel scene render.
    Pauses at awaiting_scene_review for per-scene user approval."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)

    def _pipeline_stream(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_pipeline_stream)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "plugins"}))

        # 3a. Install user-approved plugins
        if approved_plugins:
            results = {}
            for pkg in approved_plugins:
                _check_cancel(project_id)
                res = install_plugin(pkg)
                results[pkg] = res
                append_event(project_id, AgentEvent(
                    kind="tool.completed", agent="plugin_installer",
                    payload={"package": pkg, **res},
                ))
                _ws(emit, project_id, "log", message=f"Plugin {pkg}: {res['status']}")
            update_manifest(project_id, {"plugins": results})
            manifest = load_manifest(project_id)

        # 3b. Auto-install manim-voiceover
        _check_cancel(project_id)
        vo_res = ensure_installed("manim-voiceover", extras="gtts")
        append_event(project_id, AgentEvent(
            kind="tool.completed", agent="plugin_installer",
            payload={"package": "manim-voiceover", "auto": True, **vo_res},
        ))
        _ws(emit, project_id, "log", message=f"manim-voiceover[gtts]: {vo_res['status']}")
        _ws(emit, project_id, "plugins_installed")

        _stage2_planner_through_scenes(project_id, emit)

    except PipelineCancelled as e:
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        _handle_pipeline_exception(project_id, emit, e, "unhandled")


def _stage2_planner_through_scenes(
    project_id: str, emit: Emit, *,
    outline: str | None = None,
    beats_by_scene: dict[int, Path] | None = None,
) -> None:
    """Planner → Beat Writer → parallel scenes. Pauses at awaiting_scene_review.

    Both `outline` and `beats_by_scene` are optional — when supplied the matching
    agent is skipped (used by the resume endpoint to leverage existing data).
    """
    proj = project_path(project_id)
    manifest = load_manifest(project_id)
    lang = manifest.get("lang", "es")
    plugin_context = build_plugin_context(manifest)

    # 4. Planner (skip if outline already provided)
    _check_cancel(project_id)
    if outline is None:
        _ws(emit, project_id, "agent_started", agent="planner")
        outline = planner.run(
            project_id, manifest["idea"], proj,
            lang=lang,
            audience=manifest.get("audience", "general"),
            target_length=manifest.get("target_length", "60s"),
            plugin_context=plugin_context,
        )
        _ws(emit, project_id, "outline_ready", outline=outline)
        update_manifest(project_id, {"status": "planning_done"})
    else:
        _ws(emit, project_id, "log", message="Reutilizando outline.md existente — saltando Planner")
        _ws(emit, project_id, "outline_ready", outline=outline)

    # 5. Beat Writer (skip if beats already provided)
    _check_cancel(project_id)
    if beats_by_scene is None:
        _ws(emit, project_id, "agent_started", agent="beat_writer")
        beats_by_scene = beat_writer.run(
            project_id, outline, proj,
            lang=lang,
            audience=manifest.get("audience", "general"),
            target_length=manifest.get("target_length", "60s"),
        )
    else:
        _ws(emit, project_id, "log", message="Reutilizando beats existentes — saltando Beat Writer")
    _ws(emit, project_id, "beats_ready", scenes=sorted(beats_by_scene.keys()))

    # 6. Initialize per-scene state and launch parallel rendering
    _check_cancel(project_id)
    scene_entries = _parse_scenes(outline)
    init_scene_states(project_id, scene_entries)
    # Ensure scene/render dirs exist so coder.write_text and manim -o won't
    # blow up on a fresh project where these were never created.
    (proj / "scenes").mkdir(parents=True, exist_ok=True)
    (proj / "renders").mkdir(parents=True, exist_ok=True)
    update_manifest(project_id, {"status": "running"})

    _run_scenes_parallel(
        project_id, scene_entries, beats_by_scene,
        outline, proj, plugin_context, lang, emit,
    )

    # After all scenes rendered, pause for per-scene human review
    update_manifest(project_id, {"status": "awaiting_scene_review"})
    append_event(project_id, AgentEvent(kind="pipeline.paused",
                                        payload={"reason": "awaiting_scene_review"}))
    _ws(emit, project_id, "log", message="Todas las escenas renderizadas — pendiente de revisión")
    # Dedicated event so the frontend re-fetches the manifest and re-applies
    # the baseline (without this, the UI stays stuck on the "running" snapshot).
    _ws(emit, project_id, "scenes_all_rendered")


def _on_cancelled(project_id: str, emit: Emit, msg: str) -> None:
    append_event(project_id, AgentEvent(kind="pipeline.failed",
                                        payload={"reason": "cancelled", "detail": msg}))
    update_manifest(project_id, {"status": "stopped"})
    _ws(emit, project_id, "error", message=msg)
    clear_cancel(project_id)


def _run_scenes_parallel(
    project_id: str,
    scene_entries: list[str],
    beats_by_scene: dict[int, Path],
    outline: str,
    proj: Path,
    plugin_context: str,
    lang: str,
    emit: Emit,
) -> None:
    """Fan-out scene rendering across threads, collect results."""
    n_workers = min(len(scene_entries), MAX_SCENE_WORKERS)

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(
                _run_scene_initial,
                project_id, i, desc, outline, proj,
                plugin_context, lang, beats_by_scene.get(i), emit,
            ): i
            for i, desc in enumerate(scene_entries, start=1)
        }
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                fut.result()
            except Exception as e:
                update_scene_state(project_id, i, status="failed", error=str(e)[:500])
                _ws(emit, project_id, "scene_preview_ready", scene=i, status="failed",
                    message=str(e)[:200])


def _run_scene_initial(
    project_id: str,
    scene_num: int,
    scene_desc: str,
    outline: str,
    proj: Path,
    plugin_context: str,
    lang: str,
    beats_file: Path | None,
    emit: Emit,
) -> None:
    """Run Coder + render + QA for one scene. Called from a worker thread."""
    # Register stream emit for this thread so call_agent can send live lines
    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line",
            agent=agent, scene=scene_num, **entry)
    set_stream_emit(_stream_line)

    update_scene_state(project_id, scene_num, status="rendering")
    _ws(emit, project_id, "scene_started", scene=scene_num, description=scene_desc[:200])

    _ws(emit, project_id, "agent_started", agent="coder", scene=scene_num)
    scene_file, code_status = coder.run(
        project_id, scene_num, scene_desc, outline, proj,
        plugin_context=plugin_context,
        lang=lang,
        beats_file=beats_file,
    )

    if code_status == "failed":
        _ws(emit, project_id, "render_failed", scene=scene_num, message="Max fix cycles reached")
        update_scene_state(project_id, scene_num, status="failed",
                           preview_path=None)
        _ws(emit, project_id, "scene_preview_ready", scene=scene_num, status="failed")
        return

    _ws(emit, project_id, "render_ok", scene=scene_num)
    preview_mp4, _ = _render_preview(scene_file, scene_num, proj)
    frames = _extract_frames(preview_mp4, scene_num, proj)
    _ws(emit, project_id, "frames_extracted", scene=scene_num, count=len(frames))

    # Auto-QA pass
    for cycle in range(1, MAX_QA_CYCLES + 1):
        _ws(emit, project_id, "agent_started", agent="visual_qa",
            scene=scene_num, cycle=cycle)
        qa = visual_qa.run(project_id, scene_num, scene_desc, scene_file, frames, proj)
        if qa["status"] == "ok":
            _ws(emit, project_id, "qa_ok", scene=scene_num)
            break
        _ws(emit, project_id, "qa_issue", scene=scene_num,
            cycle=cycle, notes=qa["raw"][:500])
        if cycle == MAX_QA_CYCLES:
            _ws(emit, project_id, "qa_degraded", scene=scene_num)
            break
        _ws(emit, project_id, "agent_started", agent="coder",
            scene=scene_num, phase="qa_fix")
        coder.fix_with_feedback(project_id, scene_file, qa["raw"], scene_num)
        preview_mp4, _ = _render_preview(scene_file, scene_num, proj)
        frames = _extract_frames(preview_mp4, scene_num, proj)

    update_scene_state(project_id, scene_num, status="awaiting_review",
                       preview_path=str(preview_mp4))
    _ws(emit, project_id, "scene_preview_ready", scene=scene_num,
        status="awaiting_review", preview_path=str(preview_mp4))


# ── User revision: re-roll one scene ────────────────────────────────────────

def run_scene_revision(project_id: str, scene_num: int, feedback: str, emit: Emit) -> None:
    """Apply user feedback to a single scene, re-render, re-QA."""
    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line",
            agent=agent, scene=scene_num, **entry)
    set_stream_emit(_stream_line)

    proj = project_path(project_id)
    manifest = load_manifest(project_id)
    lang = manifest.get("lang", "es")
    plugin_context = build_plugin_context(manifest)

    scene_file = proj / "scenes" / f"scene_{scene_num:02d}.py"
    beats_file = proj / "beats" / f"scene_{scene_num:02d}.beats.json"
    outline_path = proj / "outline.md"
    outline = outline_path.read_text(encoding="utf-8") if outline_path.exists() else ""
    scene_entries = _parse_scenes(outline)
    scene_desc = scene_entries[scene_num - 1] if scene_num <= len(scene_entries) else ""

    # Log feedback history
    scene_state = manifest.get("scenes", {}).get(f"{scene_num:02d}", {})
    history = scene_state.get("feedback_history", [])
    from datetime import datetime, timezone
    history.append({"ts": datetime.now(timezone.utc).isoformat(), "text": feedback})
    update_scene_state(project_id, scene_num, status="revising",
                       feedback_history=history)
    _ws(emit, project_id, "scene_revising", scene=scene_num)

    try:
        _ws(emit, project_id, "agent_started", agent="coder", scene=scene_num,
            phase="revision")
        _, code_status = coder.revise(
            project_id=project_id,
            scene_number=scene_num,
            scene_file=scene_file,
            feedback=feedback,
            project_path=proj,
            lang=lang,
            plugin_context=plugin_context,
            beats_file=beats_file if beats_file.exists() else None,
        )

        if code_status == "failed":
            update_scene_state(project_id, scene_num, status="awaiting_review")
            _ws(emit, project_id, "scene_preview_ready", scene=scene_num,
                status="awaiting_review", message="Revision rendered with errors")
            return

        preview_mp4, _ = _render_preview(scene_file, scene_num, proj)
        frames = _extract_frames(preview_mp4, scene_num, proj)
        _ws(emit, project_id, "frames_extracted", scene=scene_num, count=len(frames))

        # Re-run QA
        for cycle in range(1, MAX_QA_CYCLES + 1):
            _ws(emit, project_id, "agent_started", agent="visual_qa",
                scene=scene_num, cycle=cycle)
            qa = visual_qa.run(project_id, scene_num, scene_desc, scene_file, frames, proj)
            if qa["status"] == "ok":
                _ws(emit, project_id, "qa_ok", scene=scene_num)
                break
            _ws(emit, project_id, "qa_issue", scene=scene_num,
                cycle=cycle, notes=qa["raw"][:500])
            if cycle == MAX_QA_CYCLES:
                _ws(emit, project_id, "qa_degraded", scene=scene_num)
                break
            coder.fix_with_feedback(project_id, scene_file, qa["raw"], scene_num)
            preview_mp4, _ = _render_preview(scene_file, scene_num, proj)
            frames = _extract_frames(preview_mp4, scene_num, proj)

        update_scene_state(project_id, scene_num, status="awaiting_review",
                           preview_path=str(preview_mp4))
        _ws(emit, project_id, "scene_preview_ready", scene=scene_num,
            status="awaiting_review", preview_path=str(preview_mp4))

    except PipelineCancelled as e:
        update_scene_state(project_id, scene_num, status="awaiting_review")
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        update_scene_state(project_id, scene_num, status="awaiting_review")
        _ws(emit, project_id, "error", message=f"Scene {scene_num} revision failed: {e}")


# ── Stage 3: final render (after all scenes approved) ───────────────────────

def run_finalize(project_id: str, emit: Emit) -> None:
    """Render final video from all approved scenes, then pause for curator."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)
    lang = manifest.get("lang", "es")

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_stream_line)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "scene_review"}))
        _ws(emit, project_id, "finalizing")

        # Collect scene files in order
        scene_files: list[Path] = []
        all_states = get_all_scene_states(project_id)
        for key in sorted(all_states.keys()):
            sf = proj / "scenes" / f"scene_{key}.py"
            if sf.exists():
                scene_files.append(sf)

        _ws(emit, project_id, "agent_started", agent="editor")
        final_video = editor.run(scene_files, proj, lang=lang)

        emit_grade(project_id, "editor", None, grade_video_exists(final_video))
        emit_grade(project_id, "editor", None, grade_video_playable(final_video))
        _ws(emit, project_id, "edit_done", video=str(final_video))
        update_manifest(project_id, {"status": "awaiting_review",
                                     "final_video": str(final_video)})
        append_event(project_id, AgentEvent(kind="pipeline.paused",
                                            payload={"reason": "awaiting_review"}))

    except PipelineCancelled as e:
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        _handle_pipeline_exception(project_id, emit, e, "finalize")


# ── Curator ──────────────────────────────────────────────────────────────────

def run_curator(project_id: str, emit: Emit) -> None:
    proj = project_path(project_id)

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_stream_line)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "review"}))
        _ws(emit, project_id, "agent_started", agent="curator")
        result = curator.run(project_id, proj)
        _ws(emit, project_id, "curator_done",
            learnings=result.get("learnings", "")[:300],
            patches=list(result.get("patches", {}).keys()))
        update_manifest(project_id, {"status": "curated"})
        append_event(project_id, AgentEvent(kind="pipeline.completed", payload={}))
    except PipelineCancelled as e:
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        _handle_pipeline_exception(project_id, emit, e, "curator")


# ── Cheap resume from existing artifacts ────────────────────────────────────

RESUME_STEPS = ("planner", "beats", "scenes")


def detect_resume_options(project_id: str) -> dict:
    """Inspect disk artifacts and report which resume points are available.

    Returns a dict shape consumed by /resume-options.
    """
    proj = project_path(project_id)
    outline_path = proj / "outline.md"
    beats_dir = proj / "beats"
    scenes_dir = proj / "scenes"

    has_outline = outline_path.exists() and outline_path.stat().st_size > 0
    beats_files = sorted(beats_dir.glob("scene_*.beats.json")) if beats_dir.exists() else []
    scene_files = sorted(scenes_dir.glob("scene_*.py")) if scenes_dir.exists() else []

    return {
        "planner": {
            "available": True,
            "label": "Desde el Planner",
            "detail": "Re-generar outline y todo lo demás. Coste medio (~$0.03).",
            "skips": [],
        },
        "beats": {
            "available": has_outline,
            "label": "Desde el Beat Writer",
            "detail": (
                f"Reutiliza outline.md ({outline_path.stat().st_size if has_outline else 0} chars). "
                "Re-genera beats y escenas."
            ) if has_outline else "outline.md no existe",
            "skips": ["planner"] if has_outline else [],
        },
        "scenes": {
            "available": has_outline and bool(beats_files),
            "label": "Desde el Coder (escenas)",
            "detail": (
                f"Reutiliza outline + {len(beats_files)} beats.json. "
                "Sólo re-renderiza escenas."
            ) if (has_outline and beats_files) else "Faltan outline o beats",
            "skips": ["planner", "beats"] if (has_outline and beats_files) else [],
        },
        "artifacts": {
            "outline": has_outline,
            "beats_count": len(beats_files),
            "scenes_count": len(scene_files),
        },
    }


def run_resume(project_id: str, from_step: str, emit: Emit) -> None:
    """Restart the pipeline from a checkpoint, reusing existing on-disk artifacts.

    `from_step`:
      - "planner" — re-run Planner → Beats → Scenes (everything stage-2)
      - "beats"   — skip Planner, re-run Beats → Scenes (needs outline.md)
      - "scenes"  — skip Planner + Beats, re-run Scenes only (needs outline + beats)
    """
    if from_step not in RESUME_STEPS:
        raise ValueError(f"unknown resume step: {from_step}")

    proj = project_path(project_id)

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_stream_line)

    outline: str | None = None
    beats_by_scene: dict[int, Path] | None = None

    if from_step in ("beats", "scenes"):
        outline_path = proj / "outline.md"
        if not outline_path.exists():
            raise FileNotFoundError("outline.md no existe — no se puede reanudar desde aquí")
        outline = outline_path.read_text(encoding="utf-8")

    if from_step == "scenes":
        beats_dir = proj / "beats"
        beats_files = sorted(beats_dir.glob("scene_*.beats.json")) if beats_dir.exists() else []
        if not beats_files:
            raise FileNotFoundError("no hay archivos de beats — no se puede reanudar desde escenas")
        beats_by_scene = {}
        for bf in beats_files:
            # filename: scene_NN.beats.json
            m = re.match(r"scene_(\d+)\.beats\.json", bf.name)
            if m:
                beats_by_scene[int(m.group(1))] = bf

    try:
        append_event(project_id, AgentEvent(
            kind="pipeline.resumed",
            payload={"from_step": from_step,
                     "reused_outline": outline is not None,
                     "reused_beats": beats_by_scene is not None},
        ))
        update_manifest(project_id, {"status": "running"})
        _ws(emit, project_id, "log",
            message=f"Reanudando desde {from_step} (outline={'sí' if outline else 'no'}, beats={'sí' if beats_by_scene else 'no'})")
        _stage2_planner_through_scenes(
            project_id, emit,
            outline=outline, beats_by_scene=beats_by_scene,
        )
    except PipelineCancelled as e:
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        _handle_pipeline_exception(project_id, emit, e, f"resume:{from_step}")


def can_resume(project_id: str) -> tuple[bool, str]:
    log = load_log(project_id)
    if log.is_terminal():
        return False, "pipeline already terminal"
    if not log.events:
        return False, "no prior state"
    last = log.events[-1]
    return True, f"last event: {last.kind} (agent={last.agent})"


# ── Private helpers ───────────────────────────────────────────────────────────

_SCENE_HEADER_RE = re.compile(
    r"(?im)^\s*#{1,3}\s*(?:scene|escena)\s*\d+",
    # Matches: "## Scene 1", "### Escena 3", "# scene 2", etc. (EN + ES)
)


def _parse_scenes(outline: str) -> list[str]:
    """Split the outline into per-scene chunks by `## Scene N` / `## Escena N` headers.

    Returns one entry per scene. The preamble (anything before the first scene
    header) is discarded so it isn't mistakenly treated as a "scene".
    Fallback: if no headers are found, returns the full outline as a single scene
    so the pipeline can still run.
    """
    matches = list(_SCENE_HEADER_RE.finditer(outline))
    if not matches:
        return [outline.strip()]
    chunks: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(outline)
        chunk = outline[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks or [outline.strip()]


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
    frames_dir = proj / "renders" / f"scene_{scene_num:02d}" / "frames"
    try:
        return _extract_frames_tool(video, frames_dir, n=6)
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
