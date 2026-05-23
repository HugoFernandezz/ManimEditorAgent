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
│   ├── events.py                    ← tipos de PipelineEvent tipados
│   ├── requirements.txt             ← fastapi, uvicorn, pydantic, aiofiles
│   ├── harness/                     ← capa de harness engineering
│   │   ├── events.py / store.py     ← event-sourced log (events.jsonl)
│   │   ├── runner.py                ← call_agent con retry+validator+metrics
│   │   ├── prompts.py               ← templates versionados
│   │   ├── guardrails.py            ← validadores estructurales
│   │   ├── graders.py               ← code-based + LLM-as-judge
│   │   ├── telemetry.py             ← métricas OTel gen-ai
│   │   ├── evals.py                 ← suite offline pass@k
│   │   └── debug_log.py             ← logger de debug por proyecto (ver sección Debug Logging)
│   ├── agents/
│   │   ├── researcher.py
│   │   ├── planner.py
│   │   ├── beat_writer.py
│   │   ├── coder.py
│   │   ├── visual_qa.py
│   │   ├── editor.py                ← no usa LLM, solo ffmpeg + manim
│   │   └── curator.py
│   └── tools/
│       ├── extract_frames.py        ← ffmpeg: video → N PNG
│       ├── concat_scenes.py         ← ffmpeg concat demuxer
│       ├── plugin_installer.py      ← pip install + verificación import
│       ├── plugin_context.py        ← construye el contexto de plugins inyectado en prompts
│       ├── scene_utils.py           ← helpers comunes (e.g. get_scene_name)
│       ├── format_context.py        ← contexto de formato (YouTube vs TikTok) para agentes
│       └── skill_diff.py            ← genera/aplica diffs a archivos de skill
│
├── ui/                              ← Next.js App Router
│   ├── .env.local                   ← NEXT_PUBLIC_GOOGLE_CLIENT_ID (gitignoreado, ver Drive export)
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
│   │   ├── skill-editor.tsx         ← modal editor de archivos de skill
│   │   └── export-to-drive-button.tsx ← botón exportar video final a Google Drive
│   └── lib/api.ts                   ← cliente REST + WebSocket hook
│
└── projects/<slug>/                 ← generado en runtime, en .gitignore parcial
    ├── manifest.json                ← estado del proyecto/video (incluye `scenes` dict)
    ├── events.jsonl                 ← event-sourced trace (harness)
    ├── logs/pipeline_YYYYMMDDTHHMMSS.log  ← log de debug por ejecución (ver Debug Logging)
    ├── plugins_proposal.json
    ├── outline.md
    ├── beats/scene_NN.beats.json    ← Beat Writer: 2-5 beats/escena para sync voz↔anim
    ├── scenes/scene_NN.py           ← VoiceoverScene (audio embebido)
    ├── renders/scene_NN/{preview.mp4, frames/, qa_notes.md}
    ├── final/video_{lang}.mp4
    ├── feedback.json
    └── learnings/{notes.md, skill_patch.diff}
```

---

## Flujo de usuario

1. **Crear proyecto** — sidebar → "Nuevo proyecto" → modal pide `nombre` + `descripción` → proyecto en estado `draft`
2. **Configurar video** — dentro del proyecto, tab "Vista del flujo" → formulario con idea, idioma, **formato (YouTube/TikTok)**, duración, voz → `POST /projects/{id}/start-video`
3. **Pipeline corre** — tab "Ejecución" muestra nodos animados en tiempo real vía WebSocket
4. **Plugins** — el Researcher propone plugins → UI los muestra con checkboxes → usuario aprueba → se instalan con pip
5. **Revisar video** — cuando status = `awaiting_review` → tab → reproductor + formulario de feedback + botón **Exportar a Drive** → botón Aprobar
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

| Agente | Archivo | Modelo | Tools | Skills (inline o vía tool) |
|--------|---------|--------|-------|----------------------------|
| **Researcher** | `agents/researcher.py` | sonnet | `WebSearch,WebFetch` | — |
| **Planner** | `agents/planner.py` | sonnet | **— (sin tools)** | `SKILL.md` (+ `3b1b-style.md` si la idea lo menciona) — inline |
| **Beat Writer** | `agents/beat_writer.py` | sonnet | **— (sin tools)** | `references/narration.md`, `templates/voiceover.py` — inline |
| **Coder** | `agents/coder.py` | opus | **— (sin tools)** | `SKILL.md` + `api-cheatsheet.md` + `templates/voiceover.py` + `narration.md` + `troubleshooting.md` (+ `3b1b-style.md` condicional) — inline |
| **Visual QA** | `agents/visual_qa.py` | opus | `Read,Glob` (Read multimodal sobre PNG + troubleshooting.md) | `troubleshooting.md` (vía tool) |
| **Editor** | `agents/editor.py` | — (solo ffmpeg) | — | — |
| **Curator** | `agents/curator.py` | sonnet | **— (sin tools)** | `SKILL.md`, `troubleshooting.md` — inline |

**Importante sobre tools vs inline:** Researcher y Visual_QA son los únicos que usan tools.
El Researcher necesita `WebSearch/WebFetch` para verificar plugins reales. Visual_QA usa `Read`
porque la única forma de visión multimodal con `claude -p` es leer un PNG vía tool. **Todos los
demás agentes inyectan las skills inline en el prompt** — esto reduce el consumo de tokens
~5-10× porque evita el bucle agéntico de la CLI (cada `Read` tool call son varios roundtrips
y el system prompt se reenvía cada turno).

### Secuencia del pipeline

```
check_env.py
     ↓
