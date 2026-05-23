"""Per-project human-readable debug logger.

Creates  projects/<project_id>/logs/pipeline_YYYYMMDD_HHMMSS.log
at the start of each pipeline run. Every agent call (with full prompts
and outputs), subprocess command + stdout/stderr, retries, validation
failures, and errors are written so debugging requires only one file.

Usage
-----
    from harness import debug_log

    debug_log.new_run(project_id)           # pipeline start (fresh log file)
    debug_log.ensure_run(project_id)        # continuation (reuse or create)

    debug_log.pipeline_start(project_id, manifest)
    debug_log.stage(project_id, "planner")
    debug_log.agent_call(project_id, ...)
    debug_log.agent_done(project_id, ...)
    debug_log.subprocess_result(project_id, ...)
    debug_log.error(project_id, msg, exc)
    debug_log.pipeline_end(project_id, status, elapsed)
"""
from __future__ import annotations
import logging
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Config ───────────────────────────────────────────────────────────────────

PROJECTS_ROOT = Path(__file__).parent.parent.parent / "projects"

_TRUNC_SYSTEM  =  2_000   # chars kept from system prompts
_TRUNC_PROMPT  =  6_000   # chars kept from user prompts
_TRUNC_OUTPUT  =  8_000   # chars kept from agent outputs
_TRUNC_PROC    = 10_000   # chars kept from subprocess stdout/stderr

_SEP  = "═" * 72
_DIV  = "─" * 72

