"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { fetchProject, createWebSocket, videoUrl, frameUrl, type Project, type PipelineEvent } from "@/lib/api";
import { ArrowLeft, CheckCircle, XCircle, AlertCircle, Loader2, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

type Step = {
  id: string;
  label: string;
  status: "pending" | "running" | "ok" | "error" | "degraded";
};

const PIPELINE_STEPS: Step[] = [
  { id: "env", label: "Entorno", status: "pending" },
  { id: "researcher", label: "Investigación de plugins", status: "pending" },
  { id: "planner", label: "Planificación", status: "pending" },
  { id: "scenes", label: "Escenas", status: "pending" },
  { id: "narrator", label: "Narración", status: "pending" },
  { id: "editor", label: "Edición final", status: "pending" },
];

function StepIcon({ status }: { status: Step["status"] }) {
  if (status === "running") return <Loader2 className="w-4 h-4 animate-spin text-blue-400" />;
  if (status === "ok") return <CheckCircle className="w-4 h-4 text-green-400" />;
  if (status === "error") return <XCircle className="w-4 h-4 text-red-400" />;
  if (status === "degraded") return <AlertCircle className="w-4 h-4 text-yellow-400" />;
  return <div className="w-4 h-4 rounded-full border border-zinc-600" />;
}

export default function ProjectPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [project, setProject] = useState<Project | null>(null);
  const [steps, setSteps] = useState<Step[]>(PIPELINE_STEPS.map(s => ({ ...s })));
  const [logs, setLogs] = useState<string[]>([]);
  const [outline, setOutline] = useState("");
  const [sceneQA, setSceneQA] = useState<Record<number, string>>({});
  const [expandedScene, setExpandedScene] = useState<number | null>(null);
  const logsRef = useRef<HTMLDivElement>(null);

  const setStep = (id: string, status: Step["status"]) => {
    setSteps((prev) => prev.map((s) => s.id === id ? { ...s, status } : s));
  };

  const addLog = (msg: string) => {
    setLogs((prev) => [...prev.slice(-199), msg]);
  };

  useEffect(() => {
    fetchProject(slug).then(setProject);
    const ws = createWebSocket(slug, (event: PipelineEvent) => {
      handleEvent(event);
    });
    return () => ws.close();
  }, [slug]);

  useEffect(() => {
    if (logsRef.current) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs]);

  function handleEvent(e: PipelineEvent) {
    const { kind, payload } = e;
    addLog(`[${kind}] ${JSON.stringify(payload).slice(0, 120)}`);

    if (kind === "env_check_ok") setStep("env", "ok");
    if (kind === "env_check_failed") setStep("env", "error");
    if (kind === "agent_started") {
      const agent = payload.agent as string;
      if (agent === "researcher") setStep("researcher", "running");
      if (agent === "planner") setStep("planner", "running");
      if (agent === "narrator") setStep("narrator", "running");
      if (agent === "editor") setStep("editor", "running");
      if (agent === "coder" || agent === "visual_qa") setStep("scenes", "running");
    }
    if (kind === "plugins_proposed") setStep("researcher", "ok");
    if (kind === "outline_ready") {
      setStep("planner", "ok");
      setOutline((payload.outline as string) ?? "");
    }
    if (kind === "qa_ok") setSceneQA((prev) => ({ ...prev, [payload.scene as number]: "ok" }));
    if (kind === "qa_issue") setSceneQA((prev) => ({ ...prev, [payload.scene as number]: (payload.notes as string) ?? "" }));
    if (kind === "qa_degraded") setSceneQA((prev) => ({ ...prev, [payload.scene as number]: "degraded" }));
    if (kind === "narration_ready") setStep("narrator", "ok");
    if (kind === "edit_done") {
      setStep("editor", "ok");
      fetchProject(slug).then(setProject);
    }
    if (kind === "error") {
      setSteps((prev) => prev.map((s) => s.status === "running" ? { ...s, status: "error" } : s));
    }
  }

  const canReview = project?.status === "awaiting_review";
  const canPlugins = project?.status === "awaiting_plugins";

  return (
    <div className="space-y-6">
      <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-zinc-100 text-sm">
        <ArrowLeft className="w-4 h-4" /> Volver
      </Link>

      {project && (
        <div>
          <h2 className="text-xl font-bold line-clamp-2">{project.idea}</h2>
          <p className="text-sm text-zinc-400 mt-1">{project.id} · {project.lang.toUpperCase()} · {project.target_length}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stepper */}
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide mb-3">Pipeline</h3>
          {steps.map((step, i) => (
            <div key={step.id} className="flex items-center gap-3 py-2">
              <StepIcon status={step.status} />
              <span className={`text-sm ${step.status === "pending" ? "text-zinc-500" : "text-zinc-100"}`}>
                {step.label}
              </span>
            </div>
          ))}

          <div className="pt-4 space-y-2">
            {canPlugins && (
              <Link href={`/project/${slug}/plugins`}>
                <Button size="sm" className="w-full bg-yellow-600 hover:bg-yellow-700">
                  Revisar plugins →
                </Button>
              </Link>
            )}
            {canReview && (
              <Link href={`/project/${slug}/review`}>
                <Button size="sm" className="w-full bg-purple-600 hover:bg-purple-700">
                  Revisar video →
                </Button>
              </Link>
            )}
            {project?.status === "curated" && (
              <Link href={`/project/${slug}/learnings`}>
                <Button size="sm" variant="outline" className="w-full">
                  Ver aprendizajes →
                </Button>
              </Link>
            )}
          </div>
        </div>

        {/* Main content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Video preview */}
          {project?.final_video && (
            <div className="rounded-xl overflow-hidden border border-zinc-800">
              <video controls className="w-full" src={videoUrl(slug)}>
                Tu navegador no soporta video HTML5.
              </video>
            </div>
          )}

          {/* Outline */}
          {outline && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
              <h4 className="text-sm font-semibold mb-2">Outline del video</h4>
              <pre className="text-xs text-zinc-300 whitespace-pre-wrap font-mono leading-relaxed">
                {outline}
              </pre>
            </div>
          )}

          {/* Scene QA */}
          {Object.keys(sceneQA).length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">QA por escena</h4>
              {Object.entries(sceneQA).map(([num, notes]) => (
                <div key={num} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setExpandedScene(expandedScene === +num ? null : +num)}
                    className="w-full flex items-center justify-between px-4 py-2 text-sm hover:bg-zinc-800 transition-colors"
                  >
                    <span>Escena {num} — {notes === "ok" ? "✓ OK" : notes === "degraded" ? "⚠ Degraded" : "Issues"}</span>
                    {expandedScene === +num ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </button>
                  {expandedScene === +num && notes !== "ok" && (
                    <pre className="px-4 pb-3 text-xs text-zinc-400 whitespace-pre-wrap font-mono">
                      {notes}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Log console */}
          <div className="bg-black border border-zinc-800 rounded-xl">
            <div className="px-4 py-2 border-b border-zinc-800 text-xs text-zinc-500 font-mono">Pipeline logs</div>
            <div
              ref={logsRef}
              className="h-48 overflow-y-auto p-4 space-y-1 font-mono text-xs"
            >
              {logs.length === 0 && <span className="text-zinc-600">Esperando eventos...</span>}
              {logs.map((l, i) => (
                <div key={i} className="text-zinc-400">{l}</div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