Researcher  →  plugins_proposal.json
     ↓ (pausa — usuario aprueba plugins en UI)
plugin_installer × N (+ auto-install manim-voiceover[gtts])
     ↓
Planner  →  outline.md
     ↓
Beat Writer  →  beats/scene_NN.beats.json (2-5 beats por escena)
     ↓
Por cada escena (PARALELO, hasta 4 workers):
  Coder  →  scenes/scene_NN.py (VoiceoverScene con `with self.voiceover(...)` por beat)
    ↓ grade_scene_renderable (hasta 3 ciclos de fix con Coder.fix)
  render -ql  →  preview.mp4 (audio gTTS ya embebido)
  extract_frames  →  6 PNG
  Visual QA  →  qa_notes.md
    ↓ si needs_fix: Coder aplica fix_hint (hasta 3 ciclos)
     ↓
(pausa — usuario revisa CADA escena: approve / revise con feedback)
     ↓
Editor (no LLM)  →  render -qh + concat  →  final/video_{lang}.mp4
     ↓ (pausa — usuario revisa video final y aprueba)
Curator  →  learnings/notes.md + skill_patch.diff
     ↓ (usuario acepta/rechaza hunks en UI)
skill file actualizado
```

**No hay Narrator separado.** El audio se genera dentro del propio render de Manim vía `manim-voiceover` + `GTTSService`, beat a beat. El plugin se autoinstala al confirmar plugins (`tools.plugin_installer.ensure_installed`).

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

## Formato del video (YouTube vs TikTok)

El campo `format` del manifest controla el comportamiento de todos los agentes de generación. **No hay campo `audience`** — fue reemplazado por `format`.

### `backend/tools/format_context.py`

Dos funciones exportadas:
- `get_planning_context(fmt: str) -> str` — reglas narrativas/estructurales para Planner y Beat Writer
- `get_coding_context(fmt: str) -> str` — configuración Manim + safe zones para el Coder

### Comportamiento por formato

| Aspecto | YouTube | TikTok |
|---------|---------|--------|
| Aspect ratio | 16:9 (1920×1080) | 9:16 (1080×1920) |
| Manim config | defaults | `config.pixel_width=1080; config.pixel_height=1920; config.frame_width=9; config.frame_height=16` en cada scene_NN.py |
| Narrativa | Análítica, estructura progresiva | Retención hiperactiva, hook primeros 3s |
| Safe zones | Todo el canvas | x ∈ [-3.5, 3.5], y ∈ [-4.5, 5.0] (evitar bordes) |
| Duración beats | Normal | `self.wait() ≤ 0.3s` entre animaciones |

El Coder recibe `format_context=get_coding_context(fmt)` inyectado en su prompt, que incluye las instrucciones de `config` que debe poner al inicio de cada archivo.

---

## Exportar video a Google Drive

### Componente: `ui/components/export-to-drive-button.tsx`

Flujo OAuth 2.0 token model (no server-side):
1. Carga dinámicamente Google Identity Services (`accounts.google.com/gsi/client`)
2. Solicita token con scope `drive.file` (solo puede acceder a archivos que él mismo crea)
3. Fetcha el MP4 del backend local (`GET /projects/{id}/video`)
4. Sube a Drive vía multipart upload (`https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart`)
5. Retorna `webViewLink` — enlace directo al archivo en Drive

**5 estados del botón:** idle → authorizing → fetching → uploading → success/error

### Configuración requerida

El archivo `ui/.env.local` (gitignoreado) debe contener:
```
NEXT_PUBLIC_GOOGLE_CLIENT_ID=984294178550-phqpuc3u38j77rdjfj0uek7if7maqmdc.apps.googleusercontent.com
```

Si este archivo no existe, el botón no funcionará (mostrará error de client_id faltante). No commitear este archivo — contiene credenciales OAuth.

### Dónde aparece en la UI

En `ui/app/project/[slug]/page.tsx`, dentro del bloque `project?.final_video`, hay una barra inferior al reproductor con el formato label + `<ExportToDriveButton>`.

---

## Debug Logging (`backend/harness/debug_log.py`)

Cada pipeline crea un log de texto en `projects/<id>/logs/pipeline_YYYYMMDDTHHMMSS.log`. Este archivo es la fuente de verdad para diagnosticar fallos. Cuando algo falle, pide al usuario el path del log y léelo.

### API del módulo

```python
from harness import debug_log

