"""Offline eval suite + regression tracking.

Usage:
    python -m harness.evals run            # run the suite
    python -m harness.evals report <run>   # show pass rates

Each eval is a small contained task. Results land in `evals/runs/<timestamp>/`.
We compute pass@1 and pass@3 per task (Anthropic non-determinism handling).
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from harness.graders import grade_outline_structure

EVAL_ROOT = Path(__file__).parent.parent.parent / "evals"


@dataclass
class EvalTask:
    id: str
    idea: str
    lang: str = "es"
    audience: str = "general"
    target_length: str = "30s"
    min_outline_score: float = 0.7
    expected_min_scenes: int = 3
    notes: str = ""


@dataclass
class EvalResult:
    task_id: str
    attempt: int
    started_at: str
    duration_ms: int
    grades: list[dict] = field(default_factory=list)
    pass_overall: bool = False


# Seed regression suite — keep diverse and small to start (Anthropic guidance)
SUITE: list[EvalTask] = [
    EvalTask(
        id="derivative_intuition",
        idea="Explica intuitivamente qué es la derivada en un punto, mostrando la pendiente de la recta tangente",
        lang="es", audience="high school", target_length="30s",
        notes="Easy task — should be near-100% pass for healthy system",
    ),
    EvalTask(
        id="fourier_intro",
        idea="Visualiza cómo una serie de Fourier suma ondas senoidales para aproximar una onda cuadrada",
        lang="es", audience="undergrad", target_length="60s",
        notes="Medium — requires accurate math + animated parametric plots",
    ),
    EvalTask(
        id="pythagoras_visual",
        idea="Demuestra visualmente el teorema de Pitágoras con cuadrados sobre los lados",
        lang="es", audience="general", target_length="30s",
        notes="Easy — should pass consistently",
    ),
    EvalTask(
        id="eigenvector_3d",
        idea="Muestra qué es un eigenvector de una transformación lineal en 3D, con un cubo rotando y un eje invariante",
        lang="es", audience="advanced", target_length="60s",
        notes="Hard — 3D scene + abstract concept",
    ),
]


def run_suite(repeats: int = 1, only: str | None = None) -> Path:
    """Run the eval suite. Returns the run directory."""
    # NB: this evals the **graders + outline gen**, not the full pipeline
    # (full pipeline would render videos — too slow for CI). For full pipeline
    # evals, call run_full_pipeline_eval() with a small sample.
    from harness.prompts import PLANNER
    from harness.runner import call_agent, AgentCallFailed

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = EVAL_ROOT / "runs" / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    skill_root = Path(__file__).parent.parent.parent / ".agents" / "skills" / "manim"
    skill_md = (skill_root / "SKILL.md").read_text(encoding="utf-8")

    tasks = [t for t in SUITE if only is None or t.id == only]
    all_results: list[EvalResult] = []

    for task in tasks:
        for attempt in range(1, repeats + 1):
            print(f"▸ {task.id} attempt {attempt}/{repeats}", flush=True)
            r = EvalResult(
                task_id=task.id, attempt=attempt,
                started_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=0,
            )
            t0 = time.perf_counter()
            try:
                outline = call_agent(
                    project_id=f"_eval_{task.id}_{attempt}",
                    agent="planner",
                    prompt=PLANNER.render(
                        plugin_context="", skill_md=skill_md, style_section="",
                        idea=task.idea, lang=task.lang,
                        audience=task.audience, target_length=task.target_length,
                    ),
                    system=PLANNER.system, model="sonnet",
                    tools=None,
                    timeout=120, max_attempts=2,
                )
                g = grade_outline_structure(outline)
                r.grades.append(asdict(g))
                r.pass_overall = g.passed and g.score >= task.min_outline_score
            except AgentCallFailed as e:
                r.grades.append({"grader": "planner_call", "passed": False, "score": 0.0,
                                 "details": str(e)})
                r.pass_overall = False
            r.duration_ms = int((time.perf_counter() - t0) * 1000)
            all_results.append(r)
            print(f"  → pass={r.pass_overall} duration={r.duration_ms}ms", flush=True)

    (run_dir / "results.json").write_text(
        json.dumps([asdict(r) for r in all_results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = _summarize(all_results, repeats)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(f"\n✔ Done. Results in {run_dir}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return run_dir


def _summarize(results: list[EvalResult], repeats: int) -> dict:
    by_task: dict[str, list[EvalResult]] = {}
    for r in results:
        by_task.setdefault(r.task_id, []).append(r)
    out: dict = {"per_task": {}, "overall_pass_rate": 0.0, "repeats": repeats}
    overall_pass = 0
    for tid, rs in by_task.items():
        passes = sum(1 for r in rs if r.pass_overall)
        pass_at_1 = passes / len(rs)
        # pass^k = all attempts passed (consistency metric)
        pass_caret_k = 1.0 if passes == len(rs) else 0.0
        out["per_task"][tid] = {
            "attempts": len(rs),
            "passed": passes,
            "pass@1": round(pass_at_1, 2),
            f"pass^{repeats}": round(pass_caret_k, 2),
            "avg_duration_ms": int(sum(r.duration_ms for r in rs) / len(rs)),
        }
        overall_pass += pass_at_1
    out["overall_pass_rate"] = round(overall_pass / max(len(by_task), 1), 2)
    return out


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(prog="harness.evals")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="Run the offline eval suite")
    run_p.add_argument("--repeats", type=int, default=1,
                       help="Attempts per task (computes pass@1 and pass^k)")
    run_p.add_argument("--only", type=str, default=None,
                       help="Run only the task with this id")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        run_suite(repeats=args.repeats, only=args.only)


if __name__ == "__main__":
    main()
