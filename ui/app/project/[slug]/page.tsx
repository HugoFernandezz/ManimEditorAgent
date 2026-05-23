"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { fetchProject, videoUrl, stopPipeline, type Project } from "@/lib/api";
import { PipelineView } from "@/components/pipeline-view";
import { FlowDiagram } from "@/components/flow-diagram";
import { StartVideoForm } from "@/components/start-video-form";
import { Button } from "@/components/ui/button";
import { usePipeline } from "@/lib/use-pipeline";
import { AgentLogPanel } from "@/components/agent-log-panel";
import type { PipelineState } from "@/components/pipeline-view";

const AGENT_LABELS: Partial<Record<keyof PipelineState, string>> = {
  env: "Check Env", researcher: "Researcher", plugins: "Plugins",
  planner: "Planner", beat_writer: "Beat Writer", coder: "Coder",
  visual_qa: "Visual QA", scene_review: "Scene Review",
  editor: "Editor", curator: "Curator",
};
import {
  ChevronDown, ChevronRight, Workflow, Rocket,
  Loader2, Pause, CheckCircle, XCircle, CircleDot, Settings,
} from "lucide-react";

type Tab = "flow" | "execution";

const TAB_DEFS: ReadonlyArray<{ id: Tab; label: string; Icon: React.ElementType }> = [
  { id: "flow",      label: "Vista del flujo", Icon: Workflow },
  { id: "execution", label: "Ejecución",       Icon: Rocket },
];

// ── Status banner ────────────────────────────────────────────────────────────

// action.href  → Link to another route
// action.restart → call onRestart() to switch to the flow tab on this page
interface BannerAction {
  label: string;
  btnClass: string;
  href?: string;
  restart?: true;
}

interface BannerConfig {
  border: string;
  bg: string;
  Icon: React.ElementType;
  iconClass: string;
  spin?: boolean;
  title: string;
  description: string;
  action?: BannerAction;
}

function buildBannerConfig(project: Project, slug: string): BannerConfig {
  const s = project.status;

  if (s === "draft") return {
    border: "border-zinc-700", bg: "bg-zinc-900",
    Icon: CircleDot, iconClass: "text-zinc-500",
    title: "Sin iniciar",
    description: "Configura el video en la pestaña «Vista del flujo» para arrancar el pipeline.",
  };

  if (s === "running" || s === "planning_done") return {
    border: "border-blue-700", bg: "bg-blue-950/20",
    Icon: Loader2, iconClass: "text-blue-400", spin: true,
    title: s === "planning_done" ? "Pipeline activo — Beat Writer" : "Pipeline activo",
    description: s === "planning_done"
      ? "El Planner terminó el outline. El Beat Writer está generando los beats por escena."
      : "Los agentes están trabajando. Si los logs no cambian en varios minutos, el pipeline puede estar atascado.",
    action: { label: "Reiniciar pipeline", btnClass: "bg-zinc-700 hover:bg-zinc-600", restart: true },
  };

  if (s === "awaiting_plugins") return {
    border: "border-yellow-600", bg: "bg-yellow-950/20",
    Icon: Pause, iconClass: "text-yellow-400",
    title: "Pausado — Esperando aprobación de plugins",
    description: "El Researcher encontró plugins relevantes. Revísalos y elige cuáles instalar para continuar.",
    action: { label: "Revisar plugins →", href: `/project/${slug}/plugins`, btnClass: "bg-yellow-600 hover:bg-yellow-500" },
  };

  if (s === "awaiting_scene_review") return {
    border: "border-teal-600", bg: "bg-teal-950/20",
    Icon: Pause, iconClass: "text-teal-400",
    title: "Pausado — Esperando revisión de escenas",
    description: "Todas las escenas han sido renderizadas. Revisa cada preview, apruébalas o pide cambios antes del render final.",
    action: { label: "Revisar escenas →", href: `/project/${slug}/scenes`, btnClass: "bg-teal-600 hover:bg-teal-500" },
  };

  if (s === "scenes_approved") return {
    border: "border-teal-600", bg: "bg-teal-950/20",
    Icon: Pause, iconClass: "text-teal-400",
    title: "Pausado — Todas las escenas aprobadas",
    description: "Pulsa «Render final» en la página de escenas para generar el video en alta calidad.",
    action: { label: "Ir a escenas →", href: `/project/${slug}/scenes`, btnClass: "bg-teal-600 hover:bg-teal-500" },
  };

  if (s === "awaiting_review") return {
    border: "border-purple-600", bg: "bg-purple-950/20",
    Icon: Pause, iconClass: "text-purple-400",
    title: "Pausado — Video final listo para revisar",
    description: "El video final está renderizado. Míralo, apruébalo o da feedback.",
    action: { label: "Revisar y aprobar video →", href: `/project/${slug}/review`, btnClass: "bg-purple-600 hover:bg-purple-500" },
  };

  if (s === "curated") return {
    border: "border-green-700", bg: "bg-green-950/20",
    Icon: CheckCircle, iconClass: "text-green-400",
    title: "Completado",
    description: "El video fue aprobado y el Curator extrajo aprendizajes para mejorar la skill de Manim.",
    action: { label: "Ver aprendizajes →", href: `/project/${slug}/learnings`, btnClass: "bg-zinc-700 hover:bg-zinc-600" },
  };

  if (s === "error" || s === "env_failed") return {
    border: "border-red-700", bg: "bg-red-950/20",
    Icon: XCircle, iconClass: "text-red-400",
    title: s === "env_failed" ? "Error de entorno" : "Error en el pipeline",
    description: project.error
      ?? (s === "env_failed"
        ? "Falta alguna dependencia (manim, ffmpeg, latex). Ejecuta check_env.py y reinicia."
        : "El pipeline falló. Revisa los logs abajo y reinicia el pipeline."),
    action: { label: "Reiniciar pipeline", btnClass: "bg-red-700 hover:bg-red-600", restart: true },
  };

  return {
    border: "border-zinc-700", bg: "bg-zinc-900",
    Icon: Settings, iconClass: "text-zinc-500",
    title: `Estado: ${s}`,
    description: "Estado intermedio del pipeline.",
    action: { label: "Reiniciar pipeline", btnClass: "bg-zinc-700 hover:bg-zinc-600", restart: true },
  };
}

