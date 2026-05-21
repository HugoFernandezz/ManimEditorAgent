"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { fetchProjects, type Project } from "@/lib/api";
import { NewProjectModal } from "@/components/new-project-modal";
import {
  Plus, ChevronLeft, ChevronRight, Video,
  Clock, CheckCircle, AlertCircle, Loader2, XCircle,
} from "lucide-react";

const STATUS_DOT: Record<string, string> = {
  created:          "bg-zinc-500",
  running:          "bg-blue-500 animate-pulse",
  awaiting_plugins: "bg-yellow-500",
  planning_done:    "bg-blue-400",
  awaiting_review:  "bg-purple-500",
  review_submitted: "bg-indigo-500",
  curated:          "bg-green-500",
  error:            "bg-red-500",
  env_failed:       "bg-red-500",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [showNew, setShowNew] = useState(false);

  const loadProjects = () => fetchProjects().then(setProjects);

  useEffect(() => {
    loadProjects();
    const interval = setInterval(loadProjects, 8000);
    return () => clearInterval(interval);
  }, []);

  const activeSlug = pathname.startsWith("/project/")
    ? pathname.split("/")[2]
    : null;

  return (
    <div className="flex h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* ── Sidebar ── */}
      <aside
        className={`flex flex-col border-r border-zinc-800 flex-shrink-0 ${
          collapsed ? "sidebar-collapsed" : "sidebar-expanded"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-4 border-b border-zinc-800 min-h-[57px]">
          {!collapsed && (
            <span className="text-sm font-semibold text-zinc-100 truncate">
              🎬 Manim Agent
            </span>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors flex-shrink-0"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* New project button */}
        <div className="p-2 border-b border-zinc-800">
          <button
            onClick={() => setShowNew(true)}
            className={`flex items-center gap-2 w-full rounded-lg px-2.5 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white transition-colors ${
              collapsed ? "justify-center" : ""
            }`}
          >
            <Plus className="w-4 h-4 flex-shrink-0" />
            {!collapsed && <span>Nuevo video</span>}
          </button>
        </div>

        {/* Project list */}
        <nav className="flex-1 overflow-y-auto py-2 space-y-0.5 px-1.5">
          {projects.length === 0 && !collapsed && (
            <p className="text-xs text-zinc-600 text-center py-6 px-2">
              No hay proyectos todavía
            </p>
          )}
          {projects.map((p) => {
            const isActive = p.id === activeSlug;
            return (
              <button
                key={p.id}
                onClick={() => router.push(`/project/${p.id}`)}
                title={p.idea ?? p.name}
                className={`flex items-center gap-2.5 w-full rounded-lg px-2 py-2 text-left transition-colors ${
                  isActive
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                } ${collapsed ? "justify-center" : ""}`}
              >
                <div
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    STATUS_DOT[p.status] ?? "bg-zinc-600"
                  }`}
                />
                {!collapsed && (
                  <span className="text-xs truncate flex-1">{p.name || (p.idea ?? p.id)}</span>
                )}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center gap-3 px-6 py-4 border-b border-zinc-800 flex-shrink-0">
          <Video className="w-5 h-5 text-zinc-500" />
          <span className="text-sm font-semibold text-zinc-300">
            {activeSlug
              ? (() => { const p = projects.find(x => x.id === activeSlug); return p?.name || p?.idea || activeSlug; })()
              : "Selecciona un proyecto"}
          </span>
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>

      {showNew && (
        <NewProjectModal
          onClose={() => setShowNew(false)}
          onCreate={(id) => {
            setShowNew(false);
            loadProjects();
            router.push(`/project/${id}`);
          }}
        />
      )}
    </div>
  );
}
