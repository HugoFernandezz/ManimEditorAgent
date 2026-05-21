"""FastAPI backend for ManimEditorAgent."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from events import PipelineEvent
from project_store import (
    create_project,
    list_projects,
    load_manifest,
    update_manifest,
    project_path,
)
from orchestrator import run_pipeline, run_pipeline_after_plugins, run_curator
from tools.skill_diff import apply_hunk

PROJECTS_ROOT = Path(__file__).parent.parent / "projects"

app = FastAPI(title="ManimEditorAgent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections keyed by project_id
_ws_clients: dict[str, list[WebSocket]] = {}
# Active background tasks
_pipeline_tasks: dict[str, asyncio.Task] = {}


# ── Models ──────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    idea: str
    lang: str = "es"
    audience: str = "general"
    target_length: str = "60s"
    voice_profile: str | None = None
    export_langs: list[str] = []
    tts_backend: str = "stub"


class PluginsConfirmRequest(BaseModel):
    approved: list[str]  # list of package names user approved


class ReviewRequest(BaseModel):
    approved: bool
    feedback: str = ""
    what_worked: str = ""
    what_didnt: str = ""


class PatchHunkRequest(BaseModel):
    file_rel: str   # e.g. "references/troubleshooting.md"
    hunk: str       # unified diff hunk to apply


# ── WebSocket broadcasting ───────────────────────────────────────────────────

def _emit(event: PipelineEvent) -> None:
    """Synchronous emit called from background thread via asyncio."""
    pid = event.project_id
    loop = asyncio.get_event_loop()
    if pid in _ws_clients:
        msg = event.to_json()
        for ws in list(_ws_clients[pid]):
            asyncio.run_coroutine_threadsafe(_safe_send(ws, msg), loop)


async def _safe_send(ws: WebSocket, msg: str) -> None:
    try:
        await ws.send_text(msg)
    except Exception:
        pass


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/projects")
async def get_projects() -> list[dict]:
    return list_projects()


@app.post("/projects", status_code=201)
async def create_new_project(req: CreateProjectRequest) -> dict:
    manifest = create_project(req.model_dump())
    pid = manifest["id"]
    _ws_clients[pid] = []
    # Start pipeline in background
    task = asyncio.create_task(_run_pipeline_bg(pid))
    _pipeline_tasks[pid] = task
    return manifest


@app.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    try:
        return load_manifest(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found")


@app.post("/projects/{project_id}/plugins/confirm")
async def confirm_plugins(project_id: str, req: PluginsConfirmRequest) -> dict:
    try:
        manifest = load_manifest(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found")
    if manifest.get("status") != "awaiting_plugins":
        raise HTTPException(400, "Project is not awaiting plugin confirmation")
    task = asyncio.create_task(_run_after_plugins_bg(project_id, req.approved))
    _pipeline_tasks[project_id] = task
    return {"ok": True}


@app.post("/projects/{project_id}/review")
async def submit_review(project_id: str, req: ReviewRequest) -> dict:
    try:
        manifest = load_manifest(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "Project not found")

    feedback = req.model_dump()
    proj = project_path(project_id)
    (proj / "feedback.json").write_text(
        json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    update_manifest(project_id, {"status": "review_submitted"})
    _emit(PipelineEvent(kind="review_submitted", project_id=project_id, payload=feedback))

    if req.approved:
        task = asyncio.create_task(_run_curator_bg(project_id))
        _pipeline_tasks[project_id] = task

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
        _emit(PipelineEvent(kind="patch_applied", project_id=project_id, payload={"file": req.file_rel}))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/projects/{project_id}/video")
async def get_video(project_id: str, lang: str = "es"):
    manifest = load_manifest(project_id)
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


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/{project_id}")
async def ws_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    _ws_clients.setdefault(project_id, []).append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive; client sends pings
    except WebSocketDisconnect:
        _ws_clients[project_id].remove(websocket)


# ── Background task wrappers ─────────────────────────────────────────────────

async def _run_pipeline_bg(project_id: str) -> None:
    await asyncio.to_thread(
        lambda: asyncio.run(_async_emit_wrapper(run_pipeline, project_id))
    )


async def _run_after_plugins_bg(project_id: str, approved: list[str]) -> None:
    await asyncio.to_thread(
        lambda: asyncio.run(_async_emit_wrapper(run_pipeline_after_plugins, project_id, approved))
    )


async def _run_curator_bg(project_id: str) -> None:
    await asyncio.to_thread(
        lambda: asyncio.run(_async_emit_wrapper(run_curator, project_id))
    )


async def _async_emit_wrapper(coro_fn, project_id: str, *args) -> None:
    queue: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()

    def emit_sync(event: PipelineEvent) -> None:
        queue.put_nowait(event)

    async def drain():
        while True:
            event = await queue.get()
            if event is None:
                break
            _emit(event)

    drain_task = asyncio.create_task(drain())
    try:
        await coro_fn(project_id, *args, emit_sync)
    finally:
        await queue.put(None)
        await drain_task
