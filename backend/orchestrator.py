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
from harness import debug_log
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

    # ── Debug log: fresh run file ──────────────────────────────────────────
    debug_log.new_run(project_id)
    debug_log.pipeline_start(project_id, manifest)

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_stream_line)

    _t0_pipeline = time.perf_counter()
    try:
        append_event(project_id, AgentEvent(kind="pipeline.started",
                                            payload={"idea": manifest["idea"]}))
        update_manifest(project_id, {"status": "running"})
        _ws(emit, project_id, "pipeline_started")
        debug_log.ui_state(project_id,
            "Todos los nodos = idle/gris | Tab 'Ejecución' activo | Spinner en cabecera",
            "F5 → status=running → UI muestra pipeline vacío con nodos grises")

        # 1. Env check
        debug_log.stage(project_id, "env_check")
        cmd_env = [sys.executable, str(CHECK_ENV)]
        t0 = time.perf_counter()
        result = subprocess.run(cmd_env, capture_output=True, text=True)
        debug_log.subprocess_result(project_id, "check_env.py", cmd_env, result,
                                    time.perf_counter() - t0)
        if result.returncode != 0:
            msg = (result.stdout + result.stderr)[:500]
            debug_log.error(project_id, f"Env check FAILED: {msg}")
            append_event(project_id, AgentEvent(kind="pipeline.failed",
                                                payload={"reason": "env_check", "detail": msg}))
            update_manifest(project_id, {"status": "env_failed"})
            _ws(emit, project_id, "env_check_failed", message=msg)
            debug_log.ui_state(project_id,
                "Nodo env_check = ERROR (rojo) | UI muestra banner de error con el mensaje de fallo",
                "F5 → status=env_failed → UI muestra banner de error, todos los nodos bloqueados")
            debug_log.pipeline_end(project_id, "env_failed", time.perf_counter() - _t0_pipeline)
            return
        _ws(emit, project_id, "env_check_ok", output=result.stdout)
        debug_log.ui_state(project_id,
            "Env check = OK (verde/check) | Pipeline listo para continuar")

        # 2. Researcher (optional — user can skip from the start-video form)
        if manifest.get("skip_research"):
            debug_log.info(project_id, "Researcher skipped by user — jumping straight to Stage 2")
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
            run_pipeline_after_plugins(project_id, approved_plugins=[], emit=emit)
            return

        debug_log.stage(project_id, "researcher")
        _ws(emit, project_id, "agent_started", agent="researcher")
        debug_log.ui_state(project_id,
            "Nodo 'Researcher' = RUNNING (azul/animado) | Panel lateral vacío hasta output | "
            "Resto de nodos = idle | Usuario puede clicar el nodo para ver logs en vivo")
        _check_cancel(project_id)
        plugins = researcher.run(project_id, manifest["idea"], proj)
        debug_log.info(project_id, f"Researcher proposed {len(plugins)} plugin(s): {[p.get('name') for p in plugins]}")
        _ws(emit, project_id, "plugins_proposed", plugins=plugins)
        update_manifest(project_id, {"status": "awaiting_plugins", "plugins_proposal": plugins})
        append_event(project_id, AgentEvent(kind="pipeline.paused",
                                            payload={"reason": "awaiting_plugins"}))
        debug_log.ui_state(project_id,
            "Nodo 'Researcher' = DONE (verde) | Nodo 'Plugins Gate' = HIGHLIGHTED (amarillo) | "
            "Tab 'Plugins' aparece en la barra de navegación del proyecto | "
            "UI muestra checkboxes con los plugins propuestos, botón 'Confirmar selección'",
            "F5 → status=awaiting_plugins → UI redirige automáticamente a /project/{id}/plugins | "
            "Researcher=done, Plugins Gate=activo esperando acción humana")
        debug_log.info(project_id, "Pipeline paused — awaiting plugin approval from user")

    except PipelineCancelled as e:
        debug_log.warning(project_id, f"Pipeline cancelled: {e}")
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        debug_log.error(project_id, f"Unhandled exception in run_pipeline: {e}", e)
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

    debug_log.ensure_run(project_id)
    debug_log.stage(project_id, "plugins_install",
                    f"approved={approved_plugins or '[]'}")

    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "plugins"}))

        # 3a. Install user-approved plugins
        if approved_plugins:
            results = {}
            for pkg in approved_plugins:
                _check_cancel(project_id)
                debug_log.info(project_id, f"Installing plugin: {pkg}")
                res = install_plugin(pkg)
                results[pkg] = res
                debug_log.info(project_id, f"Plugin {pkg}: status={res.get('status')}  {res}")
                append_event(project_id, AgentEvent(
                    kind="tool.completed", agent="plugin_installer",
                    payload={"package": pkg, **res},
                ))
                _ws(emit, project_id, "log", message=f"Plugin {pkg}: {res['status']}")
            update_manifest(project_id, {"plugins": results})
            manifest = load_manifest(project_id)

        # 3b. Auto-install manim-voiceover
        _check_cancel(project_id)
        debug_log.info(project_id, "Auto-installing manim-voiceover[gtts]")
        vo_res = ensure_installed("manim-voiceover", extras="gtts")
        debug_log.info(project_id, f"manim-voiceover[gtts]: {vo_res}")
        append_event(project_id, AgentEvent(
            kind="tool.completed", agent="plugin_installer",
            payload={"package": "manim-voiceover", "auto": True, **vo_res},
        ))
        _ws(emit, project_id, "log", message=f"manim-voiceover[gtts]: {vo_res['status']}")
        _ws(emit, project_id, "plugins_installed")
        debug_log.ui_state(project_id,
            "Nodo 'Plugins Gate' = DONE (verde/check) | Pipeline continúa automáticamente | "
            "Nodo 'Planner' aparece como siguiente activo")

        _stage2_planner_through_scenes(project_id, emit)

    except PipelineCancelled as e:
        debug_log.warning(project_id, f"Pipeline cancelled during plugin/planner stage: {e}")
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        debug_log.error(project_id, f"Unhandled exception in run_pipeline_after_plugins: {e}", e)
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
        debug_log.stage(project_id, "planner")
        _ws(emit, project_id, "agent_started", agent="planner")
        debug_log.ui_state(project_id,
            "Nodo 'Planner' = RUNNING (azul/animado) | Panel lateral muestra '⏳ Generando con sonnet...' | "
            "Clicar el nodo abre el panel lateral con el progreso en vivo")
        outline = planner.run(
            project_id, manifest["idea"], proj,
            lang=lang,
            fmt=manifest.get("format", "youtube"),
            target_length=manifest.get("target_length", "60s"),
            plugin_context=plugin_context,
        )
        debug_log.info(project_id, f"Outline ready — {len(outline):,} chars")
        _ws(emit, project_id, "outline_ready", outline=outline)
        update_manifest(project_id, {"status": "planning_done"})
        debug_log.ui_state(project_id,
            "Nodo 'Planner' = DONE (verde) | Outline disponible (visible en panel lateral)")
    else:
        debug_log.info(project_id, "Reusing existing outline.md — skipping Planner")
        _ws(emit, project_id, "log", message="Reutilizando outline.md existente — saltando Planner")
        _ws(emit, project_id, "outline_ready", outline=outline)

    # 5. Beat Writer (skip if beats already provided)
    _check_cancel(project_id)
    if beats_by_scene is None:
        debug_log.stage(project_id, "beat_writer")
        _ws(emit, project_id, "agent_started", agent="beat_writer")
        debug_log.ui_state(project_id,
            "Nodo 'Beat Writer' = RUNNING (azul/animado) | Panel lateral muestra '⏳ Generando con sonnet...' | "
            "Planner = DONE (verde), flecha Planner→BeatWriter resaltada")
        beats_by_scene = beat_writer.run(
            project_id, outline, proj,
            lang=lang,
            fmt=manifest.get("format", "youtube"),
            target_length=manifest.get("target_length", "60s"),
        )
        debug_log.info(project_id, f"Beats ready — {len(beats_by_scene)} scene(s): {sorted(beats_by_scene.keys())}")
    else:
        debug_log.info(project_id, "Reusing existing beats — skipping Beat Writer")
        _ws(emit, project_id, "log", message="Reutilizando beats existentes — saltando Beat Writer")
    _ws(emit, project_id, "beats_ready", scenes=sorted(beats_by_scene.keys()))
    debug_log.ui_state(project_id,
        f"Nodo 'Beat Writer' = DONE (verde) | Beats listos para {len(beats_by_scene)} escena(s) | "
        "Siguiente: Coder + escenas en paralelo")

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
        outline, proj, plugin_context, lang,
        manifest.get("format", "youtube"), emit,
    )

    # After all scenes rendered, pause for per-scene human review
    update_manifest(project_id, {"status": "awaiting_scene_review"})
    append_event(project_id, AgentEvent(kind="pipeline.paused",
                                        payload={"reason": "awaiting_scene_review"}))
    _ws(emit, project_id, "log", message="Todas las escenas renderizadas — pendiente de revisión")
    # Dedicated event so the frontend re-fetches the manifest and re-applies
    # the baseline (without this, the UI stays stuck on the "running" snapshot).
    _ws(emit, project_id, "scenes_all_rendered")
    debug_log.ui_state(project_id,
        "Nodo 'Scene Review Gate' = HIGHLIGHTED (amarillo) con badge 'acción humana' | "
        "Todas las tarjetas de escena muestran preview.mp4 con botones Aprobar/Revisar | "
        "Tab de la escena se activa para que el usuario pueda revisar cada una",
        "F5 → status=awaiting_scene_review → UI muestra tarjetas de escena con reproductor inline | "
        "Nodos Coder/Visual QA = DONE (verde), Scene Review Gate = esperando usuario")


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
    fmt: str,
    emit: Emit,
) -> None:
    """Fan-out scene rendering across threads, collect results."""
    n_workers = min(len(scene_entries), MAX_SCENE_WORKERS)

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(
                _run_scene_initial,
                project_id, i, desc, outline, proj,
                plugin_context, lang, fmt, beats_by_scene.get(i), emit,
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
    fmt: str,
    beats_file: Path | None,
    emit: Emit,
) -> None:
    """Run Coder + render + QA for one scene. Called from a worker thread."""
    # Register stream emit for this thread so call_agent can send live lines
    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line",
            agent=agent, scene=scene_num, **entry)
    set_stream_emit(_stream_line)

    debug_log.stage(project_id, f"scene_{scene_num:02d}",
                    f"desc={scene_desc[:80]!r}")
    update_scene_state(project_id, scene_num, status="rendering")
    _ws(emit, project_id, "scene_started", scene=scene_num, description=scene_desc[:200])
    debug_log.ui_state(project_id,
        f"Tarjeta Escena {scene_num} = RENDERING (spinner azul) | "
        f"Nodo 'Coder' (escena {scene_num}) = RUNNING | "
        "Múltiples escenas pueden estar en este estado simultáneamente (hasta 4 workers en paralelo)")

    debug_log.stage(project_id, f"scene_{scene_num:02d} → coder")
    _ws(emit, project_id, "agent_started", agent="coder", scene=scene_num)
    scene_file, code_status = coder.run(
        project_id, scene_num, scene_desc, outline, proj,
        plugin_context=plugin_context,
        lang=lang,
        beats_file=beats_file,
        fmt=fmt,
    )

    if code_status == "failed":
        debug_log.error(project_id,
            f"Coder FAILED for scene {scene_num} after all fix cycles")
        _ws(emit, project_id, "render_failed", scene=scene_num, message="Max fix cycles reached")
        update_scene_state(project_id, scene_num, status="failed",
                           preview_path=None)
        _ws(emit, project_id, "scene_preview_ready", scene=scene_num, status="failed")
        debug_log.ui_state(project_id,
            f"Tarjeta Escena {scene_num} = ERROR (rojo) | Mensaje de error visible | "
            "Resto de escenas continúan en paralelo sin interrumpirse",
            f"F5 → scene_{scene_num:02d}.status=failed → Tarjeta muestra badge ERROR con mensaje")
        return

    debug_log.info(project_id, f"Scene {scene_num} code generated: {scene_file}")
    _ws(emit, project_id, "render_ok", scene=scene_num)
    debug_log.ui_state(project_id,
        f"Escena {scene_num}: código generado, render -ql en curso | "
        "Tarjeta = spinner 'Renderizando...'")
    preview_mp4, duration = _render_preview(scene_file, scene_num, proj, project_id)
    debug_log.info(project_id, f"Preview rendered: {preview_mp4}  duration={duration:.1f}s")
    frames = _extract_frames(preview_mp4, scene_num, proj)
    debug_log.info(project_id, f"Frames extracted: {len(frames)} PNG(s)")
    _ws(emit, project_id, "frames_extracted", scene=scene_num, count=len(frames))

    # Auto-QA pass
    for cycle in range(1, MAX_QA_CYCLES + 1):
        debug_log.stage(project_id, f"scene_{scene_num:02d} → visual_qa", f"cycle={cycle}")
        _ws(emit, project_id, "agent_started", agent="visual_qa",
            scene=scene_num, cycle=cycle)
        qa = visual_qa.run(project_id, scene_num, scene_desc, scene_file, frames, proj)
        if qa["status"] == "ok":
            debug_log.info(project_id, f"Visual QA PASSED  scene={scene_num}  cycle={cycle}")
            _ws(emit, project_id, "qa_ok", scene=scene_num)
            debug_log.ui_state(project_id,
                f"Escena {scene_num}: Visual QA = PASSED ✓ | "
                "Nodo 'Visual QA' = DONE (verde) | Tarjeta avanza a awaiting_review")
            break
        debug_log.warning(project_id,
            f"Visual QA issue  scene={scene_num}  cycle={cycle}  notes={qa['raw'][:300]}")
        _ws(emit, project_id, "qa_issue", scene=scene_num,
            cycle=cycle, notes=qa["raw"][:500])
        debug_log.ui_state(project_id,
            f"Escena {scene_num}: Visual QA detectó problemas (ciclo {cycle}/{MAX_QA_CYCLES}) | "
            "Nodo QA = WARNING (naranja) | Panel lateral muestra las notas de QA | "
            "Pipeline aplica auto-fix vía Coder.fix_with_feedback y re-renderiza")
        if cycle == MAX_QA_CYCLES:
            debug_log.warning(project_id,
                f"Visual QA DEGRADED  scene={scene_num}  max cycles reached")
            _ws(emit, project_id, "qa_degraded", scene=scene_num)
            debug_log.ui_state(project_id,
                f"Escena {scene_num}: Visual QA DEGRADED — ciclos agotados | "
                "Nodo QA = DEGRADED (naranja oscuro) | Tarjeta avanza igual a awaiting_review con badge de advertencia")
            break
        debug_log.stage(project_id, f"scene_{scene_num:02d} → coder.fix", f"cycle={cycle}")
        _ws(emit, project_id, "agent_started", agent="coder",
            scene=scene_num, phase="qa_fix")
        coder.fix_with_feedback(project_id, scene_file, qa["raw"], scene_num)
        preview_mp4, duration = _render_preview(scene_file, scene_num, proj, project_id)
        debug_log.info(project_id,
            f"Re-rendered after QA fix  scene={scene_num}  duration={duration:.1f}s")
        frames = _extract_frames(preview_mp4, scene_num, proj)

    update_scene_state(project_id, scene_num, status="awaiting_review",
                       preview_path=str(preview_mp4))
    debug_log.info(project_id,
        f"Scene {scene_num} COMPLETE → awaiting_review  preview={preview_mp4}")
    _ws(emit, project_id, "scene_preview_ready", scene=scene_num,
        status="awaiting_review", preview_path=str(preview_mp4))
    debug_log.ui_state(project_id,
        f"Tarjeta Escena {scene_num} = AWAITING REVIEW (amarillo) | "
        "Reproductor de vídeo inline activo con preview.mp4 | "
        "Botones 'Aprobar escena' y 'Solicitar revisión' visibles | "
        "Resto de escenas paralelas pueden seguir en distintos estados",
        f"F5 → scene_{scene_num:02d}.status=awaiting_review → Tarjeta muestra preview + botones de acción")


