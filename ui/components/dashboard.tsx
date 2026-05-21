"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchProjects, type Project } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Video, Clock } from "lucide-react";

const STATUS_COLOR: Record<string, string> = {
  created: "bg-zinc-700 text-zinc-200",
  running: "bg-blue-700 text-blue-100",
  awaiting_plugins: "bg-yellow-700 text-yellow-100",
  planning_done: "bg-blue-600 text-blue-100",
  awaiting_review: "bg-purple-700 text-purple-100",
  review_submitted: "bg-indigo-700 text-indigo-100",
  curated: "bg-green-700 text-green-100",
  error: "bg-red-700 text-red-100",
  env_failed: "bg-red-700 text-red-100",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLOR[status] ?? "bg-zinc-700 text-zinc-200";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProjects()
      .then(setProjects)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Mis videos</h2>
          <p className="text-zinc-400 text-sm mt-1">
            Cada video se crea con un pipeline de agentes IA especializados
          </p>
        </div>
        <Link href="/new">
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            Nuevo video
          </Button>
        </Link>
      </div>

      {loading && (
        <p className="text-zinc-500 text-sm">Cargando proyectos...</p>
      )}

      {!loading && projects.length === 0 && (
        <div className="text-center py-24 border border-dashed border-zinc-700 rounded-xl">
          <Video className="w-12 h-12 mx-auto text-zinc-600 mb-4" />
          <p className="text-zinc-400 mb-4">No hay videos todavía</p>
          <Link href="/new">
            <Button>Crear mi primer video</Button>
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((p) => (
          <Link key={p.id} href={`/project/${p.id}`}>
            <Card className="bg-zinc-900 border-zinc-800 hover:border-zinc-600 transition-colors cursor-pointer h-full">
              <CardHeader className="pb-2">
                <CardTitle className="text-base font-medium line-clamp-2 text-zinc-100">
                  {p.idea}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <StatusBadge status={p.status} />
                <div className="flex items-center gap-2 text-xs text-zinc-500">
                  <Clock className="w-3 h-3" />
                  {new Date(p.created_at).toLocaleString("es")}
                </div>
                <div className="flex gap-2 text-xs text-zinc-400 flex-wrap">
                  <span>{p.lang.toUpperCase()}</span>
                  <span>·</span>
                  <span>{p.audience}</span>
                  <span>·</span>
                  <span>{p.target_length}</span>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
