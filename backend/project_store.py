"""Helpers to read/write project manifests and files."""
from __future__ import annotations
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

PROJECTS_ROOT = Path(__file__).parent.parent / "projects"


def _slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:60] or "video"


def create_project(manifest: dict[str, Any]) -> dict[str, Any]:
    slug = _slug(manifest.get("idea", "video"))
    base = PROJECTS_ROOT / slug
    suffix = 0
    while base.exists():
        suffix += 1
        base = PROJECTS_ROOT / f"{slug}-{suffix}"
    base.mkdir(parents=True, exist_ok=True)
    (base / "scenes").mkdir()
    (base / "renders").mkdir()
    (base / "audio").mkdir()
    (base / "final").mkdir()
    (base / "learnings").mkdir()
    manifest["id"] = base.name
    manifest["status"] = "created"
    manifest["created_at"] = datetime.now(timezone.utc).isoformat()
    manifest["plugins"] = []
    _write_json(base / "manifest.json", manifest)
    return manifest


def load_manifest(project_id: str) -> dict[str, Any]:
    return _read_json(PROJECTS_ROOT / project_id / "manifest.json")


def update_manifest(project_id: str, updates: dict[str, Any]) -> dict[str, Any]:
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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
