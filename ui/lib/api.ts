const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  // Video fields (null until video is started)
  idea?: string | null;
  lang: string;
  audience: string;
  target_length: string;
  voice_profile?: string | null;
  export_langs: string[];
  tts_backend: string;
  plugins?: Record<string, { status: string }>;
  plugins_proposal?: Plugin[];
  final_video?: string;
  error?: string;
  scenes?: Record<string, { status: SceneStatus; error?: string }>;
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

export async function createProject(data: { name: string; description?: string }): Promise<Project> {
  const res = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function startVideo(
  projectId: string,
  data: {
    idea: string;
    lang: string;
    audience: string;
    target_length: string;
    voice_profile?: string;
    export_langs?: string[];
    skip_research?: boolean;
  }
): Promise<void> {
  const res = await fetch(`${BASE}/projects/${projectId}/start-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function fetchProject(id: string): Promise<Project> {
  const res = await fetch(`${BASE}/projects/${id}`);
  if (!res.ok) throw new Error("Project not found");
  return res.json();
}

export async function confirmPlugins(id: string, approved: string[]): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}/plugins/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  if (!res.ok) throw new Error(await res.text());
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

// ── Scene types ──────────────────────────────────────────────────────────────

export type SceneStatus =
  | "pending"
  | "rendering"
  | "awaiting_review"
  | "revising"
  | "approved"
  | "failed";

export interface SceneFeedback {
  ts: string;
  text: string;
}

export interface Scene {
  scene: number;
  status: SceneStatus;
  preview_url: string | null;
  feedback_history: SceneFeedback[];
  beats: unknown[];
  scene_desc?: string;
}

export async function fetchScenes(id: string): Promise<Scene[]> {
  const res = await fetch(`${BASE}/projects/${id}/scenes`);
  if (!res.ok) throw new Error("Failed to fetch scenes");
  return res.json();
}

export async function approveScene(id: string, sceneNum: number): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}/scenes/${sceneNum}/approve`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function reviseScene(id: string, sceneNum: number, feedback: string): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}/scenes/${sceneNum}/revise`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function finalizeProject(id: string): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}/finalize`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await res.text());
}

// ── Stop & resume ──────────────────────────────────────────────────────────

export type ResumeStep = "planner" | "beats" | "scenes";

export interface ResumeStepInfo {
  available: boolean;
  label: string;
  detail: string;
  skips: string[];
}

export interface ResumeOptions {
  planner: ResumeStepInfo;
  beats: ResumeStepInfo;
  scenes: ResumeStepInfo;
  artifacts: {
    outline: boolean;
    beats_count: number;
    scenes_count: number;
  };
}

export async function stopPipeline(id: string): Promise<{ ok: boolean; killed_subprocesses: number }> {
  const res = await fetch(`${BASE}/projects/${id}/stop`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function fetchResumeOptions(id: string): Promise<ResumeOptions> {
  const res = await fetch(`${BASE}/projects/${id}/resume-options`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function resumePipeline(id: string, fromStep: ResumeStep): Promise<void> {
  const res = await fetch(`${BASE}/projects/${id}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_step: fromStep }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export function scenePreviewUrl(id: string, sceneNum: number): string {
  return `${BASE}/projects/${id}/scenes/${sceneNum}/preview`;
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