_FMT = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d  %(levelname)-7s  [%(threadName)-22s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Internal registry ─────────────────────────────────────────────────────────

_LOCK: threading.Lock = threading.Lock()
_LOGGERS: dict[str, logging.Logger] = {}


def _close_existing(project_id: str) -> None:
    """Close and remove any open handlers for this project (call under _LOCK)."""
    logger = _LOGGERS.pop(project_id, None)
    if logger:
        for h in logger.handlers[:]:
            logger.removeHandler(h)
            try:
                h.flush()
                h.close()
            except Exception:
                pass


def _create(project_id: str) -> logging.Logger:
    """Create a new log file and return the configured logger (call under _LOCK)."""
    log_dir = PROJECTS_ROOT / project_id / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_path = log_dir / f"pipeline_{ts}.log"

    logger = logging.getLogger(f"debug.pipeline.{project_id}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_FMT)
    logger.addHandler(fh)
    _LOGGERS[project_id] = logger
    return logger


def _get(project_id: str) -> logging.Logger | None:
    return _LOGGERS.get(project_id)


# ── Text helpers ──────────────────────────────────────────────────────────────

def _trunc(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    omitted = len(text) - max_chars
    return f"{text[:half]}\n... [{omitted:,} chars omitted] ...\n{text[-half:]}"


def _block(log: logging.Logger, level: int, title: str, body: str) -> None:
    """Emit a titled multi-line block with box-drawing border."""
    pad = max(0, 64 - len(title))
    log.log(level, f"┌─ {title} {'─' * pad}")
    for line in body.splitlines():
        log.log(level, f"│  {line}")
    log.log(level, f"└{'─' * 70}")


# ── Public lifecycle API ──────────────────────────────────────────────────────

def new_run(project_id: str) -> None:
    """Call at the very start of a fresh pipeline — creates a new log file."""
    with _LOCK:
        _close_existing(project_id)
        _create(project_id)


def ensure_run(project_id: str) -> None:
    """Call in continuation flows (plugins confirm, finalize, revision).

    If a log file was already opened by run_pipeline(), we continue into it.
    If we're being called standalone (resume, revision without prior run),
    we create a new file.
    """
    with _LOCK:
        if project_id not in _LOGGERS:
            _create(project_id)


def pipeline_start(project_id: str, manifest: dict) -> None:
    log = _get(project_id)
    if not log:
        return
    log.info(_SEP)
    log.info(f"PIPELINE START  project={project_id}")
    log.info(_SEP)
    fields = ["idea", "lang", "format", "target_length", "voice_profile",
              "skip_research", "status"]
    summary = "  ".join(
        f'{k}={manifest[k]!r}' for k in fields if manifest.get(k) is not None
    )
    log.info(f"Manifest summary: {summary}")
    plugins_proposal = manifest.get("plugins_proposal") or []
    log.debug(f"Plugins proposal: {plugins_proposal}")
    log.debug(f"Full manifest: {dict(manifest)}")
    log.info("")


def pipeline_end(project_id: str, status: str, elapsed: float) -> None:
    log = _get(project_id)
    if not log:
        return
    log.info("")
    log.info(_SEP)
    log.info(f"PIPELINE END  project={project_id}  status={status}  total={elapsed:.1f}s")
    log.info(_SEP)
    with _LOCK:
        for h in _LOGGERS.get(project_id, logging.getLogger()).handlers[:]:
            try:
                h.flush()
            except Exception:
                pass


# ── Public log API ────────────────────────────────────────────────────────────

def stage(project_id: str, name: str, detail: str = "") -> None:
    log = _get(project_id)
    if not log:
        return
    pad = max(0, 58 - len(name))
    suffix = f"  {detail}" if detail else ""
    log.info(f"── STAGE: {name} {'─' * pad}{suffix}")


def ui_state(project_id: str, description: str, f5_note: str = "") -> None:
    """Log a visual snapshot of the UI at this moment.

    `description` describes which pipeline nodes are active/idle/done
    and what the user would see on screen.
    `f5_note` (optional) describes what the UI would reconstruct from the
    manifest if the user pressed F5 right now.
    """
    log = _get(project_id)
    if not log:
        return
    log.info(f"◈ UI  {description}")
    if f5_note:
        log.info(f"◈ F5  {f5_note}")


def info(project_id: str, message: str) -> None:
    log = _get(project_id)
    if log:
        log.info(message)


def warning(project_id: str, message: str) -> None:
    log = _get(project_id)
    if log:
        log.warning(message)


def error(project_id: str, message: str, exc: BaseException | None = None) -> None:
    log = _get(project_id)
    if not log:
        return
    log.error(message)
    if exc is not None:
        log.error(traceback.format_exc())


# ── Agent call logging ────────────────────────────────────────────────────────

def agent_call(
    project_id: str,
    agent: str,
    model: str,
    tools: str | None,
    scene: int | None,
    attempt: int,
    max_attempts: int,
    prompt: str,
    system: str,
) -> None:
    log = _get(project_id)
    if not log:
        return
    scene_tag = f"  scene={scene}" if scene is not None else ""
    log.info(
        f"AGENT CALL  {agent}  model={model}  tools={tools or 'None'}{scene_tag}"
        f"  input={len(prompt) + len(system):,} chars  attempt={attempt}/{max_attempts}"
    )
    _block(log, logging.DEBUG,
           f"SYSTEM ({len(system):,} chars)",
           _trunc(system, _TRUNC_SYSTEM))
    _block(log, logging.DEBUG,
           f"PROMPT ({len(prompt):,} chars)",
           _trunc(prompt, _TRUNC_PROMPT))


def agent_done(
    project_id: str,
    agent: str,
    scene: int | None,
    attempt: int,
    elapsed: float,
    output: str,
    validation: str = "passed",
) -> None:
    log = _get(project_id)
    if not log:
        return
    scene_tag = f"  scene={scene}" if scene is not None else ""
    log.info(
        f"AGENT DONE  {agent}{scene_tag}  {elapsed:.1f}s"
        f"  output={len(output):,} chars  attempt={attempt}  validation={validation}"
    )
    _block(log, logging.DEBUG,
           f"OUTPUT ({len(output):,} chars)",
           _trunc(output, _TRUNC_OUTPUT))
    log.info("")


def agent_retry(
    project_id: str,
    agent: str,
    scene: int | None,
    attempt: int,
    max_attempts: int,
    backoff: float,
    reason: str,
) -> None:
    log = _get(project_id)
    if not log:
        return
    scene_tag = f"  scene={scene}" if scene is not None else ""
    log.warning(
        f"AGENT RETRY  {agent}{scene_tag}  attempt={attempt}/{max_attempts}"
        f"  backoff={backoff:.0f}s  reason={reason[:300]}"
    )


def agent_failed(
    project_id: str,
    agent: str,
    scene: int | None,
    attempt: int,
    reason: str,
    exc: BaseException | None = None,
) -> None:
    log = _get(project_id)
    if not log:
        return
    scene_tag = f"  scene={scene}" if scene is not None else ""
    log.error(
        f"AGENT FAILED  {agent}{scene_tag}  after {attempt} attempt(s)"
        f"  reason={reason[:300]}"
    )
    if exc is not None:
        log.error(traceback.format_exc())
    log.info("")


def guardrail_violated(
    project_id: str,
    agent: str,
    scene: int | None,
    attempt: int,
    validator_error: str,
) -> None:
    log = _get(project_id)
    if not log:
        return
    scene_tag = f"  scene={scene}" if scene is not None else ""
    log.warning(
        f"GUARDRAIL VIOLATED  {agent}{scene_tag}"
        f"  attempt={attempt}  error={validator_error[:300]}"
    )


# ── Subprocess logging ────────────────────────────────────────────────────────

def subprocess_result(
    project_id: str,
    label: str,
    cmd: list[Any],
    result: Any,          # subprocess.CompletedProcess
    elapsed: float,
) -> None:
    log = _get(project_id)
    if not log:
        return
    ok = result.returncode == 0
    status = "OK" if ok else f"FAILED (rc={result.returncode})"
    log.info(f"SUBPROCESS  {label}  {elapsed:.1f}s  {status}")
    log.debug(f"CMD: {' '.join(str(a) for a in cmd)}")
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if stdout:
        _block(log, logging.DEBUG, "STDOUT", _trunc(stdout, _TRUNC_PROC))
    if stderr:
        lvl = logging.ERROR if not ok else logging.DEBUG
        _block(log, lvl, "STDERR", _trunc(stderr, _TRUNC_PROC))
    if not ok and not stderr and not stdout:
        log.error(f"Process exited rc={result.returncode} with no output")
    log.info("")
