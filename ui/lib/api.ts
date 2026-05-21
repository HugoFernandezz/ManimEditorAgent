const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Project {
  id: string;
  idea: string;
  lang: string;
  audience: string;
  target_length: string;
  voice_profile?: string;
  export_langs: string[];
  tts_backend: string;
  status: string;
  created_at: string;
  plugins?: Record<string, { status: string }>;
  plugins_proposal?: Plugin[];
  final_video?: string;
  error?: string;
}

export interface Plugin {
  name: string;
  description: string;
  repo: string;
  relevance: string;
}

export interface PipelineEvent {
  kind: string;
  project_id: string;
  payload: Record<string, unknown>;
}

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${BASE}/projects`);
  return res.json();
}

export async function createProject(data: {
  idea: string;
  lang: string;
  audience: string;
  target_length: string;
  voice_profile?: string;
  export_langs?: string[];
  tts_backend?: string;
}): Promise<Project> {
  const res = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchProject(id: string): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`);
  if (!res.ok) throw new Error("Project not found");
  return res.json();
}

export async function confirmPlugins(id: string, approved: string[]): Promise<void> {
  await fetch(`${BASE}/projects/${id}/plugins/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
}

export async function submitReview(
  id: string,
  data: { approved: boolean; feedback: string; what_worked: string; what_didnt: string }
): Promise<void> {
  await fetch(`${BASE}/projects/${id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function fetchLearnings(id: string): Promise<{ notes: string; diff: string }> {
  const res = await fetch(`${BASE}/projects/${id}/learnings`);
  return res.json();
}

export async function applyPatch(id: string, file_rel: string, hunk: string): Promise<void> {
  await fetch(`${BASE}/projects/${id}/learnings/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_rel, hunk }),
  });
}

export function videoUrl(id: string, lang = "es"): string {
  return `${BASE}/projects/${id}/video?lang=${lang}`;
}

export function frameUrl(id: string, sceneNum: number, filename: string): string {
  return `${BASE}/projects/${id}/frames/${sceneNum}/${filename}`;
}

export async function fetchSkillFiles(): Promise<string[]> {
  const res = await fetch(`${BASE}/skills`);
  return res.json();
}

export async function fetchSkillFile(path: string): Promise<{ path: string; content: string }> {
  const res = await fetch(`${BASE}/skills/${path}`);
  if (!res.ok) throw new Error("Not found");
  return res.json();
}

export async function saveSkillFile(path: string, content: string): Promise<void> {
  await fetch(`${BASE}/skills/${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function createWebSocket(projectId: string, onEvent: (e: PipelineEvent) => void): WebSocket {
  const ws = new WebSocket(`ws://localhost:8000/ws/${projectId}`);
  ws.onmessage = (msg) => {
    try {
      const event: PipelineEvent = JSON.parse(msg.data);
      onEvent(event);
    } catch {}
  };
  const ping = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send("ping");
  }, 15000);
  ws.onclose = () => clearInterval(ping);
  return ws;
}
