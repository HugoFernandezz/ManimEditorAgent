"use client";
import { useState } from "react";
import { SkillEditor } from "@/components/skill-editor";
import {
  Search, BookOpen, ListOrdered, Code2, Eye, Film, Brain,
  Puzzle, CheckCircle, XCircle, AlertTriangle, Loader2, Circle, LayoutGrid,
  Square,
} from "lucide-react";

export type AgentStatus = "pending" | "running" | "ok" | "error" | "degraded" | "waiting";

export interface AgentState {
  status: AgentStatus;
  detail?: string;
}

export interface PipelineState {
  env:          AgentState;
  researcher:   AgentState;
  plugins:      AgentState;
  planner:      AgentState;
  beat_writer:  AgentState;
  coder:        AgentState;
  visual_qa:    AgentState;
  scene_review: AgentState;
  editor:       AgentState;
  curator:      AgentState;
}

export const INITIAL_PIPELINE: PipelineState = {
  env:          { status: "pending" },
  researcher:   { status: "pending" },
  plugins:      { status: "pending" },
  planner:      { status: "pending" },
  beat_writer:  { status: "pending" },
  coder:        { status: "pending" },
  visual_qa:    { status: "pending" },
  scene_review: { status: "pending" },
  editor:       { status: "pending" },
  curator:      { status: "pending" },
};

interface AgentDef {
  id: keyof PipelineState;
  label: string;
  description: string;
  icon: React.ElementType;
  skillFiles: string[];
  isGate?: boolean;
}

const AGENTS: AgentDef[] = [
  {
    id: "researcher",
    label: "Researcher",
    description: "Busca plugins relevantes en la web",
    icon: Search,
    skillFiles: [],
  },
  {
    id: "plugins",
    label: "Plugins",
    description: "Aprobación de plugins propuestos",
    icon: Puzzle,
    skillFiles: [],
    isGate: true,
  },
  {
    id: "planner",
    label: "Planner",
    description: "Crea el outline con escenas",
    icon: BookOpen,
    skillFiles: ["SKILL.md"],
  },
  {
    id: "beat_writer",
    label: "Beat Writer",
    description: "Divide cada escena en beats voz↔animación",
    icon: ListOrdered,
    skillFiles: ["references/narration.md", "templates/voiceover.py"],
  },
  {
    id: "coder",
    label: "Coder",
    description: "Escribe VoiceoverScene con un with self.voiceover por beat",
    icon: Code2,
    skillFiles: ["SKILL.md", "references/api-cheatsheet.md", "references/troubleshooting.md", "templates/voiceover.py"],
  },
  {
    id: "visual_qa",
    label: "Visual QA",
    description: "Analiza frames y detecta errores",
    icon: Eye,
    skillFiles: ["SKILL.md", "references/troubleshooting.md"],
  },
  {
    id: "scene_review",
    label: "Scene Review",
    description: "Aprobación por escena (gate humano)",
    icon: LayoutGrid,
    skillFiles: [],
    isGate: true,
  },
  {
    id: "editor",
    label: "Editor",
    description: "Render -qh + concatenación (audio ya embebido)",
    icon: Film,
    skillFiles: [],
  },
  {
    id: "curator",
    label: "Curator",
    description: "Extrae aprendizajes y actualiza skills",
    icon: Brain,
    skillFiles: ["SKILL.md", "references/troubleshooting.md"],
  },
];

function StatusIcon({ status }: { status: AgentStatus }) {
  if (status === "running")  return <Loader2 className="w-4 h-4 animate-spin text-blue-400" />;
  if (status === "ok")       return <CheckCircle className="w-4 h-4 text-green-400" />;
  if (status === "error")    return <XCircle className="w-4 h-4 text-red-400" />;
  if (status === "degraded") return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
  if (status === "waiting")  return <Loader2 className="w-4 h-4 animate-spin text-yellow-400" />;
  return <Circle className="w-4 h-4 text-zinc-600" />;
}

function statusBorder(status: AgentStatus) {
  if (status === "running")  return "border-blue-500 animate-pulse-glow";
  if (status === "ok")       return "border-green-500 animate-pulse-glow-green";
  if (status === "error")    return "border-red-500";
  if (status === "degraded") return "border-yellow-500";
  if (status === "waiting")  return "border-yellow-600";
  return "border-zinc-800";
}

function statusBg(status: AgentStatus) {
  if (status === "running")  return "bg-blue-950/20";
  if (status === "ok")       return "bg-green-950/20";
  if (status === "error")    return "bg-red-950/20";
  if (status === "degraded") return "bg-yellow-950/20";
  return "bg-zinc-900";
}

interface ConnectorProps {
  active: boolean;
}

function Connector({ active }: ConnectorProps) {
  return (
    <div className="flex items-center justify-center w-8 flex-shrink-0">
      <svg width="32" height="20" viewBox="0 0 32 20" className="overflow-visible">
        <line x1="0" y1="10" x2="32" y2="10" stroke="#3f3f46" strokeWidth="2" />
        {active && (
          <line
            x1="0" y1="10" x2="32" y2="10"
            stroke="#3b82f6" strokeWidth="2"
            className="pipeline-connector"
          />
        )}
        <polygon points="26,6 32,10 26,14" fill={active ? "#3b82f6" : "#3f3f46"} />
      </svg>
    </div>
  );
}

