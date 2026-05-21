"use client";
import { useEffect, useState } from "react";
import { fetchSkillFile, saveSkillFile, fetchSkillFiles } from "@/lib/api";
import { X, Save, Loader2, FileText, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  agentName: string;
  defaultFiles: string[];
  onClose: () => void;
}

export function SkillEditor({ agentName, defaultFiles, onClose }: Props) {
  const [allFiles, setAllFiles]     = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState(defaultFiles[0] ?? "SKILL.md");
  const [content, setContent]       = useState("");
  const [loading, setLoading]       = useState(true);
  const [saving, setSaving]         = useState(false);
  const [saved, setSaved]           = useState(false);
  const [error, setError]           = useState("");

  useEffect(() => {
    fetchSkillFiles().then(setAllFiles);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError("");
    fetchSkillFile(activeFile)
      .then((d) => { setContent(d.content); setLoading(false); })
      .catch(() => { setError("No se pudo cargar el archivo."); setLoading(false); });
  }, [activeFile]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveSkillFile(activeFile, content);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError("Error al guardar.");
    } finally {
      setSaving(false);
    }
  };

  const relevantFiles = allFiles.filter((f) => defaultFiles.includes(f));
  const otherFiles    = allFiles.filter((f) => !defaultFiles.includes(f));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-4xl mx-4 h-[80vh] flex flex-col shadow-2xl animate-fade-in-up">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-zinc-800 flex-shrink-0">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-semibold">
              Skill Editor
            </span>
            <span className="text-xs text-zinc-500 font-mono bg-zinc-800 px-2 py-0.5 rounded">
              {agentName}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || loading}
              className={`gap-1.5 h-7 text-xs transition-colors ${
                saved ? "bg-green-600 hover:bg-green-600" : ""
              }`}
            >
              {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
              {saved ? "¡Guardado!" : "Guardar"}
            </Button>
            <button onClick={onClose} className="text-zinc-400 hover:text-zinc-100 transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* File tree */}
          <div className="w-52 border-r border-zinc-800 flex-shrink-0 overflow-y-auto py-2">
            {relevantFiles.length > 0 && (
              <div className="px-3 py-1">
                <p className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-1">
                  Archivos del agente
                </p>
                {relevantFiles.map((f) => (
                  <button
                    key={f}
                    onClick={() => setActiveFile(f)}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs font-mono truncate transition-colors ${
                      activeFile === f
                        ? "bg-blue-600/20 text-blue-300 border-l-2 border-blue-500 pl-1.5"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
                    }`}
                  >
                    {f.split("/").pop()}
                  </button>
                ))}
              </div>
            )}
            {otherFiles.length > 0 && (
              <div className="px-3 py-1 mt-2">
                <p className="text-xs font-medium text-zinc-600 uppercase tracking-wide mb-1">
                  Otros archivos
                </p>
                {otherFiles.map((f) => (
                  <button
                    key={f}
                    onClick={() => setActiveFile(f)}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs font-mono truncate transition-colors ${
                      activeFile === f
                        ? "bg-blue-600/20 text-blue-300 border-l-2 border-blue-500 pl-1.5"
                        : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Editor */}
          <div className="flex-1 flex flex-col min-w-0">
            <div className="px-4 py-2 border-b border-zinc-800 flex-shrink-0">
              <span className="text-xs font-mono text-zinc-400">{activeFile}</span>
            </div>
            {loading ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 className="w-5 h-5 animate-spin text-zinc-500" />
              </div>
            ) : error ? (
              <div className="flex-1 flex items-center justify-center">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            ) : (
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                spellCheck={false}
                className="flex-1 w-full bg-transparent px-4 py-3 text-xs font-mono text-zinc-200 leading-relaxed resize-none focus:outline-none"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
