"use client";
import { useEffect, useState } from "react";
import {
  startVideo, fetchResumeOptions, resumePipeline,
  type ResumeOptions, type ResumeStep,
} from "@/lib/api";
import { Loader2, Play, FastForward, ChevronDown, ChevronRight, SkipForward, FileText, Layers, Film } from "lucide-react";
import { Button } from "@/components/ui/button";

const LENGTHS = ["30s", "60s", "2min", "5min+"];
const LANGS   = [{ code: "es", label: "Español" }, { code: "en", label: "English" }];
const FORMATS = [
  { id: "youtube", label: "YouTube", desc: "16:9 · narrativo",               subDesc: "Ritmo profundo, análisis detallado" },
  { id: "tiktok",  label: "TikTok",  desc: "9:16 · retención hiperactiva",   subDesc: "Gancho en 2 s, jump cuts, safe zones" },
] as const;
type VideoFormat = (typeof FORMATS)[number]["id"];

interface Defaults {
  idea?: string | null;
  lang?: string;
  format?: string;
  target_length?: string;
  voice_profile?: string | null;
}

interface Props {
  projectId: string;
  onStarted: () => void;
  defaults?: Defaults;
}

export function StartVideoForm({ projectId, onStarted, defaults }: Props) {
  const [idea, setIdea]               = useState(defaults?.idea ?? "");
  const [lang, setLang]               = useState(defaults?.lang ?? "es");
  const [fmt, setFmt]                 = useState<VideoFormat>((defaults?.format as VideoFormat) ?? "youtube");
  const [targetLength, setTargetLength] = useState(defaults?.target_length ?? "60s");
  const [voiceProfile, setVoiceProfile] = useState(defaults?.voice_profile ?? "");
  const [skipResearch, setSkipResearch] = useState(false);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [resumeOpts, setResumeOpts]     = useState<ResumeOptions | null>(null);
  const [resuming, setResuming]         = useState<ResumeStep | null>(null);

  // Load resume options when the advanced panel opens — and re-check on focus
  useEffect(() => {
    if (!advancedOpen) return;
    fetchResumeOptions(projectId).then(setResumeOpts).catch(() => setResumeOpts(null));
  }, [advancedOpen, projectId]);

  const handleResume = async (step: ResumeStep) => {
    if (resuming) return;
    if (!confirm(`Reanudar desde ${step}? Esto reutilizará los artefactos en disco y saltará las fases anteriores.`)) return;
    setResuming(step);
    setError("");
    try {
      await resumePipeline(projectId, step);
      onStarted();
    } catch (err) {
      setError(String(err));
      setResuming(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) return;
    setLoading(true);
    setError("");
    try {
      await startVideo(projectId, {
        idea: idea.trim(),
        lang,
        format: fmt,
        target_length: targetLength,
        voice_profile: voiceProfile || undefined,
        skip_research: skipResearch,
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
            <label className="text-xs font-medium text-zinc-400 uppercase tracking-wide">Formato</label>
            <div className="grid grid-cols-2 gap-2">
              {FORMATS.map(({ id, label, desc, subDesc }) => (
                <button
                  key={id} type="button" onClick={() => setFmt(id)}
                  className={`flex flex-col items-start gap-0.5 px-4 py-3 rounded-xl border text-left transition-colors ${
                    fmt === id
                      ? "bg-blue-600/20 border-blue-500 text-white"
                      : "bg-zinc-800 border-zinc-700 text-zinc-300 hover:border-zinc-500"
                  }`}
                >
                  <span className="text-sm font-semibold">{label}</span>
                  <span className={`text-[10px] font-medium ${fmt === id ? "text-blue-300" : "text-zinc-400"}`}>{desc}</span>
                  <span className={`text-[10px] leading-tight mt-0.5 ${fmt === id ? "text-blue-200/80" : "text-zinc-500"}`}>{subDesc}</span>
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

          {/* Skip-research toggle */}
          <button
            type="button"
            onClick={() => setSkipResearch((v) => !v)}
            aria-pressed={skipResearch}
            className={`w-full flex items-center justify-between gap-3 rounded-lg border px-4 py-3 text-left transition-colors ${
              skipResearch
                ? "bg-amber-950/30 border-amber-700/60"
                : "bg-zinc-800/60 border-zinc-700 hover:border-zinc-600"
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <FastForward className={`w-4 h-4 shrink-0 ${skipResearch ? "text-amber-400" : "text-zinc-400"}`} />
              <div className="min-w-0">
                <div className="text-xs font-medium text-zinc-100">
                  Saltar investigación de plugins
                </div>
                <div className="text-[11px] text-zinc-500 truncate">
                  Ir directo al Planner (sólo se instalará manim-voiceover)
                </div>
              </div>
            </div>
            <span
              className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                skipResearch ? "bg-amber-500" : "bg-zinc-700"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                  skipResearch ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </span>
          </button>

          {/* Opciones avanzadas: reanudar desde checkpoint */}
          <div className="border border-zinc-800 rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left bg-zinc-800/40 hover:bg-zinc-800/60 transition-colors"
            >
              <div className="flex items-center gap-2">
                {advancedOpen ? <ChevronDown className="w-3.5 h-3.5 text-zinc-400" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />}
                <span className="text-xs font-medium text-zinc-200">Opciones avanzadas</span>
                <span className="text-[10px] text-zinc-500">— reanudar desde un punto del pipeline</span>
              </div>
            </button>
            {advancedOpen && (
              <div className="px-4 py-3 space-y-2 bg-zinc-900/40">
                {!resumeOpts && (
                  <p className="text-[11px] text-zinc-500">Comprobando artefactos disponibles…</p>
                )}
                {resumeOpts && (
                  <>
                    <p className="text-[11px] text-zinc-500">
                      Si ya hay outline / beats / escenas en disco, puedes reanudar saltándote esas fases
                      en lugar de re-correr todo el pipeline.
                    </p>
                    <div className="text-[10px] text-zinc-600 grid grid-cols-3 gap-2 py-1.5">
                      <span className="flex items-center gap-1">
                        <FileText className="w-3 h-3" /> outline: {resumeOpts.artifacts.outline ? "sí" : "no"}
                      </span>
                      <span className="flex items-center gap-1">
                        <Layers className="w-3 h-3" /> beats: {resumeOpts.artifacts.beats_count}
                      </span>
                      <span className="flex items-center gap-1">
                        <Film className="w-3 h-3" /> escenas: {resumeOpts.artifacts.scenes_count}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {(["planner", "beats", "scenes"] as const).map((step) => {
                        const info = resumeOpts[step];
                        const disabled = !info.available || resuming !== null;
                        const isLoading = resuming === step;
                        return (
                          <button
                            key={step}
                            type="button"
                            onClick={() => handleResume(step)}
                            disabled={disabled}
                            className={`w-full flex items-center justify-between gap-3 rounded-md px-3 py-2 text-left border transition-colors ${
                              info.available
                                ? "bg-zinc-800/40 border-zinc-700 hover:border-blue-500/60 hover:bg-zinc-800/80"
                                : "bg-zinc-900/40 border-zinc-800 opacity-50 cursor-not-allowed"
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              {isLoading
                                ? <Loader2 className="w-3.5 h-3.5 shrink-0 animate-spin text-blue-400" />
                                : <SkipForward className={`w-3.5 h-3.5 shrink-0 ${info.available ? "text-blue-400" : "text-zinc-600"}`} />}
                              <div className="min-w-0">
                                <div className="text-xs font-medium text-zinc-100">{info.label}</div>
                                <div className="text-[10px] text-zinc-500 truncate">{info.detail}</div>
                              </div>
                            </div>
                            {info.skips.length > 0 && info.available && (
                              <span className="text-[9px] uppercase tracking-wide text-amber-400/80 shrink-0">
                                salta: {info.skips.join(", ")}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 rounded-lg px-4 py-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading || !idea.trim() || resuming !== null} className="w-full gap-2">
            {loading
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Lanzando pipeline...</>
              : <><Play className="w-4 h-4" /> {skipResearch ? "Lanzar (sin Researcher)" : "Lanzar pipeline"}</>}
          </Button>
        </form>
      </div>
    </div>
  );
}