interface Props {
  pipeline: PipelineState;
  onPluginsClick?: () => void;
  onSceneReviewClick?: () => void;
  onNodeClick?: (agentId: string) => void;
  onStop?: () => void | Promise<void>;
}

export function PipelineView({ pipeline, onPluginsClick, onSceneReviewClick, onNodeClick, onStop }: Props) {
  const [editAgent, setEditAgent] = useState<AgentDef | null>(null);
  const [stopping, setStopping] = useState(false);
  const anyRunning = Object.values(pipeline).some((s) => s.status === "running");

  const handleStop = async () => {
    if (!onStop || stopping) return;
    if (!confirm("¿Detener el pipeline? Los subprocesos en curso se matarán y el proyecto quedará en estado 'stopped'.")) return;
    setStopping(true);
    try { await onStop(); }
    finally { setStopping(false); }
  };

  return (
    <div className="w-full">
      {/* Stop button — only visible while something is running */}
      {anyRunning && onStop && (
        <div className="flex justify-end mb-2">
          <button
            onClick={handleStop}
            disabled={stopping}
            className="inline-flex items-center gap-1.5 rounded-md border border-red-700/60 bg-red-950/40 px-3 py-1.5 text-xs font-medium text-red-300 hover:bg-red-900/40 disabled:opacity-50 transition-colors"
            title="Detener el pipeline y matar subprocesos en curso"
          >
            {stopping ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Square className="w-3.5 h-3.5 fill-current" />}
            {stopping ? "Deteniendo…" : "Detener pipeline"}
          </button>
        </div>
      )}

      {/* Pipeline row — scrollable horizontally on small screens */}
      <div className="overflow-x-auto pb-4">
        <div className="flex items-center gap-0 min-w-max">
          {AGENTS.map((agent, idx) => {
            const state = pipeline[agent.id];
            const Icon  = agent.icon;
            const isActive = state.status === "running" || state.status === "ok";
            const showConnector = idx < AGENTS.length - 1;
            const hasSkills = agent.skillFiles.length > 0;
            const isRunning = state.status === "running";
            const isCompleted = state.status === "ok" || state.status === "error" || state.status === "degraded";

            // Click priority: gate action > live logs (if running) > skill editor > historical logs
            const showLogs = !agent.isGate && onNodeClick && (isRunning || isCompleted);
            const showSkillEditor = !agent.isGate && !isRunning && hasSkills;
            const clickable =
              (agent.isGate && state.status === "waiting") ||
              isRunning ||
              showSkillEditor ||
              showLogs;

            const hoverBorder =
              agent.isGate && state.status === "waiting" ? "hover:border-yellow-400" :
              isRunning ? "hover:border-blue-400" :
              showSkillEditor ? "hover:border-zinc-600" :
              showLogs ? "hover:border-zinc-500" : "";

            const title =
              agent.id === "plugins" ? "Clic para gestionar plugins" :
              agent.id === "scene_review" ? "Clic para revisar escenas" :
              isRunning ? "Clic para ver logs en vivo" :
              showSkillEditor ? "Clic para editar skill" :
              showLogs ? "Clic para ver actividad" : undefined;

            return (
              <div key={agent.id} className="flex items-center">
                {/* Node */}
                <div
                  className={`pipeline-node flex flex-col items-center gap-2 p-3.5 rounded-xl border-2 w-[120px] flex-shrink-0 transition-all duration-200 ${statusBorder(state.status)} ${statusBg(state.status)} ${clickable ? `cursor-pointer ${hoverBorder}` : "cursor-default"}`}
                  onClick={() => {
                    if (agent.isGate && agent.id === "plugins" && onPluginsClick) {
                      onPluginsClick();
                    } else if (agent.isGate && agent.id === "scene_review" && onSceneReviewClick) {
                      onSceneReviewClick();
                    } else if (isRunning && onNodeClick) {
                      onNodeClick(agent.id);
                    } else if (showSkillEditor) {
                      setEditAgent(agent);
                    } else if (showLogs) {
                      onNodeClick!(agent.id);
                    }
                  }}
                  title={title}
                >
                  <div className="flex items-center justify-between w-full">
                    <Icon className={`w-4 h-4 ${state.status === "pending" ? "text-zinc-600" : "text-zinc-300"}`} />
                    <StatusIcon status={state.status} />
                  </div>
                  <div className="text-center">
                    <p className={`text-xs font-semibold ${state.status === "pending" ? "text-zinc-500" : "text-zinc-100"}`}>
                      {agent.label}
                    </p>
                    <p className="text-[10px] text-zinc-500 leading-tight mt-0.5">
                      {agent.description}
                    </p>
                  </div>
                  {isRunning && !agent.isGate ? (
                    <div className="text-[9px] text-blue-400 font-medium uppercase tracking-wide">
                      ver logs
                    </div>
                  ) : hasSkills ? (
                    <div className="text-[9px] text-zinc-600 font-medium uppercase tracking-wide">
                      editar skill
                    </div>
                  ) : null}
                  {state.detail && (
                    <p className="text-[10px] text-zinc-400 text-center line-clamp-2">
                      {state.detail}
                    </p>
                  )}
                </div>

                {showConnector && (
                  <Connector active={isActive} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Skill editor modal */}
      {editAgent && (
        <SkillEditor
          agentName={editAgent.label}
          defaultFiles={editAgent.skillFiles}
          onClose={() => setEditAgent(null)}
        />
      )}
    </div>
  );
}
