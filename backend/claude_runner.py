"""Thin wrapper around `claude -p` CLI for non-interactive agent calls.

Uses the logged-in Claude Pro subscription — no ANTHROPIC_API_KEY required.

IMPORTANT — prompt position:
  The Claude Code CLI expects the prompt as the FIRST positional argument,
  immediately after `-p`:
      claude -p "prompt text" [--options...]
  Passing the prompt LAST (after --add-dir or other flags) causes:
      "Error: Input must be provided either through stdin or as a prompt argument."

For the streaming variant (Coder) we use --output-format stream-json so
callers can receive tool calls and partial text in real-time via on_event.
"""
from __future__ import annotations
import json
import subprocess
import threading
from pathlib import Path
from typing import Callable

_DEFAULT_TIMEOUT = 300

# Windows has a hard ~32 KB limit on the total command-line length
# (CreateProcess). When the prompt is large (Coder inlines ~28 KB of skill
# content) putting it as a positional argument hits WinError 206 instantly.
# Above this threshold we pass the prompt via stdin instead — the CLI accepts
# both modes (error message says "either through stdin or as a prompt argument").
_STDIN_THRESHOLD = 6000


# ── Active subprocess tracking (per-project) ─────────────────────────────────
# Lets the /stop endpoint terminate in-flight `claude` calls. Without this,
# stopping during a long agent call would have to wait for the timeout.
_active_procs_lock = threading.Lock()
_active_procs: dict[str, list[subprocess.Popen]] = {}


def _track(project_id: str | None, proc: subprocess.Popen) -> None:
    if not project_id:
        return
    with _active_procs_lock:
        _active_procs.setdefault(project_id, []).append(proc)


def _untrack(project_id: str | None, proc: subprocess.Popen) -> None:
    if not project_id:
        return
    with _active_procs_lock:
        bucket = _active_procs.get(project_id)
        if bucket is None:
            return
        try:
            bucket.remove(proc)
        except ValueError:
            pass
        if not bucket:
            _active_procs.pop(project_id, None)


def kill_for_project(project_id: str) -> int:
    """Kill all tracked `claude` subprocesses for this project. Returns count killed."""
    if not project_id:
        return 0
    with _active_procs_lock:
        procs = list(_active_procs.pop(project_id, []))
    killed = 0
    for p in procs:
        if p.poll() is None:
            try:
                p.kill()
                killed += 1
            except Exception:
                pass
    return killed


def _build_base_cmd(prompt: str, use_stdin: bool) -> list[str]:
    """Start of the `claude` command — handles prompt-as-arg vs stdin."""
    if use_stdin:
        # `--print` (a.k.a. `-p` with no value) tells the CLI to run
        # non-interactively and read the prompt from stdin.
        return ["claude", "--print"]
    return ["claude", "-p", prompt]


def run_text(
    prompt: str,
    system: str = "",
    model: str = "sonnet",
    timeout: int = _DEFAULT_TIMEOUT,
    project_id: str | None = None,
) -> str:
    """Call claude -p with no tools (pure text generation)."""
    use_stdin = len(prompt) > _STDIN_THRESHOLD
    cmd = _build_base_cmd(prompt, use_stdin) + [
        "--output-format", "json",
        "--no-session-persistence",
        "--model", model,
        "--tools", "",
    ]
    if system:
        cmd += ["--system-prompt", system]
    return _exec_json(cmd, timeout, project_id=project_id,
                      stdin_data=prompt if use_stdin else None)


