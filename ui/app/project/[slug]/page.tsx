"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  fetchProject, createWebSocket, videoUrl,
  type Project, type PipelineEvent,
} from "@/lib/api";
import {
  PipelineView, INITIAL_PIPELINE, type PipelineState, type AgentStatus,
} from "@/components/pipeline-view";
import { FlowDiagram } from "@/components/flow-diagram";
import { StartVideoForm } from "@/components/start-video-form";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Play, Workflow, Rocket } from "lucide-react";

type Tab = "flow" | "execution";

/* Map pipeline events → agent status updates */
function applyEvent(state: PipelineState, e: PipelineEvent): PipelineState {
  const next = { ...state };
  const { kind, payload } = e;

  const setAgent = (id: keyof PipelineState, status: AgentStatus, detail?: string) => {
    next[id] = { status, detail };
  };

  if (kind === "env_check_ok")    setAgent("env" as any, "ok");
  if (kind === "env_check_failed") setAgent("env" as any, "error", payload.message as string);

  if (kind === "agent_started") {
    const a = payload.agent as string;
    if (a === "researcher") setAgent("researcher", "running");
    if (a === "planner")    setAgent("planner",    "running");
    if (a === "narrator")   setAgent("narrator",   "running");
    if (a === "editor")     setAgent("editor",     "running");
    if (a === "curator")    setAgent("curator",    "running");
    if (a === "coder")      setAgent("coder",      "running");
    if (a === "visual_qa")  setAgent("visual_qa",  "running");
  }

  if (kind === "plugins_proposed") {
    setAgent("researcher", "ok");
    setAgent("plugins", "waiting", "Esperando aprobación");
  }
  if (kind === "plugins_installed") setAgent("plugins", "ok");

  if (kind === "outline_ready") setAgent("planner", "ok");
  if (kind === "render_ok")     setAgent("coder",   "ok");
  if (kind === "render_failed") setAgent("coder",   "degraded");
  if (kind === "qa_ok")         setAgent("visual_qa", "ok");
  if (kind === "qa_issue")      setAgent("visual_qa", "running", `Cycle ${payload.cycle}`);
  if (kind === "qa_degraded")   setAgent("visual_qa", "degraded");
  if (kind === "narration_ready") setAgent("narrator", "ok");
  if (kind === "edit_done")     setAgent("editor",  "ok");
  if (kind === "curator_done")  setAgent("curator", "ok");

  if (kind === "error") {
    // Mark the first running agent as errored
    (Object.keys(next) as (keyof PipelineState)[]).forEach((k) => {
      if (next[k].status === "running") next[k] = { status: "error" };
    });
  }

  return next;
}

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const slug   = params.slug as string;

  const [tab,      setTab]      = useState<Tab>("flow");
  const [project,  setProject]  = useState<Project | null>(null);
  const [pipeline, setPipeline] = useState<PipelineState>(INITIAL_PIPELINE);
  const [logs,     setLogs]     = useState<string[]>([]);
  const [outline,  setOutline]  = useState("");
  const [qaNotes,  setQaNotes]  = useState<Record<number, string>>({});
  const [expanded, setExpanded] = useState<number | null>(null);
  const logsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchProject(slug).then(setProject);
    const ws = createWebSocket(slug, handleEvent);
    return () => ws.close();
  }, [slug]);

  useEffect(() => {
    if (logsRef.current) logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  function handleEvent(e: PipelineEvent) {
    setPipeline((prev) => applyEvent(prev, e));
    setLogs((prev) => [...prev.slice(-299), `[${e.kind}] ${JSON.stringify(e.payload).slice(0, 100)}`]);
    if (e.kind === "outline_ready") setOutline((e.payload.outline as string) ?? "");
    if (e.kind === "qa_issue")  setQaNotes((p) => ({ ...p, [e.payload.scene as number]: e.payload.notes as string }));
    if (e.kind === "qa_ok")     setQaNotes((p) => ({ ...p, [e.payload.scene as number]: "ok" }));
    if (e.kind === "qa_degraded") setQaNotes((p) => ({ ...p, [e.payload.scene as number]: "degraded" }));
    if (e.kind === "edit_done") fetchProject(slug).then(setProject);
  }

  const canReview  = project?.status === "awaiting_review";
  const canPlugins = project?.status === "awaiting_plugins";
  const isCurated  = project?.status === "curated";

  return (
    <div className="space-y-5 max-w-full">
      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-zinc-900 border border-zinc-800 rounded-xl w-fit">
        <button
          onClick={() => setTab("flow")}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "flow"
              ? "bg-zinc-800 text-zinc-100"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <Workflow className="w-4 h-4" />
          Vista del flujo
        </button>
        <button
          onClick={() => setTab("execution")}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === "execution"
              ? "bg-zinc-800 text-zinc-100"
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <Rocket className="w-4 h-4" />
          Ejecución
          {pipeline && Object.values(pipeline).some(s => s.status === "running") && (
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse ml-0.5" />
          )}
        </button>
      </div>

      {/* ── Tab: Flow preview ── */}
      {tab === "flow" && !project && (
        <div className="text-sm text-zinc-500 py-8 text-center">Cargando...</div>
      )}
      {tab === "flow" && project && project.status === "draft" && (
        <StartVideoForm
          projectId={slug}
          onStarted={() => {
            setTab("execution");
            fetchProject(slug).then(setProject);
          }}
        />
      )}
      {tab === "flow" && project && project.status !== "draft" && (
        <FlowDiagram project={project} />
      )}

      {/* ── Tab: Execution ── */}
      {tab === "execution" && (
        <div className="space-y-5">
          {/* Live pipeline */}
          <section>
            <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">
              Estado en tiempo real
            </h3>
            <PipelineView
              pipeline={pipeline}
              projectId={slug}
              onPluginsClick={() => router.push(`/project/${slug}/plugins`)}
            />
          </section>

          {/* Action buttons */}
          {(canReview || canPlugins || isCurated) && (
            <div className="flex gap-3">
              {canPlugins && (
                <Link href={`/project/${slug}/plugins`}>
                  <Button className="gap-2 bg-yellow-600 hover:bg-yellow-500">
                    Revisar plugins propuestos →
                  </Button>
                </Link>
              )}
              {canReview && (
                <Link href={`/project/${slug}/review`}>
                  <Button className="gap-2 bg-purple-600 hover:bg-purple-500">
                    <Play className="w-4 h-4" /> Revisar y aprobar video
                  </Button>
                </Link>
              )}
              {isCurated && (
                <Link href={`/project/${slug}/learnings`}>
                  <Button variant="outline" className="gap-2">
                    Ver aprendizajes del curator →
                  </Button>
                </Link>
              )}
            </div>
          )}

          {/* Two-column: outline + video */}
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
              {Object.entries(qaNotes).map(([num, notes]) => (
                <div key={num} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setExpanded(expanded === +num ? null : +num)}
                    className="w-full flex items-center justify-between px-4 py-2.5 text-sm hover:bg-zinc-800/60 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${
                        notes === "ok" ? "bg-green-400" : notes === "degraded" ? "bg-yellow-400" : "bg-blue-400"
                      }`} />
                      <span className="text-xs font-medium">Escena {num}</span>
                      <span className="text-xs text-zinc-500">
                        {notes === "ok" ? "Sin problemas" : notes === "degraded" ? "Degraded" : "Issues"}
                      </span>
                    </div>
                    {expanded === +num ? <ChevronDown className="w-3 h-3 text-zinc-500" /> : <ChevronRight className="w-3 h-3 text-zinc-500" />}
                  </button>
                  {expanded === +num && notes !== "ok" && (
                    <pre className="px-4 pb-3 text-[11px] text-zinc-400 whitespace-pre-wrap font-mono border-t border-zinc-800">
                      {notes}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Log console */}
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
    </div>
  );
}
