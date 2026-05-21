"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { submitReview, videoUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2, ThumbsUp, ThumbsDown } from "lucide-react";
import Link from "next/link";

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;

  const [approved, setApproved] = useState<boolean | null>(null);
  const [feedback, setFeedback] = useState("");
  const [whatWorked, setWhatWorked] = useState("");
  const [whatDidnt, setWhatDidnt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (approved === null) return;
    setSubmitting(true);
    await submitReview(slug, {
      approved,
      feedback,
      what_worked: whatWorked,
      what_didnt: whatDidnt,
    });
    router.push(approved ? `/project/${slug}/learnings` : `/project/${slug}`);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Link href={`/project/${slug}`} className="inline-flex items-center gap-2 text-zinc-400 hover:text-zinc-100 text-sm">
        <ArrowLeft className="w-4 h-4" /> Volver al proyecto
      </Link>

      <div>
        <h2 className="text-2xl font-bold">Revisión del video</h2>
        <p className="text-zinc-400 text-sm mt-1">
          Revisa el resultado y deja tu feedback. Si lo apruebas, un agente extraerá aprendizajes para mejorar el sistema.
        </p>
      </div>

      {/* Video player */}
      <div className="rounded-xl overflow-hidden border border-zinc-800 bg-black">
        <video controls className="w-full max-h-[480px]" src={videoUrl(slug)}>
          Tu navegador no soporta video HTML5.
        </video>
      </div>

      {/* Approval */}
      <div className="space-y-2">
        <label className="text-sm font-medium">¿Apruebas este video?</label>
        <div className="flex gap-3">
          <button
            onClick={() => setApproved(true)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors ${
              approved === true
                ? "bg-green-700 border-green-600 text-white"
                : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-green-700"
            }`}
          >
            <ThumbsUp className="w-4 h-4" /> Sí, aprobado
          </button>
          <button
            onClick={() => setApproved(false)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors ${
              approved === false
                ? "bg-red-800 border-red-700 text-white"
                : "bg-zinc-900 border-zinc-700 text-zinc-300 hover:border-red-800"
            }`}
          >
            <ThumbsDown className="w-4 h-4" /> Necesita cambios
          </button>
        </div>
      </div>

      {/* Feedback fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium text-green-400">¿Qué funcionó bien?</label>
          <textarea
            value={whatWorked}
            onChange={(e) => setWhatWorked(e.target.value)}
            rows={4}
            placeholder="Ej: La transición entre la escena 1 y 2 fue muy fluida..."
            className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-green-600 resize-none"
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium text-red-400">¿Qué mejorar?</label>
          <textarea
            value={whatDidnt}
            onChange={(e) => setWhatDidnt(e.target.value)}
            rows={4}
            placeholder="Ej: La fórmula de la escena 3 se solapaba con el título..."
            className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-red-600 resize-none"
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Comentarios adicionales</label>
        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={3}
          placeholder="Cualquier otra observación..."
          className="w-full rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
      </div>

      <Button
        onClick={handleSubmit}
        disabled={approved === null || submitting}
        size="lg"
        className="w-full gap-2"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        {approved === true ? "Aprobar y extraer aprendizajes" : approved === false ? "Enviar feedback (sin aprobar)" : "Selecciona una opción"}
      </Button>
    </div>
  );
}
