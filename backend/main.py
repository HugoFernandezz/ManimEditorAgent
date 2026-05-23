"""FastAPI backend for ManimEditorAgent."""
from __future__ import annotations
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from events import PipelineEvent
from project_store import (
    create_project,
    list_projects,
    load_manifest,
    update_manifest,
    project_path,
)
from orchestrator import (
    run_pipeline, run_pipeline_after_plugins, run_curator,
    run_scene_revision, run_finalize, run_resume,
    detect_resume_options, request_cancel, RESUME_STEPS,
)
from project_store import update_scene_state, get_all_scene_states, all_scenes_approved
from tools.skill_diff import apply_hunk
from harness.store import load_log


SKILL_ROOT = Path(__file__).parent.parent / ".agents" / "skills" / "manim"
_ALLOWED_SKILL_FILES = frozenset({
    "SKILL.md",
    "references/api-cheatsheet.md",
    "references/troubleshooting.md",
    "references/3b1b-style.md",
    "references/narration.md",
    "references/manimgl-diff.md",
    "templates/basic.py",
    "templates/math.py",
    "templates/threed.py",
    "templates/voiceover.py",
})

# Active WebSocket connections keyed by project_id
_ws_clients: dict[str, list[WebSocket]] = {}
# Background pipeline tasks keyed by project_id (kept alive across the request)
_pipeline_tasks: dict[str, asyncio.Task] = {}
# The main event loop — captured at startup so threads can safely schedule sends
_main_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def _lifespan(_: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    try:
        yield
    finally:
        for t in list(_pipeline_tasks.values()):
            t.cancel()
        _pipeline_tasks.clear()


app = FastAPI(title="ManimEditorAgent", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ──────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class StartVideoRequest(BaseModel):
    idea: str
    lang: str = "es"
    format: str = "youtube"
    target_length: str = "60s"
    voice_profile: str | None = None
    export_langs: list[str] = []
    tts_backend: str = "stub"
    skip_research: bool = False


class PluginsConfirmRequest(BaseModel):
    approved: list[str]


class ReviewRequest(BaseModel):
    approved: bool
    feedback: str = ""
    what_worked: str = ""
    what_didnt: str = ""


class PatchHunkRequest(BaseModel):
    file_rel: str
    hunk: str


class ReviseSceneRequest(BaseModel):
    feedback: str


class SkillUpdateRequest(BaseModel):
    content: str


class ResumeRequest(BaseModel):
    from_step: str   # "planner" | "beats" | "scenes"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _manifest_or_404(project_id: str) -> dict:
    try:
        return load_manifest(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found")


def _emit(event: PipelineEvent) -> None:
    """Called from a worker thread — schedules sends on the main event loop."""
    if _main_loop is None:
        return
    msg = event.to_json()
    for ws in list(_ws_clients.get(event.project_id, [])):
        asyncio.run_coroutine_threadsafe(_safe_send(ws, msg), _main_loop)


async def _safe_send(ws: WebSocket, msg: str) -> None:
    try:
        await ws.send_text(msg)
    except Exception:
        pass


def _spawn_pipeline(project_id: str, coro_factory) -> None:
    """Schedule a background coroutine, tracking it so it isn't GC'd mid-run.

    Before spawning, request_cancel kills any in-flight `claude` subprocesses
    for this project AND waits briefly so orphaned worker threads can
    reach their except-handler and record themselves as 'superseded'
    (rather than overwriting the new run's status on the manifest).
    Cancelling the asyncio.Task alone is not enough: Task.cancel() only
    raises CancelledError in the awaiter, not in the inner thread blocked
    on subprocess.communicate().
    """
    # Kill any subprocesses + give orphan threads time to settle.
    request_cancel(project_id)
    existing = _pipeline_tasks.pop(project_id, None)
    if existing and not existing.done():
        existing.cancel()
    task = asyncio.create_task(coro_factory())
    _pipeline_tasks[project_id] = task
    task.add_done_callback(lambda _t: _pipeline_tasks.pop(project_id, None))


# ── Project routes ──────────────────────────────────────────────────────────

@app.get("/projects")
async def get_projects() -> list[dict]:
    return list_projects()


@app.post("/projects", status_code=201)
async def create_new_project(req: CreateProjectRequest) -> dict:
    manifest = create_project(req.name, req.description)
    _ws_clients[manifest["id"]] = []
    return manifest


@app.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    return _manifest_or_404(project_id)


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str) -> dict:
    import shutil
    _manifest_or_404(project_id)
    request_cancel(project_id)
    existing = _pipeline_tasks.pop(project_id, None)
    if existing and not existing.done():
        existing.cancel()
    for ws in list(_ws_clients.pop(project_id, [])):
        try:
            await ws.close()
        except Exception:
            pass
    shutil.rmtree(project_path(project_id), ignore_errors=True)
    return {"ok": True}


_RESTARTABLE = frozenset({
    "draft", "error", "env_failed", "stopped",
    # Mid-run statuses that become stuck after a backend restart:
    "running", "awaiting_plugins", "planning_done",
})

@app.post("/projects/{project_id}/start-video", status_code=202)
async def start_video(project_id: str, req: StartVideoRequest) -> dict:
    manifest = _manifest_or_404(project_id)
    if manifest.get("status") not in _RESTARTABLE:
        raise HTTPException(400, f"Cannot start video from status '{manifest['status']}'")
    update_manifest(project_id, {**req.model_dump(), "status": "running"})
    _ws_clients.setdefault(project_id, [])
    _spawn_pipeline(project_id, lambda: asyncio.to_thread(run_pipeline, project_id, _emit))
    return {"ok": True}


@app.post("/projects/{project_id}/stop")
async def stop_pipeline(project_id: str) -> dict:
    """Cancel the running pipeline.

    Signals cooperative cancellation AND kills any in-flight `claude`
    subprocesses for this project. The orchestrator marks status=stopped.
    """
    _manifest_or_404(project_id)
    killed = request_cancel(project_id)
    existing = _pipeline_tasks.pop(project_id, None)
    if existing and not existing.done():
        existing.cancel()
    _emit(PipelineEvent(kind="log", project_id=project_id,
                        payload={"message": f"Pipeline detenido — {killed} subprocesos terminados"}))
    return {"ok": True, "killed_subprocesses": killed}


@app.get("/projects/{project_id}/resume-options")
async def get_resume_options(project_id: str) -> dict:
    """Inspect on-disk artifacts and return which resume checkpoints are available."""
    _manifest_or_404(project_id)
    return detect_resume_options(project_id)


@app.post("/projects/{project_id}/resume", status_code=202)
async def resume_pipeline(project_id: str, req: ResumeRequest) -> dict:
    """Restart the pipeline from a specific checkpoint, reusing existing artifacts."""
    _manifest_or_404(project_id)
    if req.from_step not in RESUME_STEPS:
        raise HTTPException(400, f"from_step must be one of {RESUME_STEPS}")
    # Validate the checkpoint is actually available
    opts = detect_resume_options(project_id)
    if not opts[req.from_step]["available"]:
        raise HTTPException(400, f"Resume point not available: {opts[req.from_step]['detail']}")
    update_manifest(project_id, {"status": "running"})
    _ws_clients.setdefault(project_id, [])
    _spawn_pipeline(
        project_id,
        lambda: asyncio.to_thread(run_resume, project_id, req.from_step, _emit),
    )
    return {"ok": True, "from_step": req.from_step}


@app.post("/projects/{project_id}/plugins/confirm")
async def confirm_plugins(project_id: str, req: PluginsConfirmRequest) -> dict:
    manifest = _manifest_or_404(project_id)
    if manifest.get("status") != "awaiting_plugins":
        raise HTTPException(400, "Project is not awaiting plugin confirmation")
    # Mark running BEFORE spawning so the status gate is closed immediately
    # (prevents double-confirm if user navigates back and clicks again)
    update_manifest(project_id, {"status": "running"})
    _spawn_pipeline(
        project_id,
        lambda: asyncio.to_thread(run_pipeline_after_plugins, project_id, req.approved, _emit),
    )
    return {"ok": True}


@app.post("/projects/{project_id}/review")
async def submit_review(project_id: str, req: ReviewRequest) -> dict:
    _manifest_or_404(project_id)
    feedback = req.model_dump()
    proj = project_path(project_id)
    (proj / "feedback.json").write_text(
        json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    update_manifest(project_id, {"status": "review_submitted"})
    _emit(PipelineEvent(kind="review_submitted", project_id=project_id, payload=feedback))

    if req.approved:
        _spawn_pipeline(
            project_id,
            lambda: asyncio.to_thread(run_curator, project_id, _emit),
        )
    return {"ok": True}


@app.get("/projects/{project_id}/learnings")
async def get_learnings(project_id: str) -> dict:
    proj = project_path(project_id)
    notes_path = proj / "learnings" / "notes.md"
    patch_path = proj / "learnings" / "skill_patch.diff"
    return {
        "notes": notes_path.read_text(encoding="utf-8") if notes_path.exists() else "",
        "diff": patch_path.read_text(encoding="utf-8") if patch_path.exists() else "",
    }


@app.post("/projects/{project_id}/learnings/apply")
async def apply_patch(project_id: str, req: PatchHunkRequest) -> dict:
    try:
        apply_hunk(req.file_rel, req.hunk)
    except Exception as e:
        raise HTTPException(500, str(e))
    _emit(PipelineEvent(kind="patch_applied", project_id=project_id, payload={"file": req.file_rel}))
    return {"ok": True}


@app.get("/projects/{project_id}/video")
async def get_video(project_id: str, lang: str = "es"):
    _manifest_or_404(project_id)
    video_path = project_path(project_id) / "final" / f"video_{lang}.mp4"
    if not video_path.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(str(video_path), media_type="video/mp4")


@app.get("/projects/{project_id}/frames/{scene_num}")
async def get_frames(project_id: str, scene_num: int) -> list[str]:
    frames_dir = project_path(project_id) / "renders" / f"scene_{scene_num:02d}" / "frames"
    if not frames_dir.exists():
        return []
    return [f.name for f in sorted(frames_dir.glob("*.png"))]


@app.get("/projects/{project_id}/frames/{scene_num}/{filename}")
async def get_frame_image(project_id: str, scene_num: int, filename: str):
    img = project_path(project_id) / "renders" / f"scene_{scene_num:02d}" / "frames" / filename
    if not img.exists():
        raise HTTPException(404)
    return FileResponse(str(img), media_type="image/png")


# ── Harness telemetry endpoints ──────────────────────────────────────────────

@app.get("/projects/{project_id}/trace")
async def get_trace(project_id: str, limit: int = 500) -> list[dict]:
    """Full event-sourced trace for debugging and grading."""
    log = load_log(project_id)
    return [e.model_dump() for e in log.events[-limit:]]


@app.get("/projects/{project_id}/metrics")
async def get_metrics(project_id: str) -> dict:
    """Aggregated per-agent metrics: calls, retries, duration, est. cost."""
    log = load_log(project_id)
    agg: dict[str, dict] = {}
    for e in log.events:
        if not e.agent:
            continue
        if e.kind == "metric.emitted":
            a = agg.setdefault(e.agent, _empty_agent_bucket())
            a["calls"] += 1
            a["total_duration_ms"] += e.payload.get("duration_ms", 0)
            a["total_input_chars"] += e.payload.get("input_chars", 0)
            a["total_output_chars"] += e.payload.get("output_chars", 0)
            a["total_cost_usd"] += e.payload.get("cost_usd_estimate", 0.0)
            if e.payload.get("outcome") == "error":
                a["errors"] += 1
        elif e.kind == "agent.retry" and e.agent in agg:
            agg[e.agent]["retries"] += 1
        elif e.kind == "guardrail.violated" and e.agent in agg:
            agg[e.agent]["guardrail_violations"] += 1
    return {"agents": agg, "total_events": len(log.events)}


def _empty_agent_bucket() -> dict:
    return {
        "calls": 0, "total_duration_ms": 0, "total_input_chars": 0,
        "total_output_chars": 0, "errors": 0, "total_cost_usd": 0.0,
        "retries": 0, "guardrail_violations": 0,
    }


@app.get("/projects/{project_id}/grades")
async def get_grades(project_id: str) -> list[dict]:
    """All grader results for the project (deterministic + LLM-as-judge)."""
    log = load_log(project_id)
    return [
        {**e.payload, "kind": e.kind, "agent": e.agent, "scene": e.scene,
         "timestamp": e.timestamp}
        for e in log.events if e.kind in ("grader.passed", "grader.failed")
    ]


# ── Per-scene review API ─────────────────────────────────────────────────────

@app.get("/projects/{project_id}/scenes")
async def get_scenes(project_id: str) -> list[dict]:
    """Return scene list with status, preview URL, feedback history, and beats."""
    _manifest_or_404(project_id)
    proj = project_path(project_id)
    states = get_all_scene_states(project_id)
    result = []
    for key in sorted(states.keys()):
        num = int(key)
        entry = dict(states[key])
        entry["scene"] = num
        # Build preview URL if the file exists
        preview = proj / "renders" / f"scene_{key}" / "preview.mp4"
        entry["preview_url"] = f"/projects/{project_id}/scenes/{num}/preview" if preview.exists() else None
        # Attach beats summary
        beats_file = proj / "beats" / f"scene_{key}.beats.json"
        if beats_file.exists():
            try:
                import json
                entry["beats"] = json.loads(beats_file.read_text(encoding="utf-8"))
            except Exception:
                entry["beats"] = []
        else:
            entry["beats"] = []
        result.append(entry)
    return result


@app.get("/projects/{project_id}/scenes/{scene_num}/preview")
async def get_scene_preview(project_id: str, scene_num: int):
    _manifest_or_404(project_id)
    preview = project_path(project_id) / "renders" / f"scene_{scene_num:02d}" / "preview.mp4"
    if not preview.exists():
        raise HTTPException(404, "Preview not ready yet")
    return FileResponse(str(preview), media_type="video/mp4")


@app.post("/projects/{project_id}/scenes/{scene_num}/approve")
async def approve_scene(project_id: str, scene_num: int) -> dict:
    _manifest_or_404(project_id)
    update_scene_state(project_id, scene_num, status="approved")
    _emit(PipelineEvent(kind="scene_approved", project_id=project_id,
                        payload={"scene": scene_num}))
    # Check if all scenes now approved
    if all_scenes_approved(project_id):
        from project_store import update_manifest
        update_manifest(project_id, {"status": "scenes_approved"})
        _emit(PipelineEvent(kind="scenes_all_approved", project_id=project_id, payload={}))
    return {"ok": True}


@app.post("/projects/{project_id}/scenes/{scene_num}/revise", status_code=202)
async def revise_scene(project_id: str, scene_num: int, req: ReviseSceneRequest) -> dict:
    _manifest_or_404(project_id)
    _ws_clients.setdefault(project_id, [])
    _spawn_pipeline(
        project_id,
        lambda: asyncio.to_thread(run_scene_revision, project_id, scene_num, req.feedback, _emit),
    )
    return {"ok": True}


@app.post("/projects/{project_id}/finalize", status_code=202)
async def finalize_project(project_id: str) -> dict:
    manifest = _manifest_or_404(project_id)
    if manifest.get("status") != "scenes_approved":
        raise HTTPException(400, "Not all scenes are approved yet")
    _ws_clients.setdefault(project_id, [])
    _spawn_pipeline(
        project_id,
        lambda: asyncio.to_thread(run_finalize, project_id, _emit),
    )
    return {"ok": True}


# ── Skill file editor ────────────────────────────────────────────────────────

@app.get("/skills")
async def list_skill_files() -> list[str]:
    return sorted(_ALLOWED_SKILL_FILES)


@app.get("/skills/{file_path:path}")
async def get_skill_file(file_path: str) -> dict:
    if file_path not in _ALLOWED_SKILL_FILES:
        raise HTTPException(403, "File not in allowlist")
    target = SKILL_ROOT / file_path
    if not target.exists():
        raise HTTPException(404, "File not found")
    return {"path": file_path, "content": target.read_text(encoding="utf-8")}


@app.put("/skills/{file_path:path}")
async def update_skill_file(file_path: str, req: SkillUpdateRequest) -> dict:
    if file_path not in _ALLOWED_SKILL_FILES:
        raise HTTPException(403, "File not in allowlist")
    target = SKILL_ROOT / file_path
    target.write_text(req.content, encoding="utf-8")
    return {"ok": True}


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/{project_id}")
async def ws_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    clients = _ws_clients.setdefault(project_id, [])
    clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive; client sends pings
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in clients:
            clients.remove(websocket)
