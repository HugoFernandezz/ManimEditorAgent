"""Helpers to read/write project manifests and files."""
from __future__ import annotations
import json
import re
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

PROJECTS_ROOT = Path(__file__).parent.parent / "projects"

# Protects manifest read-mutate-write against concurrent scene threads
_manifest_lock = threading.RLock()


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60] or "video"


def create_project(name: str, description: str = "") -> dict[str, Any]:
    """Create an empty project (no video configured yet)."""
    slug = _slug(name)
    base = PROJECTS_ROOT / slug
    suffix = 0
    while base.exists():
        suffix += 1
        base = PROJECTS_ROOT / f"{slug}-{suffix}"
    for sub in ("scenes", "renders", "audio", "final", "learnings", "beats"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "id": base.name,
        "name": name,
        "description": description,
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Video fields — populated when the user starts a video
        "idea": None,
        "lang": "es",
        "format": "youtube",
        "target_length": "60s",
        "voice_profile": None,
        "export_langs": [],
        "tts_backend": "stub",
        "plugins": [],
        "scenes": {},
    }
    _write_json(base / "manifest.json", manifest)
    return manifest


def load_manifest(project_id: str) -> dict[str, Any]:
    return _read_json(PROJECTS_ROOT / project_id / "manifest.json")


def update_manifest(project_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    with _manifest_lock:
        m = load_manifest(project_id)
        m.update(updates)
        _write_json(PROJECTS_ROOT / project_id / "manifest.json", m)
        return m


def list_projects() -> list[dict[str, Any]]:
    result = []
    if not PROJECTS_ROOT.exists():
        return result
    for p in sorted(PROJECTS_ROOT.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        manifest_path = p / "manifest.json"
        if manifest_path.exists():
            result.append(_read_json(manifest_path))
    return result


def project_path(project_id: str) -> Path:
    return PROJECTS_ROOT / project_id


# ── Per-scene state helpers ──────────────────────────────────────────────────

def init_scene_states(project_id: str, scene_descs: list[str]) -> None:
    """Create the `scenes` dict in the manifest with N pending entries.
    Called once after the outline is parsed, before parallel rendering starts.
    """
    scenes: dict[str, dict] = {}
    for i, desc in enumerate(scene_descs, start=1):
        key = f"{i:02d}"
        scenes[key] = {
            "status": "pending",
            "preview_path": None,
            "feedback_history": [],
            "scene_desc": desc[:300],
        }
    update_manifest(project_id, {"scenes": scenes})


def update_scene_state(project_id: str, scene_num: int, **fields: Any) -> None:
    """Atomic read-mutate-write for a single scene entry.

    Using the module-level lock so concurrent scene threads don't race.
    """
    key = f"{scene_num:02d}"
    with _manifest_lock:
        m = load_manifest(project_id)
        scenes: dict = m.setdefault("scenes", {})
        entry = scenes.setdefault(key, {"status": "pending", "preview_path": None,
                                         "feedback_history": [], "scene_desc": ""})
        entry.update(fields)
        _write_json(PROJECTS_ROOT / project_id / "manifest.json", m)


def get_scene_state(project_id: str, scene_num: int) -> dict[str, Any]:
    key = f"{scene_num:02d}"
    m = load_manifest(project_id)
    return m.get("scenes", {}).get(key, {})


def get_all_scene_states(project_id: str) -> dict[str, dict[str, Any]]:
    return load_manifest(project_id).get("scenes", {})


def all_scenes_approved(project_id: str) -> bool:
    states = get_all_scene_states(project_id)
    if not states:
        return False
    return all(s.get("status") == "approved" for s in states.values())


# ── JSON helpers ─────────────────────────────────────────────────────────────

def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