interface StatusBannerProps {
  project: Project;
  slug: string;
  onRestart: () => void;
}

function StatusBanner({ project, slug, onRestart }: StatusBannerProps) {
  const conf = buildBannerConfig(project, slug);
  const Icon = conf.Icon;
  return (
    <div className={`rounded-xl border ${conf.border} ${conf.bg} px-4 py-3.5 flex items-center gap-4`}>
      <Icon className={`w-5 h-5 flex-shrink-0 ${conf.iconClass} ${conf.spin ? "animate-spin" : ""}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-zinc-100">{conf.title}</p>
        <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">{conf.description}</p>
      </div>
      {conf.action && (
        conf.action.restart
          ? <Button onClick={onRestart} className={`flex-shrink-0 text-sm ${conf.action.btnClass}`}>
              {conf.action.label}
            </Button>
          : <Link href={conf.action.href!} className="flex-shrink-0">
              <Button className={`text-sm ${conf.action.btnClass}`}>{conf.action.label}</Button>
            </Link>
      )}
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const slug   = params.slug as string;

  const { project, setProject, pipeline, logs, outline, qaNotes, agentLogs } = usePipeline(slug);

  // userTab: explicitly chosen by user (null = derive from project status)
  const [userTab, setUserTab] = useState<Tab | null>(null);
  const [activeLogAgent, setActiveLogAgent] = useState<string | null>(null);
  // Derive tab: execution when pipeline is active, flow otherwise
  const tab: Tab = userTab ?? (!project || project.status === "draft" ? "flow" : "execution");

  const [expanded, setExpanded] = useState<number | null>(null);
  const logsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  function handleTabClick(t: Tab) { setUserTab(t); }
  function handleRestart() { setUserTab("flow"); }

  const isRunning = useMemo(
    () => Object.values(pipeline).some((s) => s.status === "running"),
    [pipeline],
  );

  return (
    <div className="space-y-5 max-w-full">
      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-zinc-900 border border-zinc-800 rounded-xl w-fit">
        {TAB_DEFS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => handleTabClick(id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === id ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
            {id === "execution" && isRunning && (
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse ml-0.5" />
            )}
          </button>
        ))}
      </div>

      {/* ── Tab: Flow ── */}
      {tab === "flow" && !project && (
        <div className="text-sm text-zinc-500 py-8 text-center">Cargando...</div>
      )}
      {tab === "flow" && project && (() => {
        const restartable = ["draft","error","env_failed","stopped","running","awaiting_plugins","planning_done"];
        const showForm = restartable.includes(project.status);
        return showForm ? (
          <div className="space-y-4">
            {project.status !== "draft" && (
              <div className="rounded-xl border border-amber-700 bg-amber-950/20 px-4 py-3 text-sm text-amber-300">
                <strong>Reiniciar pipeline</strong> — Esto lanzará el pipeline desde el principio
                con los nuevos parámetros que configures abajo.
                {project.status === "running" || project.status === "awaiting_plugins"
                  ? " Cualquier progreso anterior se descartará."
                  : ""}
              </div>
            )}
            <StartVideoForm
              projectId={slug}
              defaults={project ?? undefined}
              onStarted={() => {
                handleTabClick("execution");
                fetchProject(slug).then(setProject);
              }}
            />
          </div>
        ) : (
          <FlowDiagram project={project} />
        );
      })()}

      {/* ── Tab: Execution ── */}
      {tab === "execution" && (
        <div className="space-y-5">

          {/* Status banner — always first */}
          {project
            ? <StatusBanner project={project} slug={slug} onRestart={handleRestart} />
            : <div className="h-16 rounded-xl border border-zinc-800 bg-zinc-900 animate-pulse" />
          }

          {/* Pipeline nodes */}
          <section>
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">
              Nodos del pipeline
            </h3>
            <PipelineView
              pipeline={pipeline}
              onPluginsClick={() => router.push(`/project/${slug}/plugins`)}
              onSceneReviewClick={() => router.push(`/project/${slug}/scenes`)}
              onNodeClick={(id) => setActiveLogAgent(id)}
              onStop={async () => {
                await stopPipeline(slug);
                fetchProject(slug).then(setProject).catch(() => {});
              }}
            />
          </section>

          {/* Outline + final video */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {outline && (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
                <div className="px-4 py-2.5 border-b border-zinc-800">
                  <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wide">Outline</p>
                </div>
                <pre className="p-4 text-xs text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed max-h-72 overflow-y-auto">
                  {outline}
                </pre>
              </div>
            )}
            {project?.final_video && (
              <div className="rounded-xl overflow-hidden border border-zinc-800 bg-black">
                <video controls className="w-full" src={videoUrl(slug)} />
              </div>
            )}
          </div>

          {/* QA per scene */}
          {Object.keys(qaNotes).length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">QA por escena</h3>
              {Object.entries(qaNotes).map(([num, notes]) => {
                const sceneNum = Number(num);
                const isOk = notes === "ok";
                const isDegraded = notes === "degraded";
                const dotClass = isOk ? "bg-green-400" : isDegraded ? "bg-yellow-400" : "bg-blue-400";
                const label    = isOk ? "Sin problemas" : isDegraded ? "Degraded" : "Issues";
                return (
                  <div key={num} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
                    <button
                      onClick={() => setExpanded(expanded === sceneNum ? null : sceneNum)}
                      className="w-full flex items-center justify-between px-4 py-2.5 text-sm hover:bg-zinc-800/60 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
                        <span className="text-xs font-medium">Escena {num}</span>
                        <span className="text-xs text-zinc-500">{label}</span>
                      </div>
                      {expanded === sceneNum
                        ? <ChevronDown className="w-3 h-3 text-zinc-500" />
                        : <ChevronRight className="w-3 h-3 text-zinc-500" />}
                    </button>
                    {expanded === sceneNum && !isOk && (
                      <pre className="px-4 pb-3 text-[11px] text-zinc-400 whitespace-pre-wrap font-mono border-t border-zinc-800">
                        {notes}
                      </pre>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Pipeline logs */}
          <div className="bg-black border border-zinc-800 rounded-xl overflow-hidden">
            <div className="px-4 py-2 border-b border-zinc-800">
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-wide">Pipeline logs</p>
            </div>
            <div ref={logsRef} className="h-36 overflow-y-auto p-3 space-y-0.5 font-mono text-[11px]">
              {logs.length === 0
                ? <span className="text-zinc-600">Esperando eventos del pipeline...</span>
                : logs.map((l, i) => <div key={i} className="text-zinc-500">{l}</div>)
              }
            </div>
          </div>
        </div>
      )}

      {/* Agent log panel (slide-over) */}
      {activeLogAgent && (
        <AgentLogPanel
          agentKey={activeLogAgent}
          agentLabel={AGENT_LABELS[activeLogAgent as keyof PipelineState] ?? activeLogAgent}
          logs={agentLogs}
          onClose={() => setActiveLogAgent(null)}
        />
      )}
    </div>
  );
}
