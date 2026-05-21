"""Event-sourced state for the agent pipeline.

12-Factor #5: unify execution state and business state — derive everything from
a single events log. Enables pause/resume, deterministic replay, and trace-based
grading (Anthropic's "Demystifying Evals" principle).
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field
import uuid


EventKind = Literal[
    # Lifecycle
    "pipeline.started",
    "pipeline.paused",
    "pipeline.resumed",
    "pipeline.completed",
    "pipeline.failed",
    # Per-agent
    "agent.started",
    "agent.output",
    "agent.retry",
    "agent.failed",
    "agent.completed",
    # Tool / subprocess
    "tool.started",
    "tool.completed",
    "tool.failed",
    # Validation
    "guardrail.violated",
    "grader.passed",
    "grader.failed",
    # Human-in-the-loop
    "human.requested",
    "human.responded",
    # Metrics
    "metric.emitted",
]


class AgentEvent(BaseModel):
    """A single immutable event in the pipeline trace."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: EventKind
    agent: str | None = None       # researcher | planner | coder | ...
    scene: int | None = None       # 1-indexed, when applicable
    attempt: int = 1               # for retries
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_id: str | None = None   # causal chain (which event triggered this)


class EventLog(BaseModel):
    """Append-only log. The current state is derived from this list."""
    project_id: str
    events: list[AgentEvent] = Field(default_factory=list)

    def append(self, event: AgentEvent) -> None:
        self.events.append(event)

    def last(self, kind: EventKind | None = None, agent: str | None = None) -> AgentEvent | None:
        for e in reversed(self.events):
            if kind and e.kind != kind:
                continue
            if agent and e.agent != agent:
                continue
            return e
        return None

    def count(self, kind: EventKind, agent: str | None = None) -> int:
        return sum(1 for e in self.events if e.kind == kind and (agent is None or e.agent == agent))

    def attempts_for(self, agent: str, scene: int | None = None) -> int:
        """How many times has this agent (optionally for a scene) tried?"""
        return sum(
            1 for e in self.events
            if e.kind in ("agent.started", "agent.retry") and e.agent == agent and e.scene == scene
        )

    def is_paused(self) -> bool:
        return self.last("pipeline.paused") is not None and (
            self.last("pipeline.resumed") is None
            or self.last("pipeline.paused").timestamp > self.last("pipeline.resumed").timestamp
        )

    def is_terminal(self) -> bool:
        last = self.events[-1] if self.events else None
        return last is not None and last.kind in ("pipeline.completed", "pipeline.failed")

    # --- Derived state ---
    def derive_status(self) -> str:
        """Replace the ad-hoc status field on the manifest with a derived value."""
        if not self.events:
            return "draft"
        if self.is_terminal():
            return self.events[-1].kind.split(".")[1]   # "completed" | "failed"
        if self.is_paused():
            pause = self.last("pipeline.paused")
            return f"paused.{pause.payload.get('reason', 'unknown')}"
        last_agent = self.last("agent.started")
        return f"running.{last_agent.agent}" if last_agent else "running"
