"use client";
import { useState } from "react";
import { SkillEditor } from "@/components/skill-editor";
import {
  Search, BookOpen, Code2, Eye, Mic, Film, Brain,
  Puzzle, CheckCircle, XCircle, AlertTriangle, Loader2, Circle,
} from "lucide-react";

export type AgentStatus = "pending" | "running" | "ok" | "error" | "degraded" | "waiting";

export interface AgentState {
  status: AgentStatus;
  detail?: string;
}

export interface PipelineState {
  env:        AgentState;
  researcher: AgentState;
  plugins:    AgentState;
  planner:    AgentState;
  coder:      AgentState;
  visual_qa:  AgentState;
  narrator:   AgentState;
  editor:     AgentState;
  curator:    AgentState;
}

export const INITIAL_PIPELINE: PipelineState = {
  env:        { status: "pending" },
  researcher: { status: "pending" },
  plugins:    { status: "pending" },
  planner:    { status: "pending" },
  coder:      { status: "pending" },
  visual_qa:  { status: "pending" },
  narrator:   { status: "pending" },
  editor:     { status: "pending" },
  curator:    { status: "pending" },
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
    id: "coder",
    label: "Coder",
    description: "Escribe el código ManimCE",
    icon: Code2,
    skillFiles: ["SKILL.md", "references/api-cheatsheet.md", "references/troubleshooting.md", "templates/basic.py", "templates/math.py"],
  },
  {
    id: "visual_qa",
    label: "Visual QA",
    description: "Analiza frames y detecta errores",
    icon: Eye,
    skillFiles: ["SKILL.md", "references/troubleshooting.md"],
  },
  {
    id: "narrator",
    label: "Narrator",
    description: "Genera el guion y sintetiza voz",
    icon: Mic,
    skillFiles: ["references/narration.md"],
  },
  {
    id: "editor",
    label: "Editor",
    description: "Render final y concatenación",
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
  projectId?: string;
  onPluginsClick?: () => void;
}

export function PipelineView({ pipeline, projectId, onPluginsClick }: Props) {
  const [editAgent, setEditAgent] = useState<AgentDef | null>(null);

  return (
    <div className="w-full">
      {/* Pipeline row — scrollable horizontally on small screens */}
      <div className="overflow-x-auto pb-4">
        <div className="flex items-center gap-0 min-w-max">
          {AGENTS.map((agent, idx) => {
            const state = pipeline[agent.id];
            const Icon  = agent.icon;
            const isActive = state.status === "running" || state.status === "ok";
            const showConnector = idx < AGENTS.length - 1;
            const hasSkills = agent.skillFiles.length > 0;

            return (
              <div key={agent.id} className="flex items-center">
                {/* Node */}
                <div
                  className={`pipeline-node flex flex-col items-center gap-2 p-3.5 rounded-xl border-2 w-[120px] flex-shrink-0 transition-all duration-200 ${statusBorder(state.status)} ${statusBg(state.status)} ${
                    agent.isGate && state.status === "waiting"
                      ? "cursor-pointer hover:border-yellow-400"
                      : hasSkills
                      ? "cursor-pointer hover:border-zinc-600"
                      : "cursor-default"
                  }`}
                  onClick={() => {
                    if (agent.isGate && onPluginsClick) {
                      onPluginsClick();
                    } else if (hasSkills) {
                      setEditAgent(agent);
                    }
                  }}
                  title={hasSkills ? "Clic para editar skill" : agent.isGate ? "Clic para gestionar plugins" : undefined}
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
                  {hasSkills && (
                    <div className="text-[9px] text-zinc-600 font-medium uppercase tracking-wide">
                      editar skill
                    </div>
                  )}
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
