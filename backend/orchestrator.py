"""Pipeline state machine for one video project.

Each pipeline run is isolated — no shared state between videos.
Agents call the `claude -p` CLI, which uses the Claude Pro subscription.
Events are emitted synchronously from a worker thread via the Emit callback.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from events import PipelineEvent
from project_store import project_path, update_manifest, load_manifest

SKILL_ROOT = Path(__file__).parent.parent / ".agents" / "skills" / "manim"
CHECK_ENV = SKILL_ROOT / "scripts" / "check_env.py"
MAX_QA_CYCLES = 3


Emit = Callable[[PipelineEvent], None]


def run_pipeline(project_id: str, emit: Emit) -> None:
    """Run env check + researcher, then pause awaiting plugin approval."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)

    def ev(kind, **payload):
        emit(PipelineEvent(kind=kind, project_id=project_id, payload=payload))

    try:
        update_manifest(project_id, {"status": "running"})
        ev("pipeline_started")

        # --- 1. ENV CHECK ---
        result = subprocess.run([sys.executable, str(CHECK_ENV)], capture_output=True, text=True)
        if result.returncode != 0:
            ev("env_check_failed", message=result.stdout + result.stderr)
            update_manifest(project_id, {"status": "env_failed"})
            return
        ev("env_check_ok", output=result.stdout)

        # --- 2. RESEARCHER ---
        ev("agent_started", agent="researcher")
        from agents import researcher
        plugins = researcher.run(manifest["idea"], proj)
        ev("plugins_proposed", plugins=plugins)
        update_manifest(project_id, {"status": "awaiting_plugins", "plugins_proposal": plugins})
        # Pipeline pauses — client calls POST /projects/{id}/plugins/confirm to resume

    except Exception as e:
        ev("error", message=str(e))
        update_manifest(project_id, {"status": "error", "error": str(e)})


def run_pipeline_after_plugins(project_id: str, approved_plugins: list[str], emit: Emit) -> None:
    """Continue pipeline after user approves plugins."""
    proj = project_path(project_id)
    manifest = load_manifest(project_id)

    def ev(kind, **payload):
        emit(PipelineEvent(kind=kind, project_id=project_id, payload=payload))

    try:
        # --- 3. INSTALL PLUGINS ---
        if approved_plugins:
            from tools.plugin_installer import install_plugin
            results = {}
            for pkg in approved_plugins:
                res = install_plugin(pkg)
                results[pkg] = res
                ev("log", message=f"Plugin {pkg}: {res['status']}")
            update_manifest(project_id, {"plugins": results})
        ev("plugins_installed")

        # --- 4. PLANNER ---
        ev("agent_started", agent="planner")
        from agents import planner
        outline = planner.run(
            manifest["idea"],
            proj,
            lang=manifest.get("lang", "es"),
            audience=manifest.get("audience", "general"),
            target_length=manifest.get("target_length", "60s"),
        )
        ev("outline_ready", outline=outline)
        update_manifest(project_id, {"status": "planning_done"})

        # --- 5. SCENES LOOP ---
        scene_entries = _parse_scenes(outline)
        scene_files: list[Path] = []
        scene_durations: list[float] = []

        for i, scene_desc in enumerate(scene_entries, start=1):
            ev("scene_started", scene=i, description=scene_desc[:200])

            # --- CODER ---
            ev("agent_started", agent="coder", scene=i)
            from agents import coder
            scene_file, code_status = coder.run(i, scene_desc, outline, proj)
            scene_files.append(scene_file)

            if code_status == "failed":
                ev("render_failed", scene=i, message="Max fix cycles reached")
                scene_durations.append(5.0)
                continue
            ev("render_ok", scene=i)

            # --- RENDER PREVIEW ---
            preview_mp4, duration = _render_preview(scene_file, i, proj)
            scene_durations.append(duration)

            # --- EXTRACT FRAMES ---
            frames = _extract_frames(preview_mp4, i, proj)
            ev("frames_extracted", scene=i, count=len(frames))

            # --- VISUAL QA LOOP ---
            qa_cycles = 0
            while qa_cycles < MAX_QA_CYCLES:
                ev("agent_started", agent="visual_qa", scene=i, cycle=qa_cycles + 1)
                from agents import visual_qa
                qa_result = visual_qa.run(i, scene_desc, scene_file, frames, proj)
                if qa_result["status"] == "ok":
                    ev("qa_ok", scene=i)
                    break
                qa_cycles += 1
                ev("qa_issue", scene=i, cycle=qa_cycles, notes=qa_result["raw"][:500])

                if qa_cycles >= MAX_QA_CYCLES:
                    ev("qa_degraded", scene=i)
                    break

                # Coder applies QA fix
                ev("agent_started", agent="coder", scene=i, phase="qa_fix")
                _apply_qa_fix(scene_file, qa_result["raw"])
                preview_mp4, duration = _render_preview(scene_file, i, proj)
                scene_durations[i - 1] = duration
                frames = _extract_frames(preview_mp4, i, proj)

        # --- 6. NARRATOR ---
        ev("agent_started", agent="narrator")
        from agents import narrator
        audio_files = narrator.run(
            outline,
            scene_durations,
            proj,
            lang=manifest.get("lang", "es"),
            voice_profile=manifest.get("voice_profile"),
            tts_backend=manifest.get("tts_backend", "stub"),
        )
        ev("narration_ready")

        # --- 7. EDITOR ---
        ev("agent_started", agent="editor")
        from agents import editor
        final_video = editor.run(scene_files, audio_files, proj, lang=manifest.get("lang", "es"))
        ev("edit_done", video=str(final_video))
        update_manifest(project_id, {"status": "awaiting_review", "final_video": str(final_video)})

    except Exception as e:
        ev("error", message=str(e))
        update_manifest(project_id, {"status": "error", "error": str(e)})


