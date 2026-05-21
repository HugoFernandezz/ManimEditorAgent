"use client";
import { useState } from "react";
import { createProject } from "@/lib/api";
import { X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const AUDIENCES = ["general", "high school", "undergrad", "advanced"];
const LENGTHS   = ["30s", "60s", "2min", "5min+"];
const LANGS     = [{ code: "es", label: "Español" }, { code: "en", label: "English" }];

interface Props {
  onClose: () => void;
  onCreate: (projectId: string) => void;
}

export function NewProjectModal({ onClose, onCreate }: Props) {
  const [idea, setIdea]               = useState("");
  const [lang, setLang]               = useState("es");
  const [audience, setAudience]       = useState("general");
  const [targetLength, setTargetLength] = useState("60s");
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) return;
    setLoading(true);
    setError("");
    try {
      const proj = await createProject({ idea: idea.trim(), lang, audience, target_length: targetLength });
      onCreate(proj.id);
    } catch (err) {
      setError(String(err));
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Scrim */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div className="relative z-10 bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-lg mx-4 shadow-2xl animate-fade-in-up">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <h2 className="text-base font-semibold">Nuevo video</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Idea */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Idea del video *
            </label>
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="Ej: Explica intuitivamente qué es la derivada en un punto, para bachillerato"
              rows={3}
              required
              autoFocus
              className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition-colors"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Idioma */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Idioma</label>
              <select
                value={lang}
                onChange={(e) => setLang(e.target.value)}
                className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </div>
            {/* Duración */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Duración</label>
              <select
                value={targetLength}
                onChange={(e) => setTargetLength(e.target.value)}
                className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {LENGTHS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>

          {/* Audiencia */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Audiencia</label>
            <div className="flex flex-wrap gap-2">
              {AUDIENCES.map((a) => (
                <button
                  key={a} type="button" onClick={() => setAudience(a)}
                  className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${
                    audience === a
                      ? "bg-blue-600 border-blue-600 text-white"
                      : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-500"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading || !idea.trim()} className="w-full gap-2">
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> Creando...</> : "Lanzar pipeline →"}
          </Button>
        </form>
      </div>
    </div>
  );
}