def run_with_tools(
    prompt: str,
    system: str = "",
    model: str = "sonnet",
    tools: str = "default",
    add_dirs: list[Path] | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
    on_event: Callable[[dict], None] | None = None,
    project_id: str | None = None,
) -> str:
    """Call claude -p with tools.

    For large prompts we pass via stdin to avoid Windows' ~32KB command-line
    limit. Otherwise prompt goes as the first positional arg, since `--add-dir`
    flags after that confuse the CLI arg parser.

    Without on_event: --output-format json (single response).
    With on_event:    --output-format stream-json (live tool-call events).
    """
    use_stdin = len(prompt) > _STDIN_THRESHOLD
    fmt = "stream-json" if on_event is not None else "json"
    cmd = _build_base_cmd(prompt, use_stdin) + [
        "--output-format", fmt,
        "--no-session-persistence",
        "--model", model,
        "--tools", tools,
    ]
    # The CLI rejects `--print --output-format=stream-json` without --verbose
    if fmt == "stream-json":
        cmd.append("--verbose")
    if system:
        cmd += ["--system-prompt", system]
    for d in (add_dirs or []):
        cmd += ["--add-dir", str(d)]

    stdin_data = prompt if use_stdin else None
    if on_event is not None:
        return _exec_streaming(cmd, timeout, on_event,
                                project_id=project_id, stdin_data=stdin_data)
    return _exec_json(cmd, timeout, project_id=project_id, stdin_data=stdin_data)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _exec_json(cmd: list[str], timeout: int, project_id: str | None = None,
               stdin_data: str | None = None) -> str:
    """Run cmd via Popen+communicate so the process can be killed externally.

    encoding="utf-8" is critical on Windows: without it, subprocess decodes
    claude CLI's UTF-8 output as cp1252 → mojibake (é→Ã©, ¿→Â¿, etc.)
    If stdin_data is provided, it's piped to the CLI (used for large prompts
    that exceed the Windows ~32KB command-line limit).
    """
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_data is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    _track(project_id, proc)
    try:
        stdout, stderr = proc.communicate(input=stdin_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise RuntimeError(f"claude CLI timed out after {timeout}s")
    finally:
        _untrack(project_id, proc)

    if proc.returncode != 0:
        raise RuntimeError(
            (stderr or "").strip()
            or (stdout or "").strip()
            or f"claude CLI exited with code {proc.returncode} (no output)"
        )
    if not stdout or not stdout.strip():
        raise RuntimeError(
            "claude CLI returned empty output (rc=0). "
            f"stderr: {(stderr or '').strip()[:300] or '<empty>'}"
        )
    data = json.loads(stdout)
    if data.get("is_error"):
        raise RuntimeError(data.get("result", "Unknown error"))
    return data.get("result", "")


def _exec_streaming(
    cmd: list[str], timeout: int,
    on_event: Callable[[dict], None],
    project_id: str | None = None,
    stdin_data: str | None = None,
) -> str:
    """Run cmd with stream-json output; calls on_event for each NDJSON line."""
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_data is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )
    _track(project_id, proc)
    # If we have stdin data, send it now then close stdin so the CLI knows
    # the prompt is complete. We don't iterate stdin during streaming.
    if stdin_data is not None and proc.stdin is not None:
        try:
            proc.stdin.write(stdin_data)
            proc.stdin.close()
        except Exception:
            pass
    result_text = ""
    is_error = False
    try:
        for raw in proc.stdout:   # type: ignore[union-attr]
            raw = raw.rstrip("\n")
            if not raw:
                continue
            try:
                event = json.loads(raw)
                on_event(event)
                if event.get("type") == "result":
                    result_text = event.get("result", "")
                    is_error = bool(event.get("is_error", False))
            except json.JSONDecodeError:
                pass
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("Agent timed out")
    except Exception:
        proc.kill()
        raise
    finally:
        _untrack(project_id, proc)

    if proc.returncode != 0 or is_error:
        stderr = proc.stderr.read()  # type: ignore[union-attr]
        # returncode is often -9/-15 when we killed the proc from /stop.
        # Surface a recognizable message so the orchestrator can label it as such.
        if proc.returncode in (-9, -15) or (proc.returncode is not None and proc.returncode < 0):
            raise RuntimeError(f"claude CLI killed (rc={proc.returncode})")
        raise RuntimeError(stderr.strip() or result_text)
    return result_text


# ── Stream-event parser (used by harness/runner.py) ───────────────────────────

def parse_stream_event(event: dict) -> dict | None:
    """Convert a raw stream-json event → compact log entry for the UI.

    Returns None for events we don't surface (tool results, system init).
    """
    t = event.get("type", "")

    if t == "tool_use":
        name = event.get("tool_name") or event.get("name", "?")
        return {"line_type": "tool_use", "tool_name": name,
                "summary": _tool_summary(name, event.get("input", {}))}

    if t == "assistant":
        for block in event.get("message", {}).get("content", []):
            bt = block.get("type", "")
            if bt == "text":
                text = (block.get("text") or "").strip()[:200]
                if text:
                    return {"line_type": "text", "summary": text}
            elif bt == "tool_use":
                name = block.get("name", "?")
                return {"line_type": "tool_use", "tool_name": name,
                        "summary": _tool_summary(name, block.get("input", {}))}

    if t == "result":
        ok = not event.get("is_error", False)
        turns = event.get("num_turns", "?")
        cost = event.get("total_cost_usd")
        s = f"{'Completado' if ok else 'Error'} · {turns} turnos"
        if cost:
            s += f" · ${cost:.4f}"
        return {"line_type": "result" if ok else "error", "summary": s}

    return None


def _tool_summary(name: str, inp: dict) -> str:
    if name == "Read":
        p = inp.get("file_path", "")
        return (p.split("/")[-1] or p)[:80]
    if name == "Glob":
        return f"[{inp.get('pattern', '?')}]"[:80]
    if name == "Grep":
        return f"/{inp.get('pattern', '?')}/"[:80]
    if name == "Write":
        p = inp.get("file_path", "")
        return (p.split("/")[-1] or p)[:80]
    return str(inp)[:80]
