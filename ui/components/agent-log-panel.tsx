"use client";
import { useEffect, useRef } from "react";
import { X, FileText, MessageSquare, CheckCircle, XCircle, Hash } from "lucide-react";
import type { StreamLine, AgentLogs } from "@/lib/pipeline-reducer";

interface Props {
  agentKey: string;        // e.g. "coder" or "coder:1"
  agentLabel: string;
  logs: AgentLogs;
  onClose: () => void;
}

function LineIcon({ line }: { line: StreamLine }) {
  if (line.line_type === "tool_use") {
    if (line.tool_name === "Read")  return <FileText className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 mt-0.5" />;
    if (line.tool_name === "Grep")  return <Hash className="w-3.5 h-3.5 text-purple-400 flex-shrink-0 mt-0.5" />;
    if (line.tool_name === "Glob")  return <Hash className="w-3.5 h-3.5 text-purple-400 flex-shrink-0 mt-0.5" />;
    if (line.tool_name === "Write") return <FileText className="w-3.5 h-3.5 text-yellow-400 flex-shrink-0 mt-0.5" />;
    return <FileText className="w-3.5 h-3.5 text-zinc-400 flex-shrink-0 mt-0.5" />;
  }
  if (line.line_type === "text")   return <MessageSquare className="w-3.5 h-3.5 text-zinc-400 flex-shrink-0 mt-0.5" />;
  if (line.line_type === "result") return <CheckCircle className="w-3.5 h-3.5 text-green-400 flex-shrink-0 mt-0.5" />;
  if (line.line_type === "error")  return <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />;
  return null;
}

function lineColor(line: StreamLine): string {
  if (line.line_type === "tool_use") return "text-zinc-200";
  if (line.line_type === "result")   return "text-green-300";
  if (line.line_type === "error")    return "text-red-300";
  return "text-zinc-400";
}

function toolLabel(line: StreamLine): string {
  if (!line.tool_name) return "";
  return `${line.tool_name} → `;
}

export function AgentLogPanel({ agentKey, agentLabel, logs, onClose }: Props) {
  const lines: StreamLine[] = logs[agentKey] ?? [];
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines.length]);

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex justify-end"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Panel */}
      <div className="w-full max-w-md h-full bg-zinc-950 border-l border-zinc-800 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 flex-shrink-0">
          <div>
            <p className="text-sm font-semibold text-zinc-100">{agentLabel}</p>
            <p className="text-[11px] text-zinc-500 mt-0.5">Actividad del agente</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Log lines */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-xs">
          {lines.length === 0 ? (
            <p className="text-zinc-600 italic text-center py-8">
              Sin actividad todavía.<br />
              Las líneas aparecen en tiempo real cuando el agente trabaje.
            </p>
          ) : (
            lines.map((line, i) => (
              <div key={i} className="flex items-start gap-2">
                <LineIcon line={line} />
                <span className={lineColor(line)}>
                  {line.line_type === "tool_use" && (
                    <span className="text-zinc-500">{toolLabel(line)}</span>
                  )}
                  {line.summary}
                </span>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-zinc-800 flex-shrink-0">
          <p className="text-[10px] text-zinc-600">
            {lines.length} líneas · Las herramientas Read/Grep/Glob se muestran en azul
          </p>
        </div>
      </div>
    </div>
  );
}
