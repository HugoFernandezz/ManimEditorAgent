# ManimEditorAgent — Memoria del proyecto

> Lee este archivo al inicio de cada sesión. Contiene todo lo necesario para continuar el desarrollo sin contexto previo.

---

## Qué es este proyecto

Sistema multi-agente que, dado el nombre de un proyecto y una idea de video, orquesta una cadena de agentes de IA para producir un video Manim (animación matemática/científica) pulido de forma automatizada. El usuario interactúa exclusivamente desde una UI web; no necesita tocar la terminal ni escribir código Manim.

**Stack:**
- Backend: Python + FastAPI + WebSocket
- Agentes: `claude -p` CLI (usa la suscripción Claude Pro del usuario, sin API key separada)
- Frontend: Next.js 15 + TypeScript + Tailwind + shadcn/ui
- Render: ManimCE + ffmpeg
- Repo: https://github.com/HugoFernandezz/ManimEditorAgent.git
- Rama principal: `master`

---

## Estructura de directorios

```
proyectoManim/
├── CLAUDE.md                        ← este archivo
├── start.ps1                        ← arranca backend + frontend en ventanas separadas
├── .gitignore
│
├── .agents/skills/manim/            ← LA SKILL PRINCIPAL (solo esta existe)
│   ├── SKILL.md                     ← reglas del workflow Manim, anti-patterns
│   ├── references/
│   │   ├── api-cheatsheet.md        ← API ManimCE esencial
│   │   ├── troubleshooting.md       ← error → fix (actualizable por Curator)
│   │   ├── 3b1b-style.md            ← paleta de colores 3Blue1Brown
│   │   ├── narration.md             ← guía manim-voiceover
│   │   └── manimgl-diff.md          ← diferencias CE vs GL
│   ├── scripts/
│   │   ├── check_env.py             ← verifica manim, ffmpeg, latex
│   │   └── render_verify.py         ← render -ql + parse stderr
│   └── templates/
│       ├── basic.py, math.py, threed.py, voiceover.py
│
├── backend/
│   ├── main.py                      ← FastAPI: REST endpoints + WebSocket /ws/{project_id}
│   ├── orchestrator.py              ← state machine del pipeline (sync, corre en thread)
│   ├── project_store.py             ← CRUD de manifests en projects/
│   ├── claude_runner.py             ← wrapper de `claude -p` CLI
│   ├── events.py                    ← 20 tipos de PipelineEvent tipados
│   ├── sessions.py                  ← deprecated (era para SDK, ya no se usa)
│   ├── requirements.txt             ← fastapi, uvicorn, pydantic, aiofiles
│   ├── agents/
│   │   ├── researcher.py
│   │   ├── planner.py
│   │   ├── coder.py
│   │   ├── visual_qa.py
│   │   ├── narrator.py
│   │   ├── editor.py                ← no usa LLM, solo ffmpeg + manim
│   │   └── curator.py
│   └── tools/
│       ├── extract_frames.py        ← ffmpeg: video → N PNG
│       ├── mux_audio.py             ← ffmpeg: video + wav → mp4
│       ├── concat_scenes.py         ← ffmpeg concat demuxer
│       ├── plugin_installer.py      ← pip install + verificación import
│       ├── tts_adapter.py           ← interfaz TTS pluggable (stub silencioso por defecto)
│       └── skill_diff.py            ← genera/aplica diffs a archivos de skill
│
├── ui/                              ← Next.js App Router
│   ├── app/
│   │   ├── layout.tsx               ← monta AppShell (sidebar + header)
│   │   ├── page.tsx                 ← home: "selecciona un proyecto"
│   │   ├── new/page.tsx             ← redirect a / (creación via modal)
│   │   └── project/[slug]/
│   │       ├── page.tsx             ← vista principal del proyecto (tabs)
│   │       ├── plugins/page.tsx     ← confirmación de plugins propuestos
│   │       ├── review/page.tsx      ← reproductor + feedback del usuario
│   │       └── learnings/page.tsx   ← diff viewer del Curator
│   ├── components/
│   │   ├── app-shell.tsx            ← layout: sidebar colapsable + header
│   │   ├── new-project-modal.tsx    ← modal: solo nombre + descripción
│   │   ├── start-video-form.tsx     ← formulario de configuración del video (dentro del proyecto)
│   │   ├── pipeline-view.tsx        ← nodos animados en tiempo real (tab Ejecución)
│   │   ├── flow-diagram.tsx         ← diagrama vertical estático (tab Vista del flujo)
│   │   └── skill-editor.tsx         ← modal editor de archivos de skill
│   └── lib/api.ts                   ← cliente REST + WebSocket hook
│
└── projects/<slug>/                 ← generado en runtime, en .gitignore parcial
    ├── manifest.json                ← estado del proyecto/video
    ├── plugins_proposal.json
    ├── outline.md
    ├── scenes/scene_NN.py
    ├── renders/scene_NN/{preview.mp4, frames/, qa_notes.md}
    ├── audio/{script.txt, scene_NN.wav}
    ├── final/video_{lang}.mp4
    ├── feedback.json
    └── learnings/{notes.md, skill_patch.diff}
```

