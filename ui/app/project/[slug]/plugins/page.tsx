"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { fetchProject, confirmPlugins, type Plugin } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, ExternalLink, Loader2, Package } from "lucide-react";
import Link from "next/link";

export default function PluginsPage() {
  const params = useParams();
  const router = useRouter();
  const slug = params.slug as string;

  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    fetchProject(slug).then((p) => {
      setPlugins(p.plugins_proposal ?? []);
      setLoading(false);
    });
  }, [slug]);

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const handleConfirm = async () => {
    setConfirming(true);
    await confirmPlugins(slug, Array.from(selected));
    router.push(`/project/${slug}`);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Link href={`/project/${slug}`} className="inline-flex items-center gap-2 text-zinc-400 hover:text-zinc-100 text-sm">
        <ArrowLeft className="w-4 h-4" /> Volver al proyecto
      </Link>

      <div>
        <h2 className="text-2xl font-bold">Plugins propuestos</h2>
        <p className="text-zinc-400 text-sm mt-1">
          El agente de investigación encontró estos plugins relevantes para tu video. Selecciona cuáles instalar.
        </p>
      </div>

      {loading && <p className="text-zinc-500 text-sm">Cargando propuestas...</p>}

      {!loading && plugins.length === 0 && (
        <div className="text-center py-16 border border-dashed border-zinc-700 rounded-xl">
          <Package className="w-10 h-10 mx-auto text-zinc-600 mb-3" />
          <p className="text-zinc-400 mb-2">No se encontraron plugins relevantes</p>
          <Button onClick={handleConfirm} disabled={confirming}>
            {confirming ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
            Continuar sin plugins
          </Button>
        </div>
      )}

      {!loading && plugins.length > 0 && (
        <div className="space-y-3">
          {plugins.map((p) => (
            <div
              key={p.name}
              onClick={() => toggle(p.name)}
              className={`border rounded-xl p-4 cursor-pointer transition-colors ${
                selected.has(p.name)
                  ? "border-blue-600 bg-blue-950/30"
                  : "border-zinc-800 bg-zinc-900 hover:border-zinc-600"
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`mt-0.5 w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
                  selected.has(p.name) ? "border-blue-500 bg-blue-500" : "border-zinc-600"
                }`}>
                  {selected.has(p.name) && <span className="text-white text-xs">✓</span>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm font-medium text-blue-300">{p.name}</span>
                    {p.repo && (
                      <a
                        href={p.repo}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-zinc-500 hover:text-zinc-300"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                  <p className="text-sm text-zinc-300 mt-1">{p.description}</p>
                  <p className="text-xs text-zinc-500 mt-1 italic">{p.relevance}</p>
                </div>
              </div>
            </div>
          ))}

          <div className="flex gap-3 pt-4">
            <Button
              onClick={() => setSelected(new Set(plugins.map(p => p.name)))}
              variant="outline"
              size="sm"
            >
              Seleccionar todos
            </Button>
            <Button
              onClick={() => setSelected(new Set())}
              variant="outline"
              size="sm"
            >
              Deseleccionar todos
            </Button>
            <Button onClick={handleConfirm} disabled={confirming} className="ml-auto gap-2">
              {confirming && <Loader2 className="w-4 h-4 animate-spin" />}
              Instalar seleccionados y continuar ({selected.size})
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