# ── User revision: re-roll one scene ────────────────────────────────────────

def run_scene_revision(project_id: str, scene_num: int, feedback: str, emit: Emit) -> None:
    """Apply user feedback to a single scene, re-render, re-QA."""
    debug_log.ensure_run(project_id)
    debug_log.stage(project_id, f"scene_{scene_num:02d}_revision",
                    f"feedback={feedback[:80]!r}")

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line",
            agent=agent, scene=scene_num, **entry)
    set_stream_emit(_stream_line)

    proj = project_path(project_id)
    manifest = load_manifest(project_id)
    lang = manifest.get("lang", "es")
    fmt = manifest.get("format", "youtube")
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
    debug_log.ui_state(project_id,
        f"Tarjeta Escena {scene_num} = REVISING (azul/spinner) | "
        "Feedback del usuario registrado | Coder revisando la escena con el feedback",
        f"F5 → scene_{scene_num:02d}.status=revising → Tarjeta muestra spinner 'Revisando...' | "
        "Resto de escenas no se ven afectadas")

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
            fmt=fmt,
        )

        if code_status == "failed":
            update_scene_state(project_id, scene_num, status="awaiting_review")
            _ws(emit, project_id, "scene_preview_ready", scene=scene_num,
                status="awaiting_review", message="Revision rendered with errors")
            return

        preview_mp4, duration = _render_preview(scene_file, scene_num, proj, project_id)
        debug_log.info(project_id,
            f"Re-rendered after user revision  scene={scene_num}  duration={duration:.1f}s")
        frames = _extract_frames(preview_mp4, scene_num, proj)
        _ws(emit, project_id, "frames_extracted", scene=scene_num, count=len(frames))

        # Re-run QA
        for cycle in range(1, MAX_QA_CYCLES + 1):
            debug_log.stage(project_id, f"scene_{scene_num:02d}_revision → visual_qa",
                            f"cycle={cycle}")
            _ws(emit, project_id, "agent_started", agent="visual_qa",
                scene=scene_num, cycle=cycle)
            qa = visual_qa.run(project_id, scene_num, scene_desc, scene_file, frames, proj)
            if qa["status"] == "ok":
                debug_log.info(project_id,
                    f"Visual QA PASSED after revision  scene={scene_num}  cycle={cycle}")
                _ws(emit, project_id, "qa_ok", scene=scene_num)
                break
            debug_log.warning(project_id,
                f"QA issue after revision  scene={scene_num}  cycle={cycle}  {qa['raw'][:200]}")
            _ws(emit, project_id, "qa_issue", scene=scene_num,
                cycle=cycle, notes=qa["raw"][:500])
            if cycle == MAX_QA_CYCLES:
                _ws(emit, project_id, "qa_degraded", scene=scene_num)
                break
            coder.fix_with_feedback(project_id, scene_file, qa["raw"], scene_num)
            preview_mp4, _ = _render_preview(scene_file, scene_num, proj, project_id)
            frames = _extract_frames(preview_mp4, scene_num, proj)

        update_scene_state(project_id, scene_num, status="awaiting_review",
                           preview_path=str(preview_mp4))
        _ws(emit, project_id, "scene_preview_ready", scene=scene_num,
            status="awaiting_review", preview_path=str(preview_mp4))

    except PipelineCancelled as e:
        debug_log.warning(project_id, f"Scene {scene_num} revision cancelled: {e}")
        update_scene_state(project_id, scene_num, status="awaiting_review")
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        debug_log.error(project_id, f"Scene {scene_num} revision failed: {e}", e)
        update_scene_state(project_id, scene_num, status="awaiting_review")
        _ws(emit, project_id, "error", message=f"Scene {scene_num} revision failed: {e}")