---

## Flujo de usuario

1. **Crear proyecto** — sidebar → "Nuevo proyecto" → modal pide `nombre` + `descripción` → proyecto en estado `draft`
2. **Configurar video** — dentro del proyecto, tab "Vista del flujo" → formulario con idea, idioma, audiencia, duración, voz → `POST /projects/{id}/start-video`
3. **Pipeline corre** — tab "Ejecución" muestra nodos animados en tiempo real vía WebSocket
4. **Plugins** — el Researcher propone plugins → UI los muestra con checkboxes → usuario aprueba → se instalan con pip
5. **Revisar video** — cuando status = `awaiting_review` → tab → reproductor + formulario de feedback → botón Aprobar
6. **Aprendizajes** — si aprobado, el Curator genera learnings y propone diff a la skill → UI muestra diff por hunks → usuario acepta/rechaza cada uno

---

## Sistema de agentes (núcleo de la app)

### Cómo se invocan

**NO se usa el SDK de Anthropic directamente.** Cada agente llama a `claude -p` vía subprocess a través de `backend/claude_runner.py`:

```python
# Texto puro (sin herramientas)
run_text(prompt, system, model="sonnet", timeout=120)

# Con herramientas habilitadas
run_with_tools(prompt, system, model="opus", tools="Read", add_dirs=[path])
```

Esto usa la **suscripción Claude Pro** del usuario — no necesita `ANTHROPIC_API_KEY`.

### Aislamiento de contexto

Cada video es una invocación fresh de `claude -p --no-session-persistence`. Ningún agente recibe historial de videos anteriores.

### Tabla de agentes

| Agente | Archivo | Modelo | Tools | Skill files que lee |
|--------|---------|--------|-------|---------------------|
| **Researcher** | `agents/researcher.py` | sonnet | WebSearch, WebFetch | — |
| **Planner** | `agents/planner.py` | sonnet | — | `SKILL.md` |
| **Coder** | `agents/coder.py` | opus | — | `SKILL.md`, `api-cheatsheet.md`, `troubleshooting.md`, templates |
| **Visual QA** | `agents/visual_qa.py` | opus | Read (imágenes) | `SKILL.md`, `troubleshooting.md` |
| **Narrator** | `agents/narrator.py` | sonnet | — | `references/narration.md` |
| **Editor** | `agents/editor.py` | — (ffmpeg) | — | — |
| **Curator** | `agents/curator.py` | sonnet | — | `SKILL.md`, `troubleshooting.md` |

### Secuencia del pipeline

```
check_env.py
     ↓
Researcher  →  plugins_proposal.json
     ↓ (pausa — usuario aprueba plugins en UI)
plugin_installer × N
     ↓
Planner  →  outline.md
     ↓
Por cada escena (secuencial):
  Coder  →  scene_NN.py
    ↓ render_verify.py (hasta 3 ciclos de fix)
  render -ql  →  preview.mp4
  extract_frames  →  6 PNG
  Visual QA  →  qa_notes.md
    ↓ si needs_fix: Coder aplica fix_hint (hasta 3 ciclos)
     ↓
Narrator  →  script.txt + scene_NN.wav (TTS o silencioso)
     ↓
Editor  →  render -qh + mux + concat  →  final/video_{lang}.mp4
     ↓ (pausa — usuario revisa y aprueba en UI)
Curator  →  learnings/notes.md + skill_patch.diff
     ↓ (usuario acepta/rechaza hunks en UI)
skill file actualizado
```

