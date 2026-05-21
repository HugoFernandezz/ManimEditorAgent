"use client";
import { useState } from "react";
import { SkillEditor } from "@/components/skill-editor";
import {
  Search, Puzzle, BookOpen, Code2, Eye,
  Mic, Film, Brain, ArrowDown, FileText,
} from "lucide-react";
import type { Project } from "@/lib/api";

interface StepDef {
  id: string;
  icon: React.ElementType;
  label: string;
  role: string;
  inputs: string[];
  outputs: string[];
  model: string;
  tools?: string;
  skillFiles: string[];
  isGate?: boolean;
  color: string;          // tailwind border/icon color class
  bgColor: string;
}

const STEPS: StepDef[] = [
  {
    id: "researcher",
    icon: Search,
    label: "Researcher",
    role: "Busca plugins de Manim relevantes para la idea",
    inputs: ["idea del video"],
    outputs: ["lista de plugins propuestos (plugins_proposal.json)"],
    model: "claude sonnet",
    tools: "WebSearch · WebFetch",
    skillFiles: [],
    color: "text-cyan-400 border-cyan-800",
    bgColor: "bg-cyan-950/20",
  },
  {
    id: "plugins",
    icon: Puzzle,
    label: "Plugins Gate",
    role: "El usuario aprueba qué plugins instalar (pip install)",
    inputs: ["plugins_proposal.json"],
    outputs: ["plugins instalados en el entorno Python"],
    model: "— (acción humana)",
    skillFiles: [],
    isGate: true,
    color: "text-yellow-400 border-yellow-800",
    bgColor: "bg-yellow-950/20",
  },
  {
    id: "planner",
    icon: BookOpen,
    label: "Planner",
    role: "Crea el outline narrativo con 3-7 escenas verificadas",
    inputs: ["idea", "idioma", "audiencia", "duración objetivo"],
    outputs: ["outline.md con escenas, duraciones y puntos clave"],
    model: "claude sonnet",
    skillFiles: ["SKILL.md"],
    color: "text-blue-400 border-blue-800",
    bgColor: "bg-blue-950/20",
  },
  {
    id: "coder",
    icon: Code2,
    label: "Coder",
    role: "Escribe el código ManimCE por escena (hasta 3 ciclos de fix)",
    inputs: ["outline.md", "template (basic/math/threed)", "errores previos"],
    outputs: ["scenes/scene_NN.py", "renders/scene_NN/preview.mp4"],
    model: "claude opus",
    skillFiles: ["SKILL.md", "references/api-cheatsheet.md", "references/troubleshooting.md", "templates/basic.py", "templates/math.py"],
    color: "text-violet-400 border-violet-800",
    bgColor: "bg-violet-950/20",
  },
  {
    id: "visual_qa",
    icon: Eye,
    label: "Visual QA",
    role: "Analiza 6 frames del render y propone correcciones (máx 3 ciclos)",
    inputs: ["6 frames PNG del render", "scene_NN.py", "outline de la escena"],
    outputs: ["qa_notes.md (status: ok | needs_fix + fix_hints)"],
    model: "claude opus",
    tools: "Read (imágenes)",
    skillFiles: ["SKILL.md", "references/troubleshooting.md"],
    color: "text-pink-400 border-pink-800",
    bgColor: "bg-pink-950/20",
  },
  {
    id: "narrator",
    icon: Mic,
    label: "Narrator",
    role: "Escribe el guion de voz segmentado por escena y sintetiza audio",
    inputs: ["outline.md", "duraciones reales de cada escena"],
    outputs: ["audio/script.txt", "audio/scene_NN.wav (TTS o silencioso)"],
    model: "claude sonnet",
    skillFiles: ["references/narration.md"],
    color: "text-emerald-400 border-emerald-800",
    bgColor: "bg-emerald-950/20",
  },
  {
    id: "editor",
    icon: Film,
    label: "Editor",
    role: "Render final en alta calidad, mux audio+vídeo, concatena escenas",
    inputs: ["scene_NN.py (×N)", "scene_NN.wav (×N)"],
    outputs: ["final/video_{lang}.mp4"],
    model: "— (ffmpeg + manim -qh)",
    skillFiles: [],
    color: "text-orange-400 border-orange-800",
    bgColor: "bg-orange-950/20",
  },
  {
    id: "curator",
    icon: Brain,
    label: "Curator",
    role: "Post-aprobación: extrae aprendizajes y propone mejoras a las skills",
    inputs: ["outline.md", "qa_notes.md (×N)", "feedback.json del usuario"],
    outputs: ["learnings/notes.md", "learnings/skill_patch.diff"],
    model: "claude sonnet",
    skillFiles: ["SKILL.md", "references/troubleshooting.md"],
    color: "text-rose-400 border-rose-800",
    bgColor: "bg-rose-950/20",
  },
];

