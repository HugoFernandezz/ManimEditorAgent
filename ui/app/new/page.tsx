"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createProject } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

const AUDIENCES = ["general", "high school", "undergrad", "advanced"];
const LENGTHS = ["30s", "60s", "2min", "5min+"];
const LANGS = [
  { code: "es", label: "Español" },
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
];

export default function NewProjectPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [idea, setIdea] = useState("");
  const [lang, setLang] = useState("es");
  const [audience, setAudience] = useState("general");
  const [targetLength, setTargetLength] = useState("60s");
  const [voiceProfile, setVoiceProfile] = useState("");
  const [exportLangs, setExportLangs] = useState<string[]>([]);

  const toggleExport = (code: string) => {
    setExportLangs((prev) =>
      prev.includes(code) ? prev.filter((l) => l !== code) : [...prev, code]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) return;
    setLoading(true);
    setError("");
    try {
      const proj = await createProject({
        idea: idea.trim(),
        lang,
        audience,
        target_length: targetLength,
        voice_profile: voiceProfile || undefined,
        export_langs: exportLangs,
      });
      router.push(`/project/${proj.id}`);
    } catch (err) {
      setError(String(err));
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <Link href="/" className="inline-flex items-center gap-2 text-zinc-400 hover:text-zinc-100 text-sm">
        <ArrowLeft className="w-4 h-4" /> Volver
      </Link>

      <div>
        <h2 className="text-2xl font-bold">Nuevo video Manim</h2>
        <p className="text-zinc-400 text-sm mt-1">
          Describe tu idea y el pipeline de agentes hará el resto
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Idea */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Idea del video *</label>
          <textarea
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
            placeholder="Ej: Explica intuitivamente qué es la derivada en un punto, para bachillerato"
            rows={4}
            required
            className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          {/* Idioma */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Idioma principal</label>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {LANGS.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>

          {/* Duración */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Duración objetivo</label>
            <select
              value={targetLength}
              onChange={(e) => setTargetLength(e.target.value)}
              className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {LENGTHS.map((l) => (
                <option key={l} value={l}>{l}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Audiencia */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Audiencia</label>
          <div className="flex flex-wrap gap-2">
            {AUDIENCES.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAudience(a)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  audience === a
                    ? "bg-blue-600 border-blue-600 text-white"
                    : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-zinc-500"
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        {/* Export langs */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Exportar también en</label>
          <div className="flex flex-wrap gap-2">
            {LANGS.filter((l) => l.code !== lang).map((l) => (
              <button
                key={l.code}
                type="button"
                onClick={() => toggleExport(l.code)}
                className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                  exportLangs.includes(l.code)
                    ? "bg-purple-700 border-purple-600 text-white"
                    : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-zinc-500"
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-zinc-500">Solo audio — el video visual se reutiliza</p>
        </div>

        {/* Voice profile */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Perfil de voz clonada <span className="text-zinc-500">(opcional)</span></label>
          <input
            value={voiceProfile}
            onChange={(e) => setVoiceProfile(e.target.value)}
            placeholder="Ruta al audio de muestra (ej: voice/mi_voz.wav)"
            className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-4 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-zinc-500">Déjalo vacío para usar narración silenciosa (stub)</p>
        </div>

        {error && (
          <div className="bg-red-900/40 border border-red-700 rounded-lg px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        <Button type="submit" disabled={loading || !idea.trim()} size="lg" className="w-full gap-2">
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Creando proyecto...
            </>
          ) : (
            "Lanzar pipeline →"
          )}
        </Button>
      </form>
    </div>
  );
}
