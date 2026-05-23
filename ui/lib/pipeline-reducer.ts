import type { PipelineEvent } from "@/lib/api";
import type { PipelineState, AgentStatus } from "@/components/pipeline-view";

export interface StreamLine {
  line_type: "tool_use" | "text" | "result" | "error";
  tool_name?: string;
  summary: string;
  ts: number;
}

// agent key → lines (capped at 300 per agent)
export type AgentLogs = Record<string, StreamLine[]>;

type AgentId = keyof PipelineState;

const AGENT_IDS: readonly AgentId[] = [
  "env", "researcher", "plugins", "planner", "beat_writer",
  "coder", "visual_qa", "scene_review", "editor", "curator",
];

const isAgentId = (s: unknown): s is AgentId =>
  typeof s === "string" && (AGENT_IDS as readonly string[]).includes(s);

export function applyStreamLine(
  logs: AgentLogs,
  e: PipelineEvent,
): AgentLogs {
  if (e.kind !== "agent_stream_line") return logs;
  const agent = typeof e.payload.agent === "string" ? e.payload.agent : "?";
  const scene  = typeof e.payload.scene  === "number" ? e.payload.scene : undefined;
  const key = scene != null ? `${agent}:${scene}` : agent;
  const line: StreamLine = {
    line_type: (e.payload.line_type as StreamLine["line_type"]) ?? "text",
    tool_name: typeof e.payload.tool_name === "string" ? e.payload.tool_name : undefined,
    summary: typeof e.payload.summary === "string" ? e.payload.summary : "",
    ts: Date.now(),
  };
  const prev = logs[key] ?? [];
  return { ...logs, [key]: [...prev.slice(-299), line] };
}

/**
 * Reduce a single backend pipeline event into the next UI pipeline state.
 * Pure function — easy to unit-test, no closure over component state.
 */
export function applyEvent(state: PipelineState, e: PipelineEvent): PipelineState {
  const { kind, payload } = e;
  const set = (id: AgentId, status: AgentStatus, detail?: string): PipelineState => ({
    ...state, [id]: { status, detail },
  });

  switch (kind) {
    case "env_check_ok":
      return set("env", "ok");
    case "env_check_failed":
      return set("env", "error", typeof payload.message === "string" ? payload.message : undefined);

    case "agent_started": {
      const a = payload.agent;
      return isAgentId(a) ? set(a, "running") : state;
    }

    case "plugins_proposed":
      return {
        ...state,
        researcher: { status: "ok" },
        plugins: { status: "waiting", detail: "Esperando aprobación" },
      };
    case "plugins_installed": return set("plugins", "ok");
    case "outline_ready":     return set("planner", "ok");
    case "beats_ready":       return set("beat_writer", "ok");
    case "render_ok":         return set("coder", "ok");
    case "render_failed":     return set("coder", "degraded");
    case "qa_ok":             return set("visual_qa", "ok");
    case "qa_issue": {
      const c = payload.cycle;
      return set("visual_qa", "running", typeof c === "number" ? `Cycle ${c}` : undefined);
    }
    case "qa_degraded":   return set("visual_qa", "degraded");

    case "scene_preview_ready": {
      const n = payload.scene;
      const status = payload.status;
      // Failed scenes show on the Coder node (where the error actually is),
      // not on Scene Review (which only matters for human-approvable previews).
      if (status === "failed") {
        const detail = typeof n === "number" ? `Escena ${n} falló` : undefined;
        return set("coder", "error", detail);
      }
      const detail = typeof n === "number" ? `Escena ${n} lista` : undefined;
      return set("scene_review", "waiting", detail);
    }
    case "scene_approved": {
      const n = payload.scene;
      return set("scene_review", "running", typeof n === "number" ? `Escena ${n} aprobada` : undefined);
    }
    case "scene_revising": {
      const n = payload.scene;
      return set("scene_review", "running", typeof n === "number" ? `Revisando escena ${n}…` : undefined);
    }
    case "scenes_all_approved":
      return set("scene_review", "ok");

    case "finalizing":    return set("editor", "running");
    case "edit_done":     return set("editor", "ok");
    case "curator_done":  return set("curator", "ok");

    case "error": {
      // Mark every still-running agent as errored.
      const next = { ...state };
      for (const id of AGENT_IDS) {
        if (next[id].status === "running") next[id] = { status: "error" };
      }
      return next;
    }

    default:
      return state;
  }
}
