"use client";
import { useState } from "react";
import { CheckCircle, Loader2, XCircle, Clock, ChevronDown, ChevronRight, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Scene, SceneStatus } from "@/lib/api";

interface Props {
  scene: Scene;
  onApprove: (sceneNum: number) => Promise<void>;
  onRevise: (sceneNum: number, feedback: string) => Promise<void>;
}

function StatusBadge({ status }: { status: SceneStatus }) {
  const map: Record<SceneStatus, { label: string; className: string; Icon?: React.ElementType }> = {
    pending:         { label: "Pendiente",        className: "bg-zinc-800 text-zinc-400" },
    rendering:       { label: "Renderizando…",    className: "bg-blue-900/50 text-blue-300", Icon: Loader2 },
    awaiting_review: { label: "Listo para revisar", className: "bg-amber-900/50 text-amber-300", Icon: Clock },
    revising:        { label: "Revisando…",       className: "bg-purple-900/50 text-purple-300", Icon: Loader2 },
    approved:        { label: "Aprobado",         className: "bg-green-900/50 text-green-300", Icon: CheckCircle },
    failed:          { label: "Error",            className: "bg-red-900/50 text-red-300", Icon: XCircle },
  };
  const { label, className, Icon } = map[status] ?? map.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${className}`}>
      {Icon && <Icon className={`w-3 h-3 ${status === "rendering" || status === "revising" ? "animate-spin" : ""}`} />}
      {label}
    </span>
  );
}

export function SceneCard({ scene, onApprove, onRevise }: Props) {
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const previewUrl = scene.preview_url
    ? `http://localhost:8000${scene.preview_url}`
    : null;

  const isReviewable = scene.status === "awaiting_review";
  const isActive = scene.status === "rendering" || scene.status === "revising";

  async function handleApprove() {
    setBusy(true);
    try { await onApprove(scene.scene); } finally { setBusy(false); }
  }

  async function handleRevise() {
    if (!feedbackText.trim()) return;
    setBusy(true);
    try {
      await onRevise(scene.scene, feedbackText.trim());
      setFeedbackText("");
      setFeedbackOpen(false);
    } finally { setBusy(false); }
  }

  return (
    <div className={`flex flex-col rounded-xl border bg-zinc-900 overflow-hidden transition-all ${
      isActive ? "border-blue-700 animate-pulse-glow" :
      scene.status === "approved" ? "border-green-800" :
      scene.status === "awaiting_review" ? "border-amber-700" :
      scene.status === "failed" ? "border-red-800" :
      "border-zinc-800"
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800">
        <span className="text-sm font-semibold text-zinc-100">Escena {scene.scene}</span>
        <StatusBadge status={scene.status} />
      </div>

      {/* Video preview */}
      <div className="bg-black aspect-video flex items-center justify-center">
        {previewUrl ? (
          <video
            key={previewUrl}
            controls
            className="w-full h-full object-contain"
            src={previewUrl}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-zinc-600">
            {isActive
              ? <Loader2 className="w-6 h-6 animate-spin" />
              : <div className="w-6 h-6 rounded bg-zinc-800" />}
            <span className="text-xs">
              {isActive ? "Procesando…" : "Sin preview todavía"}
            </span>
          </div>
        )}
      </div>

      {/* Scene desc */}
      {scene.scene_desc && (
        <p className="px-4 py-2 text-xs text-zinc-500 line-clamp-2 border-b border-zinc-800/50">
          {scene.scene_desc}
        </p>
      )}

      {/* Actions */}
      {isReviewable && (
        <div className="p-3 space-y-2">
          <div className="flex gap-2">
            <Button
              size="sm"
              className="flex-1 gap-1.5 bg-green-700 hover:bg-green-600 text-xs"
              onClick={handleApprove}
              disabled={busy}
            >
              {busy && !feedbackOpen ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
              Aprobar
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="flex-1 gap-1.5 text-xs border-zinc-700"
              onClick={() => setFeedbackOpen((v) => !v)}
              disabled={busy}
            >
              <MessageSquare className="w-3 h-3" />
              Dar feedback
            </Button>
          </div>

          {feedbackOpen && (
            <div className="space-y-2">
              <textarea
                className="w-full rounded-lg bg-zinc-800 border border-zinc-700 text-xs text-zinc-200 placeholder-zinc-600 px-3 py-2 resize-none focus:outline-none focus:border-zinc-500"
                rows={3}
                placeholder="Describe qué quieres cambiar en esta escena…"
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
              />
              <div className="flex gap-2 justify-end">
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs text-zinc-500"
                  onClick={() => { setFeedbackOpen(false); setFeedbackText(""); }}
                >
                  Cancelar
                </Button>
                <Button
                  size="sm"
                  className="text-xs bg-purple-700 hover:bg-purple-600"
                  onClick={handleRevise}
                  disabled={busy || !feedbackText.trim()}
                >
                  {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                  Enviar feedback
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Feedback history */}
      {scene.feedback_history.length > 0 && (
        <div className="border-t border-zinc-800">
          <button
            className="w-full flex items-center justify-between px-4 py-2 text-xs text-zinc-500 hover:text-zinc-400 transition-colors"
            onClick={() => setHistoryOpen((v) => !v)}
          >
            <span>Historial de feedback ({scene.feedback_history.length})</span>
            {historyOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
          {historyOpen && (
            <ul className="px-4 pb-3 space-y-2">
              {scene.feedback_history.map((fb, i) => (
                <li key={i} className="text-[11px] text-zinc-400 bg-zinc-800/50 rounded-lg px-3 py-2">
                  <span className="text-zinc-600 font-mono mr-2">
                    {new Date(fb.ts).toLocaleTimeString()}
                  </span>
                  {fb.text}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
