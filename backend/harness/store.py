"""Atomic persistence of the event log.

If the backend crashes mid-pipeline, the on-disk log lets us resume from the
last consistent state — Anthropic's checkpointing pattern for long-running agents.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from harness.events import EventLog, AgentEvent

PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"


def log_path(project_id: str) -> Path:
    return PROJECTS_ROOT / project_id / "events.jsonl"


def append_event(project_id: str, event: AgentEvent) -> None:
    """Atomic append — survives crashes (each line is self-contained)."""
    p = log_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = event.model_dump_json() + "\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        os.fsync(f.fileno())


def load_log(project_id: str) -> EventLog:
    p = log_path(project_id)
    log = EventLog(project_id=project_id)
    if not p.exists():
        return log
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            log.events.append(AgentEvent.model_validate_json(line))
        except Exception:
            # Corrupted line — skip but don't crash. Real systems would alert.
            continue
    return log


def write_snapshot(project_id: str, data: dict) -> None:
    """For non-event state like the resolved status. Atomic via temp+rename."""
    p = PROJECTS_ROOT / project_id / "status.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