# ── Stage 3: final render (after all scenes approved) ───────────────────────

def run_finalize(project_id: str, emit: Emit) -> None:
    """Render final video from all approved scenes, then pause for curator."""
    debug_log.ensure_run(project_id)
    debug_log.stage(project_id, "editor_finalize")
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
        debug_log.ui_state(project_id,
            "Nodo 'Editor' = RUNNING (azul/animado) | "
            "Scene Review Gate = DONE (verde) | Todas las escenas aprobadas | "
            "UI muestra 'Generando video final...' | Tab Ejecución activo",
            "F5 → status=scenes_approved → UI muestra Editor como running, nodos anteriores como done")

        # Collect scene files in order
        scene_files: list[Path] = []
        all_states = get_all_scene_states(project_id)
        for key in sorted(all_states.keys()):
            sf = proj / "scenes" / f"scene_{key}.py"
            if sf.exists():
                scene_files.append(sf)

        debug_log.info(project_id,
            f"Editor: {len(scene_files)} scene file(s) → HQ render + concat")
        _ws(emit, project_id, "agent_started", agent="editor")
        final_video = editor.run(scene_files, proj, lang=lang, project_id=project_id)

        emit_grade(project_id, "editor", None, grade_video_exists(final_video))
        emit_grade(project_id, "editor", None, grade_video_playable(final_video))
        debug_log.info(project_id, f"Final video ready: {final_video}")
        _ws(emit, project_id, "edit_done", video=str(final_video))
        update_manifest(project_id, {"status": "awaiting_review",
                                     "final_video": str(final_video)})
        append_event(project_id, AgentEvent(kind="pipeline.paused",
                                            payload={"reason": "awaiting_review"}))
        debug_log.ui_state(project_id,
            "Nodo 'Editor' = DONE (verde) | "
            "Tab 'Revisar' aparece en la navegación con indicador de notificación | "
            "Reproductor de vídeo final visible con botón 'Exportar a Drive' | "
            "Formulario de aprobación con campo de feedback | Botón 'Aprobar y generar aprendizajes'",
            "F5 → status=awaiting_review → UI redirige a /project/{id}/review | "
            "Video final reproducible, formulario de feedback disponible")

    except PipelineCancelled as e:
        debug_log.warning(project_id, f"Finalize cancelled: {e}")
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        debug_log.error(project_id, f"Finalize failed: {e}", e)
        _handle_pipeline_exception(project_id, emit, e, "finalize")