### Cómo las skills se leen

Los agentes leen los archivos de skill directamente con Python `Path.read_text()` y los incluyen en el prompt de `claude -p`. No hay ningún mecanismo de RAG ni embedding — es contexto directo en el prompt.

```python
# Ejemplo en coder.py
skill_md = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
troubleshoot = (SKILL_ROOT / "references" / "troubleshooting.md").read_text(encoding="utf-8")
prompt = f"SKILL CONTEXT:\n{skill_md}\n\n{troubleshoot}\n\n..."
```

`SKILL_ROOT` = `proyectoManim/.agents/skills/manim/`

### Cómo el Curator actualiza las skills

1. Lee `outline.md`, `qa_notes.md` (×N), `feedback.json`
2. Genera texto propuesto para `SKILL.md` y/o `troubleshooting.md`
3. `skill_diff.py` genera un unified diff
4. La UI muestra el diff por hunks (accept/reject)
5. `PUT /skills/{path}` escribe el archivo si el usuario acepta

Los archivos editables están en una allowlist en `main.py` (`_ALLOWED_SKILL_FILES`).

---

## Comunicación frontend ↔ backend

### REST endpoints clave

| Método | Ruta | Acción |
|--------|------|--------|
| GET | `/projects` | Lista todos los proyectos |
| POST | `/projects` | Crea proyecto (solo nombre + descripción) |
| GET | `/projects/{id}` | Lee manifest |
| POST | `/projects/{id}/start-video` | Configura video y arranca pipeline |
| POST | `/projects/{id}/plugins/confirm` | Instala plugins aprobados y continúa |
| POST | `/projects/{id}/review` | Envía feedback; si approved=true lanza Curator |
| GET | `/projects/{id}/learnings` | Lee notes.md + skill_patch.diff |
| POST | `/projects/{id}/learnings/apply` | Aplica un hunk de diff a la skill |
| GET | `/projects/{id}/video` | Sirve el mp4 final |
| GET/PUT | `/skills/{path}` | Lee/escribe archivos de skill (editor) |
| WS | `/ws/{project_id}` | Stream de eventos del pipeline |

### WebSocket events (backend → frontend)

```
pipeline_started, env_check_ok, env_check_failed,
agent_started, agent_finished, agent_error,
plugins_proposed, plugins_installed,
outline_ready,
scene_started, render_ok, render_failed,
frames_extracted, qa_ok, qa_issue, qa_degraded,
narration_ready, edit_done,
review_submitted, curator_done, patch_applied,
log, error
```

El frontend actualiza los nodos del `PipelineView` y el tab en función de estos eventos.

---

## Manifest del proyecto (projects/\<slug\>/manifest.json)

```jsonc
{
  "id": "derivadas-bachillerato",
  "name": "Derivadas para bachillerato",       // nombre del proyecto
  "description": "...",
  "status": "draft | running | awaiting_plugins | awaiting_review | curated | error",
  "created_at": "2026-...",
  // Campos de video (null hasta que el usuario lanza start-video):
  "idea": "Explica la derivada en un punto",
  "lang": "es",
  "audience": "high school",
  "target_length": "60s",
  "voice_profile": null,
  "export_langs": [],
  "tts_backend": "stub",
  "plugins": {},                               // resultado del installer
  "plugins_proposal": [],                      // propuesta del Researcher
  "final_video": "projects/.../final/video_es.mp4"
}
```

---

## Decisiones de diseño importantes

