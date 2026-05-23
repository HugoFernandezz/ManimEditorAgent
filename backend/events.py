from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel


EventKind = Literal[
    "pipeline_started",
    "env_check_ok",
    "env_check_failed",
    "agent_started",
    "agent_finished",
    "agent_error",
    "plugins_proposed",
    "plugins_installed",
    "outline_ready",
    "beats_ready",
    "scene_started",
    "scene_preview_ready",
    "scene_approved",
    "scene_revising",
    "scenes_all_approved",
    "scenes_all_rendered",
    "finalizing",
    "render_ok",
    "render_failed",
    "frames_extracted",
    "qa_ok",
    "qa_issue",
    "qa_degraded",
    "edit_done",
    "review_submitted",
    "curator_done",
    "patch_applied",
    "agent_stream_line",
    "log",
    "error",
]


class PipelineEvent(BaseModel):
    kind: EventKind
    project_id: str
    payload: dict[str, Any] = {}

    def to_json(self) -> str:
        return self.model_dump_json()
