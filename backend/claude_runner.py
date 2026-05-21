"""Thin wrapper around `claude -p` CLI for non-interactive agent calls.

Uses the logged-in Claude Pro subscription — no ANTHROPIC_API_KEY required.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

_DEFAULT_TIMEOUT = 300  # seconds per agent call


def run_text(
    prompt: str,
    system: str = "",
    model: str = "sonnet",
    timeout: int = _DEFAULT_TIMEOUT,
) -> str:
    """Call claude -p with no tools (pure text generation)."""
    cmd = _base_cmd(model) + ["--tools", ""]
    if system:
        cmd += ["--system-prompt", system]
    cmd += [prompt]
    return _exec(cmd, timeout)


def run_with_tools(
    prompt: str,
    system: str = "",
    model: str = "sonnet",
    tools: str = "default",
    add_dirs: list[Path] | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> str:
    """Call claude -p with specified tools enabled."""
    cmd = _base_cmd(model) + ["--tools", tools]
    if system:
        cmd += ["--system-prompt", system]
    for d in (add_dirs or []):
        cmd += ["--add-dir", str(d)]
    cmd += [prompt]
    return _exec(cmd, timeout)


def _base_cmd(model: str) -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--no-session-persistence",
        "--model", model,
    ]


def _exec(cmd: list[str], timeout: int) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    data = json.loads(result.stdout)
    if data.get("is_error"):
        raise RuntimeError(data.get("result", "Unknown error from claude CLI"))
    return data.get("result", "")