def run_curator(project_id: str, emit: Emit) -> None:
    proj = project_path(project_id)

    def ev(kind, **payload):
        emit(PipelineEvent(kind=kind, project_id=project_id, payload=payload))

    try:
        ev("agent_started", agent="curator")
        from agents import curator
        result = curator.run(proj)
        ev("curator_done", learnings=result.get("learnings", "")[:300], patches=list(result.get("patches", {}).keys()))
        update_manifest(project_id, {"status": "curated"})
    except Exception as e:
        ev("error", message=str(e))


# --- Helpers ---

def _parse_scenes(outline: str) -> list[str]:
    """Split outline into per-scene descriptions."""
    parts = re.split(r"(?m)^#{1,3}\s*[Ss]cena?\s*\d+", outline)
    scenes = [p.strip() for p in parts if p.strip()]
    return scenes if scenes else [outline]


def _render_preview(scene_file: Path, scene_num: int, proj: Path) -> tuple[Path, float]:
    import re as _re
    scene_name = _get_scene_name(scene_file)
    render_dir = proj / "renders" / f"scene_{scene_num:02d}"
    render_dir.mkdir(parents=True, exist_ok=True)
    out = render_dir / "preview.mp4"
    subprocess.run(
        ["manim", "-ql", "--output_file", str(out), str(scene_file), scene_name],
        capture_output=True, text=True,
    )
    duration = _probe_duration(out)
    return out, duration


def _extract_frames(video: Path, scene_num: int, proj: Path) -> list[Path]:
    from tools.extract_frames import extract_frames
    frames_dir = proj / "renders" / f"scene_{scene_num:02d}" / "frames"
    try:
        return extract_frames(video, frames_dir, n=6)
    except Exception:
        return []


def _probe_duration(video: Path) -> float:
    if not video.exists():
        return 5.0
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 5.0


def _get_scene_name(scene_file: Path) -> str:
    import re
    text = scene_file.read_text(encoding="utf-8")
    m = re.search(r"class\s+(Scene\w*)\s*\(", text)
    return m.group(1) if m else "Scene"


def _apply_qa_fix(scene_file: Path, qa_notes: str) -> None:
    from agents.coder import _fix, _skill_context, _strip_fences
    skill_ctx = _skill_context()
    scene_name = _get_scene_name(scene_file)
    code = scene_file.read_text(encoding="utf-8")
    fixed = _fix(skill_ctx, code, f"QA feedback:\n{qa_notes}", scene_name)
    scene_file.write_text(fixed, encoding="utf-8")
