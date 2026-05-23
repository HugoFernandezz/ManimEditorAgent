"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  fetchScenes, fetchProject, approveScene, reviseScene, finalizeProject,
  type Scene,
} from "@/lib/api";
import { SceneCard } from "@/components/scene-card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, CheckCircle, Loader2 } from "lucide-react";

const POLL_INTERVAL_MS = 4000;

function allApproved(scenes: Scene[]): boolean {
  return scenes.length > 0 && scenes.every((s) => s.status === "approved");
}

function hasActiveScenes(scenes: Scene[]): boolean {
  return scenes.some((s) => s.status === "rendering" || s.status === "revising");
}

export default function ScenesPage() {
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;

  const [scenes, setScenes] = useState<Scene[]>([]);
  const [loading, setLoading] = useState(true);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function applyScenes(data: Scene[]) {
    setScenes(data);
    setError(null);
    setLoading(false);
  }

  // Initial load
  useEffect(() => {
    let alive = true;
    fetchScenes(slug)
      .then((data) => { if (alive) applyScenes(data); })
      .catch((e) => { if (alive) { setError(e instanceof Error ? e.message : "Error al cargar"); setLoading(false); } });
    return () => { alive = false; };
  }, [slug]);

  // Polling while active scenes exist
  useEffect(() => {
    if (!hasActiveScenes(scenes)) return;
    pollRef.current = setTimeout(() => {
      fetchScenes(slug)
        .then((data) => applyScenes(data))
        .catch((e) => setError(e instanceof Error ? e.message : "Error al cargar"));
    }, POLL_INTERVAL_MS);
    return () => { if (pollRef.current) clearTimeout(pollRef.current); };
  }, [scenes, slug]);

  const handleApprove = (sceneNum: number) =>
    approveScene(slug, sceneNum).then(() =>
      fetchScenes(slug).then(applyScenes)
    );

  const handleRevise = (sceneNum: number, feedback: string) =>
    reviseScene(slug, sceneNum, feedback).then(() =>
      fetchScenes(slug).then(applyScenes)
    );

  const handleFinalize = () => {
    setFinalizing(true);
    finalizeProject(slug)
      .then(() => router.push(`/project/${slug}`))
      .catch((e) => { setError(e instanceof Error ? e.message : "Error al finalizar"); setFinalizing(false); });
  };

  const approved = scenes.filter((s) => s.status === "approved").length;
  const total = scenes.length;
  const canFinalize = allApproved(scenes);

  // Sync: if project status changed to scenes_approved or beyond, redirect
  useEffect(() => {
    if (!canFinalize) return;
    fetchProject(slug).then((p) => {
      if (p.status === "awaiting_review" || p.status === "curated") {
        router.push(`/project/${slug}`);
      }
    });
  }, [canFinalize, slug, router]);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Link
            href={`/project/${slug}`}
            className="inline-flex items-center gap-1.5 text-zinc-400 hover:text-zinc-100 text-sm transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Volver al proyecto
          </Link>
        </div>
        <div className="flex items-center gap-4">
          {total > 0 && (
            <span className="text-sm text-zinc-400">
              <span className={`font-semibold ${canFinalize ? "text-green-400" : "text-zinc-100"}`}>
                {approved}
              </span>
              <span className="text-zinc-600"> / {total} aprobadas</span>
            </span>
          )}
          <Button
            onClick={handleFinalize}
            disabled={!canFinalize || finalizing}
            className="gap-2 bg-teal-700 hover:bg-teal-600 disabled:opacity-40"
          >
            {finalizing
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <CheckCircle className="w-4 h-4" />}
            Render final
          </Button>
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-bold">Revisión de escenas</h2>
        <p className="text-zinc-400 text-sm mt-1">
          Aprueba cada escena o da feedback para regenerarla. El render final se desbloquea cuando todas estén aprobadas.
        </p>
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-600 transition-all duration-500"
            style={{ width: `${(approved / total) * 100}%` }}
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/30 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-2 text-zinc-500 py-8 justify-center">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Cargando escenas…</span>
        </div>
      )}

      {/* Scenes grid */}
      {!loading && scenes.length === 0 && !error && (
        <div className="text-center py-16 border border-dashed border-zinc-700 rounded-xl">
          <p className="text-zinc-500 text-sm">
            Todavía no hay escenas disponibles. El pipeline está procesando.
          </p>
        </div>
      )}

      {!loading && scenes.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {scenes.map((scene) => (
            <SceneCard
              key={scene.scene}
              scene={scene}
              onApprove={handleApprove}
              onRevise={handleRevise}
            />
          ))}
        </div>
      )}

      {/* All approved CTA */}
      {canFinalize && (
        <div className="flex flex-col items-center gap-3 py-6 border border-green-800 bg-green-950/20 rounded-xl">
          <CheckCircle className="w-10 h-10 text-green-400" />
          <p className="text-green-300 font-semibold">¡Todas las escenas aprobadas!</p>
          <p className="text-zinc-400 text-sm">Pulsa &quot;Render final&quot; para generar el video completo en alta calidad.</p>
          <Button
            onClick={handleFinalize}
            disabled={finalizing}
            className="gap-2 bg-teal-700 hover:bg-teal-600 mt-1"
          >
            {finalizing ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            Render final
          </Button>
        </div>
      )}
    </div>
  );
}