interface Props {
  project: Project;
}

export function FlowDiagram({ project }: Props) {
  const [editStep, setEditStep] = useState<StepDef | null>(null);

  return (
    <div className="max-w-2xl mx-auto space-y-0">
      {/* Context banner */}
      <div className="mb-6 px-4 py-3 rounded-xl bg-zinc-900 border border-zinc-800 text-sm text-zinc-400">
        <span className="text-zinc-200 font-medium">Idea: </span>
        {project.idea}
        <span className="mx-2 text-zinc-600">·</span>
        <span className="text-zinc-500">{project.lang.toUpperCase()}</span>
        <span className="mx-2 text-zinc-600">·</span>
        <span className="text-zinc-500">{project.audience}</span>
        <span className="mx-2 text-zinc-600">·</span>
        <span className="text-zinc-500">{project.target_length}</span>
      </div>

      {STEPS.map((step, idx) => {
        const Icon = step.icon;
        const isLast = idx === STEPS.length - 1;
        const hasSkills = step.skillFiles.length > 0;

        return (
          <div key={step.id} className="flex flex-col items-center animate-fade-in-up"
            style={{ animationDelay: `${idx * 60}ms` }}>
            {/* Node */}
            <div
              className={`w-full rounded-xl border ${step.color.split(" ")[1]} ${step.bgColor} p-4 transition-all duration-200 ${
                hasSkills
                  ? "cursor-pointer hover:brightness-110 hover:scale-[1.01]"
                  : "cursor-default"
              }`}
              onClick={() => hasSkills && setEditStep(step)}
            >
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div className={`mt-0.5 p-2 rounded-lg bg-zinc-900/60 flex-shrink-0`}>
                  <Icon className={`w-4 h-4 ${step.color.split(" ")[0]}`} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-zinc-100">{step.label}</span>
                    {step.isGate && (
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-yellow-900/50 text-yellow-400 border border-yellow-800">
                        acción humana
                      </span>
                    )}
                    <span className="text-[10px] text-zinc-500 font-mono ml-auto">{step.model}</span>
                  </div>

                  <p className="text-xs text-zinc-300 leading-relaxed">{step.role}</p>

                  {step.tools && (
                    <p className="text-[11px] text-zinc-500">
                      <span className="text-zinc-600">tools:</span> {step.tools}
                    </p>
                  )}

                  {/* IO */}
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wide mb-1">Entrada</p>
                      <ul className="space-y-0.5">
                        {step.inputs.map((inp, i) => (
                          <li key={i} className="text-[11px] text-zinc-400 flex items-start gap-1">
                            <span className="text-zinc-600 mt-0.5">›</span> {inp}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <p className="text-[10px] text-zinc-600 uppercase tracking-wide mb-1">Salida</p>
                      <ul className="space-y-0.5">
                        {step.outputs.map((out, i) => (
                          <li key={i} className="text-[11px] text-zinc-400 flex items-start gap-1">
                            <span className="text-zinc-600 mt-0.5">›</span> {out}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Skill files */}
                  {hasSkills && (
                    <div className="flex items-center gap-1.5 pt-1 flex-wrap">
                      <FileText className="w-3 h-3 text-zinc-600" />
                      {step.skillFiles.map((f) => (
                        <span key={f} className="text-[10px] font-mono text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
                          {f.split("/").pop()}
                        </span>
                      ))}
                      <span className="text-[10px] text-zinc-600 ml-auto">clic para editar →</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Connector arrow */}
            {!isLast && (
              <div className="flex flex-col items-center py-1 text-zinc-700">
                <div className="w-px h-4 bg-zinc-700" />
                <ArrowDown className="w-3 h-3" />
              </div>
            )}
          </div>
        );
      })}

      {editStep && (
        <SkillEditor
          agentName={editStep.label}
          defaultFiles={editStep.skillFiles}
          onClose={() => setEditStep(null)}
        />
      )}
    </div>
  );
}