# ── Curator ──────────────────────────────────────────────────────────────────

def run_curator(project_id: str, emit: Emit) -> None:
    debug_log.ensure_run(project_id)
    debug_log.stage(project_id, "curator")
    proj = project_path(project_id)

    def _stream_line(agent: str, scene: int | None, entry: dict) -> None:
        _ws(emit, project_id, "agent_stream_line", agent=agent, scene=scene, **entry)
    set_stream_emit(_stream_line)

    try:
        append_event(project_id, AgentEvent(kind="pipeline.resumed",
                                            payload={"after": "review"}))
        _ws(emit, project_id, "agent_started", agent="curator")
        debug_log.ui_state(project_id,
            "Nodo 'Curator' = RUNNING (azul/animado) | "
            "UI muestra 'Generando aprendizajes...' | Panel lateral con progreso del Curator")
        result = curator.run(project_id, proj)
        debug_log.info(project_id,
            f"Curator done — learnings={len(result.get('learnings',''))} chars  "
            f"patches={list(result.get('patches',{}).keys())}")
        _ws(emit, project_id, "curator_done",
            learnings=result.get("learnings", "")[:300],
            patches=list(result.get("patches", {}).keys()))
        update_manifest(project_id, {"status": "curated"})
        debug_log.ui_state(project_id,
            "Nodo 'Curator' = DONE (verde) — PIPELINE COMPLETO ✓ | "
            "Tab 'Aprendizajes' activo con diff viewer por hunks | "
            "Cada hunk tiene botón Aceptar/Rechazar para actualizar la skill | "
            "Todos los nodos del pipeline = DONE (verde)",
            "F5 → status=curated → UI muestra tab Aprendizajes con el diff viewer | "
            "Pipeline completo, todos los nodos verdes")
        debug_log.pipeline_end(project_id, "curated", 0)
        append_event(project_id, AgentEvent(kind="pipeline.completed", payload={}))
    except PipelineCancelled as e:
        debug_log.warning(project_id, f"Curator cancelled: {e}")
        _on_cancelled(project_id, emit, str(e))
    except Exception as e:
        debug_log.error(project_id, f"Curator failed: {e}", e)
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


def _render_preview(
    scene_file: Path, scene_num: int, proj: Path, project_id: str = ""
) -> tuple[Path, float]:
    scene_name = _get_scene_name(scene_file)
    render_dir = proj / "renders" / f"scene_{scene_num:02d}"
    render_dir.mkdir(parents=True, exist_ok=True)
    out = render_dir / "preview.mp4"
    cmd = ["manim", "-ql", "--output_file", str(out), str(scene_file), scene_name]
    debug_log.info(project_id, f"Render preview  scene={scene_num}  →  {out.name}")
    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    debug_log.subprocess_result(
        project_id, f"manim -ql scene {scene_num}", cmd, result,
        time.perf_counter() - t0,
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
