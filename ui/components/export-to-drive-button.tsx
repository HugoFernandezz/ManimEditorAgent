"use client";
import { useState, useCallback } from "react";
import { Upload, ExternalLink, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient: (config: {
            client_id: string;
            scope: string;
            callback: (response: { access_token?: string; error?: string }) => void;
          }) => { requestAccessToken: () => void };
        };
      };
    };
  }
}

type ExportState = "idle" | "authorizing" | "fetching" | "uploading" | "success" | "error";

const STATE_LABEL: Record<ExportState, string> = {
  idle:        "Exportar a Drive",
  authorizing: "Autorizando...",
  fetching:    "Descargando video...",
  uploading:   "Subiendo a Drive...",
  error:       "Reintentar",
  success:     "",
};

function loadGsiScript(): Promise<void> {
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[src*="accounts.google.com/gsi/client"]');
    if (existing) {
      existing.addEventListener("load", () => resolve());
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("No se pudo cargar la librería de Google."));
    document.head.appendChild(script);
  });
}

async function uploadToDrive(token: string, blob: Blob, filename: string): Promise<string> {
  const boundary = "ManimDriveBoundary";
  const enc = new TextEncoder();

  const part1 = enc.encode(
    `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n` +
    JSON.stringify({ name: filename, mimeType: "video/mp4" }) +
    `\r\n--${boundary}\r\nContent-Type: video/mp4\r\n\r\n`
  );
  const part3 = enc.encode(`\r\n--${boundary}--`);
  const videoBytes = new Uint8Array(await blob.arrayBuffer());

  const body = new Uint8Array(part1.byteLength + videoBytes.byteLength + part3.byteLength);
  body.set(part1, 0);
  body.set(videoBytes, part1.byteLength);
  body.set(part3, part1.byteLength + videoBytes.byteLength);

  const res = await fetch(
    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": `multipart/related; boundary=${boundary}`,
      },
      body,
    }
  );
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Drive API: ${res.status} — ${text}`);
  }
  const data = await res.json();
  return data.webViewLink ?? `https://drive.google.com/file/d/${data.id}/view`;
}

interface Props {
  videoSrc: string;
  filename?: string;
}

export function ExportToDriveButton({ videoSrc, filename = "video.mp4" }: Props) {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const [state, setState] = useState<ExportState>("idle");
  const [driveUrl, setDriveUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExport = useCallback(async () => {
    if (!clientId) {
      setError("Falta NEXT_PUBLIC_GOOGLE_CLIENT_ID en .env.local");
      setState("error");
      return;
    }
    setState("authorizing");
    setError(null);
    try {
      await loadGsiScript();

      const token = await new Promise<string>((resolve, reject) => {
        const client = window.google!.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: "https://www.googleapis.com/auth/drive.file",
          callback: (resp) => {
            if (resp.error) reject(new Error(resp.error));
            else resolve(resp.access_token!);
          },
        });
        client.requestAccessToken();
      });

      setState("fetching");
      const videoRes = await fetch(videoSrc);
      if (!videoRes.ok) throw new Error("No se pudo obtener el video del servidor local.");
      const blob = await videoRes.blob();

      setState("uploading");
      const url = await uploadToDrive(token, blob, filename);
      setDriveUrl(url);
      setState("success");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido.");
      setState("error");
    }
  }, [clientId, videoSrc, filename]);

  if (state === "success" && driveUrl) {
    return (
      <a
        href={driveUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-green-700 hover:bg-green-600 text-white rounded-lg transition-colors"
      >
        <ExternalLink className="w-4 h-4" />
        Ver en Drive
      </a>
    );
  }

  const busy = state !== "idle" && state !== "error";

  return (
    <div className="flex items-center gap-3">
      <Button
        onClick={handleExport}
        disabled={busy}
        className="flex items-center gap-2 bg-zinc-700 hover:bg-zinc-600 text-sm h-8 px-3"
      >
        {busy
          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
          : <Upload className="w-3.5 h-3.5" />}
        {STATE_LABEL[state]}
      </Button>
      {state === "error" && error && (
        <span className="text-xs text-red-400 max-w-xs">{error}</span>
      )}
    </div>
  );
}