| Decisión | Razón |
|----------|-------|
| `claude -p` CLI en vez del SDK | Usa Claude Pro del usuario (sin coste extra de API) |
| Pipeline **síncrono** en worker thread | Simplicidad; GPU/CPU no se saturan con escenas en paralelo |
| `--no-session-persistence` en cada invocación | Contexto completamente aislado entre videos |
| Visual QA usa `--tools Read` (multimodal) | Claude Code puede leer PNG directamente; no hay base64 manual |
| Researcher usa `--tools WebSearch,WebFetch` | Búsqueda real en plugins.manim.community en lugar de training data |
| Skills se leen con `Path.read_text()` | Sin RAG; el contexto cabe en el prompt de sonnet/opus |
| Curator propone diffs, el usuario aprueba | Las skills son contexto crítico — no se modifican en silencio |
| Proyectos y videos son entidades separadas | El usuario puede crear el proyecto y configurar el video más tarde |
| TTS es un stub enchufable | El backend real (XTTS/F5/Piper) se elige después |

---

## Para arrancar en local

```powershell
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload   # http://localhost:8000

# Terminal 2 — frontend
cd ui
npm install
npm run dev                 # http://localhost:3000

# O todo a la vez:
.\start.ps1
```

**Prerequisitos:** `manim`, `ffmpeg`, `latex` instalados y accesibles en PATH. Verificar con:
```powershell
python .agents/skills/manim/scripts/check_env.py
```

El usuario debe estar autenticado en Claude Code (`claude auth`) para que `claude -p` funcione.

---

## Capa de harness engineering (backend/harness/)

Capa que envuelve a todos los agentes. Implementa los principios de *awesome-harness-engineering*:

| Módulo | Responsabilidad | Principio |
|--------|-----------------|-----------|
| `events.py` | `AgentEvent` + `EventLog` event-sourced | 12-Factor #5 |
| `store.py` | `events.jsonl` atómico (resumibilidad tras crash) | Anthropic checkpointing |
| `runner.py` | `call_agent()` con retry exponencial + validator + métricas | 12-Factor #9 |
| `guardrails.py` | Validadores estructurales (JSON, YAML, Python AST) | Safe autonomy |
| `prompts.py` | Templates versionados (`v2`) y parametrizados | 12-Factor #2 |
| `graders.py` | Cascada deterministic → LLM-judge | Anthropic eval taxonomy |
| `evals.py` | Suite offline con `pass@1` / `pass^k` | Non-determinism handling |
| `telemetry.py` | Métricas OTel gen-ai (cost, latency, tokens) | Observabilidad |

### Cómo añadir un agente nuevo

```python
# 1. Define el prompt en harness/prompts.py:
MY_AGENT = Prompt(name="my_agent", version="v1", system="...", user_template="$x $y")

# 2. Define un validator (opcional pero recomendado):
def _validator(raw: str) -> tuple[bool, str]:
    return ("expected_marker" in raw, "missing marker")

# 3. El agente en sí queda en 4 líneas:
def run(project_id: str, x: str, y: str) -> str:
    return call_agent(
        project_id=project_id, agent="my_agent",
        prompt=MY_AGENT.render(x=x, y=y), system=MY_AGENT.system,
        validator=_validator,
    )
```

### Endpoints de telemetría

- `GET /projects/{id}/trace` — log completo de eventos (~JSONL en memoria)
- `GET /projects/{id}/metrics` — calls/retries/tokens/cost por agente
- `GET /projects/{id}/grades` — resultados de todos los graders

### Ejecutar evals

```bash
cd backend
python -m harness.evals run --repeats 3        # pass@3 / pass^3
python -m harness.evals run --only fourier_intro
```

Resultados en `evals/runs/<timestamp>/{results.json, summary.json}`.

---

## Cosas pendientes / fuera de alcance actual

- [ ] Backend real de voz clonada (XTTS v2, F5-TTS, Piper) — `tts_adapter.py` tiene la interfaz lista
- [ ] Traducción automática del script a otros idiomas (la estructura multi-idioma ya existe en el manifest)
- [ ] Paralelización de escenas (secuencial por ahora)
- [ ] Autenticación / multiusuario en la UI (actualmente single-user local)
- [ ] Dockerización
- [ ] Tests automatizados
