"use client";
import { useState } from "react";
import { createProject } from "@/lib/api";
import { X, Loader2, FolderPlus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  onClose: () => void;
  onCreate: (projectId: string) => void;
}

export function NewProjectModal({ onClose, onCreate }: Props) {
  const [name, setName]               = useState("");
  const [description, setDescription] = useState("");
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError("");
    try {
      const proj = await createProject({ name: name.trim(), description: description.trim() });
      onCreate(proj.id);
    } catch (err) {
      setError(String(err));
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-md mx-4 shadow-2xl animate-fade-in-up">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <FolderPlus className="w-4 h-4 text-zinc-400" />
            <h2 className="text-base font-semibold">Nuevo proyecto</h2>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Nombre del proyecto *
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej: Derivadas para bachillerato"
              required
              autoFocus
              className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Descripción <span className="text-zinc-600">(opcional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Para qué es este proyecto, notas iniciales..."
              rows={3}
              className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-2.5 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition-colors"
            />
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <p className="text-xs text-zinc-600">
            Podrás configurar y lanzar el video desde dentro del proyecto.
          </p>

          <Button type="submit" disabled={loading || !name.trim()} className="w-full gap-2">
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Creando...</>
              : "Crear proyecto →"}
          </Button>
        </form>
      </div>
    </div>
  );
}