debug_log.new_run(project_id)          # inicio del pipeline → crea nuevo archivo
debug_log.ensure_run(project_id)       # continuación → reutiliza o crea
debug_log.pipeline_start(project_id, manifest)
debug_log.pipeline_end(project_id, status, elapsed)
debug_log.stage(project_id, "planner")
debug_log.info(project_id, "mensaje")
debug_log.warning(project_id, "mensaje")
debug_log.error(project_id, "mensaje", exc)   # incluye traceback si exc no es None
debug_log.agent_call(...)              # prompts completos (truncados a 6000 chars)
debug_log.agent_done(...)              # output completo (truncado a 8000 chars)
debug_log.agent_retry(...)
debug_log.agent_failed(...)
debug_log.guardrail_violated(...)
debug_log.subprocess_result(...)       # cmd + stdout + stderr (truncado a 10000 chars)
debug_log.ui_state(project_id, description, f5_note="")   # snapshot visual de la UI
```

### `ui_state()` — snapshots visuales

Además del logging técnico, el orquestador llama a `debug_log.ui_state()` en cada transición para describir qué vería el usuario en pantalla en ese momento (qué nodos están activos, qué tabs aparecen, qué botones) y qué mostraría la UI si hiciera F5. Esto permite diagnosticar bugs de UI sin tener que reproducir el estado manualmente.

### Dónde se llama `new_run` vs `ensure_run`

- `new_run`: solo en `run_pipeline()` → crea archivo fresco al inicio de cada pipeline
- `ensure_run`: en `run_pipeline_after_plugins()`, `run_scene_revision()`, `run_finalize()`, `run_curator()` → reutiliza el archivo existente o crea uno nuevo si se llaman en standalone (resume, revision sin pipeline previo)

### Límites de truncado

| Campo | Límite |
|-------|--------|
| System prompt | 2 000 chars |
| User prompt | 6 000 chars |
| Output del agente | 8 000 chars |
| Subprocess stdout/stderr | 10 000 chars |

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
agent_started, agent_stream_line,
plugins_proposed, plugins_installed,
outline_ready, beats_ready,
scene_started, render_ok, render_failed,
frames_extracted, qa_ok, qa_issue, qa_degraded,
scene_preview_ready, scene_revising, scene_approved, scenes_all_approved,
scenes_all_rendered, finalizing, edit_done,
review_submitted, curator_done, patch_applied,
log, error
```

`agent_stream_line` lleva las líneas de tool_use / text del bucle agéntico del CLI (parseadas en `parse_stream_event`), y es lo que muestra el panel lateral cuando el usuario clica un nodo en ejecución. Para agentes sin tools (Planner/Beat Writer/Curator) el harness emite 2 líneas sintéticas ("Generando…" + "Output recibido N chars") para que el panel no aparezca vacío.

El frontend actualiza los nodos del `PipelineView` y el tab en función de estos eventos.

### Comportamiento al clicar un nodo (ui/components/pipeline-view.tsx)

Prioridad del onClick (decidido en este orden):
1. Si es gate (`plugins` / `scene_review`): navega a su página
2. Si el nodo está **running**: abre el panel lateral con los logs en vivo
3. Si NO está running y tiene skills: abre el editor de skill
4. Si NO está running, sin skills, pero ya completó (ok/error/degraded): abre el panel de logs histórico

---

## Manifest del proyecto (projects/\<slug\>/manifest.json)

```jsonc
{
  "id": "derivadas-bachillerato",
  "name": "Derivadas para bachillerato",       // nombre del proyecto
  "description": "...",
  "status": "draft | running | awaiting_plugins | planning_done | awaiting_scene_review | scenes_approved | awaiting_review | review_submitted | curated | error | env_failed",
  "created_at": "2026-...",
  // Campos de video (null hasta que el usuario lanza start-video):
  "idea": "Explica la derivada en un punto",
  "lang": "es",
  "format": "youtube | tiktok",                // ← antes era "audience"
  "target_length": "60s",
  "voice_profile": null,
  "export_langs": [],
  "plugins": {},                               // resultado del installer
  "plugins_proposal": [],                      // propuesta del Researcher
  "scenes": {                                  // poblado por init_scene_states
    "01": {
      "status": "pending|rendering|awaiting_review|revising|approved|failed",
      "preview_path": "projects/.../renders/scene_01/preview.mp4",
      "feedback_history": [{"ts": "...", "text": "..."}],
      "scene_desc": "primeros 300 chars del bloque del outline",
      "error": "..."                           // si status=failed
    }
  },
  "final_video": "projects/.../final/video_es.mp4"
}
```

