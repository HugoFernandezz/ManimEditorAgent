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
    "scene_started",
    "render_ok",
    "render_failed",
    "frames_extracted",
    "qa_ok",
    "qa_issue",
    "qa_degraded",
    "narration_ready",
    "edit_done",
    "review_submitted",
    "curator_done",
    "patch_applied",
    "log",
    "error",
]


class PipelineEvent(BaseModel):
    kind: EventKind
    project_id: str
    payload: dict[str, Any] = {}

    def to_json(self) -> str:
        return self.model_dump_json()
