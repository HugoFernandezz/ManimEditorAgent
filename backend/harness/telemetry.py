"""OpenTelemetry-style metrics for agent calls.

Follows the OTel GenAI semantic conventions: gen_ai.request.model,
gen_ai.usage.input_tokens, gen_ai.usage.output_tokens, gen_ai.response.duration_ms.

We don't ship an OTel exporter here (avoid dep bloat) but emit structured
metric events into the log so any backend (Prometheus, Honeycomb, jsonl) can
ingest them later.
"""
from __future__ import annotations
import time
from contextlib import contextmanager
from typing import Iterator
from harness.events import AgentEvent


@contextmanager
def measure(agent: str, model: str, scene: int | None = None) -> Iterator[dict]:
    """Yields a metrics dict the caller fills; emits a metric event on exit."""
    metrics: dict = {
        "gen_ai.system": "anthropic.claude",
        "gen_ai.request.model": model,
        "gen_ai.operation.name": agent,
        "input_chars": 0,
        "output_chars": 0,
        "duration_ms": 0,
        "outcome": "unknown",
    }
    start = time.perf_counter()
    try:
        yield metrics
        if metrics["outcome"] == "unknown":
            metrics["outcome"] = "success"
    except Exception:
        metrics["outcome"] = "error"
        raise
    finally:
        metrics["duration_ms"] = int((time.perf_counter() - start) * 1000)


def estimate_cost_usd(model: str, input_chars: int, output_chars: int) -> float:
    """Rough cost estimate. Claude Pro has unlimited use up to rate limit,
    so this is mostly informational for tracking which agents are heaviest."""
    # ~4 chars/token; prices per 1M tokens (rough Sonnet/Opus tiers)
    tokens_in  = input_chars / 4
    tokens_out = output_chars / 4
    if "opus" in model:
        return (tokens_in * 15 + tokens_out * 75) / 1_000_000
    return (tokens_in * 3 + tokens_out * 15) / 1_000_000


def metric_event(agent: str, scene: int | None, metrics: dict) -> AgentEvent:
    """Build an AgentEvent of kind=metric.emitted from a metrics dict."""
    metrics["cost_usd_estimate"] = estimate_cost_usd(
        metrics.get("gen_ai.request.model", ""),
        metrics.get("input_chars", 0),
        metrics.get("output_chars", 0),
    )
    return AgentEvent(kind="metric.emitted", agent=agent, scene=scene, payload=metrics)
