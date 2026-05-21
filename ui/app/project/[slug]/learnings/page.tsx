"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { fetchLearnings, applyPatch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Check, X, Loader2, BookOpen } from "lucide-react";
import Link from "next/link";

interface DiffBlock {
  file: string;
  hunk: string;
  applied: boolean;
}

function parseDiffBlocks(raw: string): DiffBlock[] {
  const blocks: DiffBlock[] = [];
  const sections = raw.split(/###\s+/);
  for (const section of sections) {
    if (!section.trim()) continue;
    const lines = section.split("\n");
    const file = lines[0].trim();
    const rest = lines.slice(1).join("\n");
    const hunkMatch = rest.match(/```diff\n([\s\S]*?)\n```/);
    if (hunkMatch) {
      blocks.push({ file, hunk: hunkMatch[1], applied: false });
    }
  }
  return blocks;
}

export default function LearningsPage() {
  const params = useParams();
  const slug = params.slug as string;

  const [notes, setNotes] = useState("");
  const [blocks, setBlocks] = useState<DiffBlock[]>([]);
  const [applying, setApplying] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLearnings(slug).then(({ notes, diff }) => {
      setNotes(notes);
      setBlocks(parseDiffBlocks(diff));
      setLoading(false);
    });
  }, [slug]);

  const handleApply = async (i: number, block: DiffBlock) => {
    setApplying((prev) => ({ ...prev, [i]: true }));
    await applyPatch(slug, block.file, block.hunk);
    setBlocks((prev) => prev.map((b, idx) => idx === i ? { ...b, applied: true } : b));
    setApplying((prev) => ({ ...prev, [i]: false }));
  };

  const handleReject = (i: number) => {
    setBlocks((prev) => prev.map((b, idx) => idx === i ? { ...b, applied: true } : b));
  };

  if (loading) return <div className="text-zinc-500 text-sm">Cargando aprendizajes...</div>;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <Link href={`/project/${slug}`} className="inline-flex items-center gap-2 text-zinc-400 hover:text-zinc-100 text-sm">
        <ArrowLeft className="w-4 h-4" /> Volver al proyecto
      </Link>

      <div>
        <h2 className="text-2xl font-bold">Aprendizajes del video</h2>
        <p className="text-zinc-400 text-sm mt-1">
          El agente curator extrajo lo más relevante. Revisa y acepta los cambios propuestos a la skill.
        </p>
      </div>

      {/* Notes */}
      {notes && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-2">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen className="w-4 h-4 text-zinc-400" />
            <h3 className="text-sm font-semibold">Resumen del curator</h3>
          </div>
          <pre className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">{notes}</pre>
        </div>
      )}

      {/* Diff blocks */}
      {blocks.length === 0 && !notes && (
        <p className="text-zinc-500 text-sm">No hay aprendizajes registrados todavía.</p>
      )}

      {blocks.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold">Cambios propuestos a la skill</h3>
          {blocks.map((block, i) => (
            <div
              key={i}
              className={`border rounded-xl overflow-hidden transition-opacity ${
                block.applied ? "opacity-50" : "border-zinc-700"
              }`}
            >
              <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800">
                <span className="text-xs font-mono text-zinc-300">{block.file}</span>
                {!block.applied ? (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 gap-1 text-red-400 border-red-900 hover:bg-red-950"
                      onClick={() => handleReject(i)}
                    >
                      <X className="w-3 h-3" /> Rechazar
                    </Button>
                    <Button
                      size="sm"
                      className="h-7 gap-1 bg-green-700 hover:bg-green-600"
                      onClick={() => handleApply(i, block)}
                      disabled={applying[i]}
                    >
                      {applying[i] ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                      Aplicar
                    </Button>
                  </div>
                ) : (
                  <span className="text-xs text-zinc-500">procesado</span>
                )}
              </div>
              <pre className="overflow-x-auto p-4 text-xs font-mono leading-5 bg-black">
                {block.hunk.split("\n").map((line, j) => (
                  <span
                    key={j}
                    className={`block ${
                      line.startsWith("+") ? "text-green-400 bg-green-950/30" :
                      line.startsWith("-") ? "text-red-400 bg-red-950/30" :
                      "text-zinc-400"
                    }`}
                  >
                    {line || " "}
                  </span>
                ))}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
