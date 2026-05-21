"use client";
import { useState } from "react";
import { startVideo } from "@/lib/api";
import { Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";

const AUDIENCES = ["general", "high school", "undergrad", "advanced"];
const LENGTHS   = ["30s", "60s", "2min", "5min+"];
const LANGS     = [{ code: "es", label: "Español" }, { code: "en", label: "English" }];

interface Props {
  projectId: string;
  onStarted: () => void;
}

export function StartVideoForm({ projectId, onStarted }: Props) {
  const [idea, setIdea]               = useState("");
  const [lang, setLang]               = useState("es");
  const [audience, setAudience]       = useState("general");
  const [targetLength, setTargetLength] = useState("60s");
  const [voiceProfile, setVoiceProfile] = useState("");
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) return;
    setLoading(true);
    setError("");
    try {
      await startVideo(projectId, {
        idea: idea.trim(),
        lang,
        audience,
        target_length: targetLength,
        voice_profile: voiceProfile || undefined,
      });
      onStarted();
    } catch (err) {
      setError(String(err));
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h3 className="text-sm font-semibold">Configurar video</h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            Define la idea y parámetros para lanzar el pipeline de agentes
          </p>
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

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
              Perfil de voz <span className="text-zinc-600 normal-case">(opcional)</span>
            </label>
            <input
              value={voiceProfile}
              onChange={(e) => setVoiceProfile(e.target.value)}
              placeholder="Ruta al audio de muestra (ej: voice/mi_voz.wav)"
              className="w-full rounded-lg bg-zinc-800 border border-zinc-700 px-4 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
            />
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading || !idea.trim()} className="w-full gap-2">
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Lanzando pipeline...</>
              : <><Play className="w-4 h-4" /> Lanzar pipeline</>}
          </Button>
        </form>
      </div>
    </div>
  );
}
