"""Harness engineering layer.

Provides the infrastructure that wraps agents:
- Event-sourced state (events.py, store.py)
- Resilient agent invocation (runner.py)
- Structured validation (guardrails.py)
- Versioned prompts (prompts.py)
- Deterministic + LLM graders (graders.py, evals.py)
- Metrics & tracing (telemetry.py)

Design principle: agents stay simple; the harness handles retries, validation,
checkpointing, observability and evaluation.
"""
