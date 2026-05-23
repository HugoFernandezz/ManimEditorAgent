"use client";
import { useEffect, useReducer, useState } from "react";
import { fetchProject, createWebSocket, type PipelineEvent, type Project } from "@/lib/api";
import { INITIAL_PIPELINE, type PipelineState, type AgentState } from "@/components/pipeline-view";
import { applyEvent, applyStreamLine, type AgentLogs } from "@/lib/pipeline-reducer";

const MAX_LOGS = 300;

export interface PipelineSnapshot {
  project: Project | null;
  pipeline: PipelineState;
  logs: string[];
  outline: string;
  qaNotes: Record<number, string>;
  agentLogs: AgentLogs;
}

type Action =
  | { type: "event"; event: PipelineEvent }
  | { type: "baseline"; pipeline: PipelineState }
  | { type: "force-baseline"; pipeline: PipelineState }
  | { type: "reset" };

const EMPTY_SNAP: PipelineSnapshot = {
  project: null, pipeline: INITIAL_PIPELINE,
  logs: [], outline: "", qaNotes: {}, agentLogs: {},
};

function reducer(state: PipelineSnapshot, action: Action): PipelineSnapshot {
  if (action.type === "reset") {
    return { ...EMPTY_SNAP, project: state.project };
  }
  if (action.type === "baseline") {
    // First-time baseline: only apply if nothing in the pipeline has moved yet,
    // so we don't clobber a WS event that arrived before the fetch.
    const allPending = Object.values(state.pipeline).every((s) => s.status === "pending");
    if (!allPending) return state;
    return { ...state, pipeline: action.pipeline };
  }
  if (action.type === "force-baseline") {
    // Hard re-sync — used when the backend signals a phase transition and
    // we want the manifest snapshot to win over any stale local state.
    return { ...state, pipeline: action.pipeline };
  }
  const e = action.event;

  // Stream lines go only into agentLogs — keep the text log clean
  if (e.kind === "agent_stream_line") {
    return { ...state, agentLogs: applyStreamLine(state.agentLogs, e) };
  }

  const next: PipelineSnapshot = {
    ...state,
    pipeline: applyEvent(state.pipeline, e),
    logs: [
      ...state.logs.slice(-(MAX_LOGS - 1)),
      `[${e.kind}] ${JSON.stringify(e.payload).slice(0, 100)}`,
    ],
  };
  if (e.kind === "outline_ready" && typeof e.payload.outline === "string") {
    next.outline = e.payload.outline;
  }
  if (e.kind === "qa_issue" || e.kind === "qa_ok" || e.kind === "qa_degraded") {
    const scene = e.payload.scene;
    if (typeof scene === "number") {
      const value =
        e.kind === "qa_ok" ? "ok" :
        e.kind === "qa_degraded" ? "degraded" :
        typeof e.payload.notes === "string" ? e.payload.notes : "issue";
      next.qaNotes = { ...state.qaNotes, [scene]: value };
    }
  }
  return next;
}

function statusToPipelineState(project: Project): PipelineState {
  const ok: AgentState   = { status: "ok" };
  const err: AgentState  = { status: "error" };
  const wait: AgentState = { status: "waiting", detail: "Esperando aprobación" };
  const run: AgentState  = { status: "running" };
  const base = { ...INITIAL_PIPELINE };
  const s = project.status;

  if (s === "draft") return base;
  // "stopped" = user-aborted run. We don't know how far we got from the
  // status field alone — leave everything as "pending" so the UI doesn't
  // lie. The "Advanced options" panel in the form reveals on-disk artifacts
  // (outline.md, beats files, scenes) for cheap-resume.
  if (s === "stopped") return base;
  base.env = ok;
  if (s === "env_failed" || s === "error") return base;
  base.researcher = ok;
  if (s === "awaiting_plugins") { base.plugins = wait; return base; }
  base.plugins = ok;
  if (s === "planning_done") { base.planner = ok; base.beat_writer = run; return base; }
  if (s === "running") return base; // can't tell which phase — let WS fill in
  base.planner = ok; base.beat_writer = ok;

  // Derive Coder/Visual_QA from per-scene state instead of assuming success.
  // If ANY scene failed, the Coder phase didn't really succeed.
  const sceneEntries = project.scenes ? Object.values(project.scenes) : [];
  const anyFailed = sceneEntries.some((sc) => sc.status === "failed");
  const allRendered = sceneEntries.length > 0 && sceneEntries.every(
    (sc) => sc.status === "awaiting_review" || sc.status === "approved" || sc.status === "failed",
  );
  if (anyFailed) {
    base.coder = err;
    base.visual_qa = allRendered ? { status: "degraded", detail: "Alguna escena falló" } : err;
  } else {
    base.coder = ok; base.visual_qa = ok;
  }

  if (s === "awaiting_scene_review") {
    base.scene_review = anyFailed
      ? { status: "waiting", detail: "Con escenas fallidas" }
      : wait;
    return base;
  }
  base.scene_review = ok;
  if (s === "awaiting_review") { base.editor = ok; return base; }
  base.editor = ok;
  if (s === "curated") base.curator = ok;
  return base;
}

export function usePipeline(slug: string) {
  const [snap, dispatch] = useReducer(reducer, EMPTY_SNAP);
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchProject(slug).then((p) => {
      if (cancelled) return;
      setProject(p);
      dispatch({ type: "baseline", pipeline: statusToPipelineState(p) });
    });
    // After any of these "phase complete" events, refetch the manifest and
    // re-derive the baseline. This recovers from cases where the WS missed
    // intermediate events (e.g. user navigated away and came back, or a
    // resume started mid-pipeline) and the local state diverged from disk.
    const REFETCH_ON = new Set([
      "edit_done", "scenes_all_approved", "scenes_all_rendered",
      "plugins_installed", "curator_done",
    ]);
    const forceRefetch = () => {
      fetchProject(slug).then((p) => {
        if (!cancelled) {
          setProject(p);
          dispatch({ type: "force-baseline", pipeline: statusToPipelineState(p) });
        }
      });
    };
    const ws = createWebSocket(slug, (e) => {
      dispatch({ type: "event", event: e });
      if (REFETCH_ON.has(e.kind)) forceRefetch();
    });
    return () => { cancelled = true; ws.close(); };
  }, [slug]);

  return {
    project,
    setProject,
    pipeline: snap.pipeline,
    logs: snap.logs,
    outline: snap.outline,
    qaNotes: snap.qaNotes,
    agentLogs: snap.agentLogs,
  };
}