---

## Decisiones de diseño importantes

| Decisión | Razón |
|----------|-------|
| `claude -p` CLI en vez del SDK | Usa Claude Pro del usuario (sin coste extra de API) |
| Pipeline **síncrono** en worker thread con escenas en paralelo (max 4) | Simplicidad + throughput |
| `--no-session-persistence` en cada invocación | Contexto completamente aislado entre videos |
| Visual QA usa `--tools Read,Glob` (multimodal) | Claude Code puede leer PNG directamente; no hay base64 manual |
| Researcher usa `--tools WebSearch,WebFetch` | Búsqueda real en plugins.manim.community en lugar de training data |
| Planner/Beat Writer/Coder/Curator **sin tools**, skill inyectado en prompt | Reduce tokens ~5-10× vs. el bucle agéntico de tool calls (cada Read = varios roundtrips, y el system prompt se reenvía cada turno) |
| Audio embebido en el render Manim (VoiceoverScene) | No hay paso de mux post-render: cada escena ya sale con su narración sincronizada vía `tracker.duration` |
| Beats como unidad atómica de sync voz↔anim | El Beat Writer produce 2-5 beats/escena; el Coder emite un `with self.voiceover(...)` por beat |
| Curator propone diffs, el usuario aprueba | Las skills son contexto crítico — no se modifican en silencio |
| Proyectos y videos son entidades separadas | El usuario puede crear el proyecto y configurar el video más tarde |
| Per-scene review con revise/approve | El usuario aprueba escena por escena antes del render final -qh |
| TikTok: config Manim en el scene_file, no en el comando | Cada `manim` CLI es un proceso fresh — el Coder pone `config.pixel_width/height` al principio del archivo y se aplica sin cambiar el comando de render |
| Drive export: OAuth token model en el cliente | Sin servidor OAuth — el token se obtiene en el navegador con Google Identity Services; scope `drive.file` minimiza permisos |
| Debug log por pipeline, no global | Permite aislar fallos por proyecto sin mezclar trazas; un archivo por run hace más fácil adjuntarlo para diagnóstico |

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

## Quirks de la CLI / Windows (no te tropieces otra vez)

Estos son detalles no obvios de cómo invocamos `claude -p` que ya nos rompieron en el pasado. Están todos en `backend/claude_runner.py`:

1. **El prompt va PRIMERO**, justo después de `-p`. Pasarlo al final (tras `--add-dir` u otros flags) hace que la CLI lo rechace con `"Input must be provided either through stdin or as a prompt argument."`.
2. **`encoding="utf-8", errors="replace"` en `subprocess.run` / `Popen`** — en Windows el default es cp1252; sin esto, la salida UTF-8 de `claude -p` se decodifica mal y todos los acentos / `¿` / `—` se vuelven mojibake (`Ã©`, `Â¿`, `â€"`). El archivo escrito a disco luego se ve mal aunque `write_text(..., encoding="utf-8")` sea correcto.
3. **`--verbose` es obligatorio cuando `--output-format=stream-json`** (CLI 2.1.x). La combinación `--print --output-format=stream-json` sin `--verbose` falla al instante con un mensaje claro pero los reintentos no aportan nada — se añade automáticamente en `run_with_tools` cuando hay `on_event`.
4. **Guard contra stdout vacío con returncode 0** — la CLI a veces sale OK sin producir nada. `_exec_json` detecta `stdout` vacío y lanza un mensaje explícito en vez de dejar que `json.loads(None/"")` peté con un `TypeError` críptico.
5. **`set_stream_emit` es per-thread (threading.local)**. Cualquier agente cuya llamada deba surfar líneas al panel de la UI necesita que su thread tenga el emitter registrado. Lo hacen: `_run_scene_initial` (threads de escenas) y `run_pipeline_after_plugins` (thread principal stage-2).

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
| `debug_log.py` | Log de debug por proyecto + UI state snapshots | Diagnosticabilidad |

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

- [ ] Backend real de voz clonada (XTTS v2, F5-TTS, Piper) en lugar de gTTS
- [ ] Traducción automática del script a otros idiomas (la estructura multi-idioma ya existe en el manifest)
- [ ] Autenticación / multiusuario en la UI (actualmente single-user local)
- [ ] Dockerización
- [ ] Tests automatizados
