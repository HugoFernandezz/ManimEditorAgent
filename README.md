# ManimEditorAgent

> **Sistema multi-agente que convierte una idea en un video de animación matemática**, totalmente automatizado. Sin tocar código Manim ni la terminal.

<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-Pro_subscription-blueviolet?style=for-the-badge&logo=anthropic" />
  <img src="https://img.shields.io/badge/ManimCE-latest-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Next.js-15-black?style=for-the-badge&logo=next.js" />
  <img src="https://img.shields.io/badge/FastAPI-Python-009688?style=for-the-badge&logo=fastapi" />
</p>

---

## ¿Qué hace?

Describes una idea → una cadena de agentes de IA produce el video completo:

```
Idea  ──▶  Researcher  ──▶  Planner  ──▶  Beat Writer  ──▶  Coder × escenas
                                                                    │
                                                              (paralelo, hasta 4)
                                                                    │
                                                             render -ql  ──▶  Visual QA
                                                                    │
                                                           Revisión humana
                                                                    │
                                                         Editor (ffmpeg + -qh)
                                                                    │
                                                            Curator (aprendizajes)
```

| Agente | Qué hace |
|--------|----------|
| **Researcher** | Busca plugins Manim necesarios para la idea |
| **Planner** | Genera el outline de escenas |
| **Beat Writer** | Sincroniza narración ↔ animación beat a beat |
| **Coder** | Escribe el código Manim de cada escena con audio embebido |
| **Visual QA** | Revisa frames del render y propone correcciones |
| **Editor** | Concatena escenas en el video final con ffmpeg |
| **Curator** | Extrae aprendizajes y mejora la skill de Manim |

**No necesitas API key de Anthropic.** Los agentes usan `claude -p` — tu propia suscripción Claude Code Pro.

---

## Stack

- **Backend** — Python · FastAPI · WebSocket
- **Agentes** — `claude -p` CLI (Claude Code)
- **Frontend** — Next.js 15 · TypeScript · Tailwind · shadcn/ui
- **Render** — ManimCE · ffmpeg
- **TTS** — gTTS (gratis) · ElevenLabs (opcional)

---

## Requisitos previos

- [Claude Code](https://claude.ai/code) con suscripción Pro y `claude auth` completado
- Python ≥ 3.10
- Node.js ≥ 18
- [ManimCE](https://docs.manim.community/en/stable/installation.html) instalado (`manim --version`)
- ffmpeg instalado (`ffmpeg -version`)
- LaTeX instalado (MiKTeX / TeX Live)

Verifica el entorno:
```bash
python .agents/skills/manim/scripts/check_env.py
```

---

## Instalación

### 1 — Clonar

```bash
git clone https://github.com/HugoFernandezz/ManimEditorAgent.git
cd ManimEditorAgent
```

### 2 — Backend

```bash
cd backend
pip install -r requirements.txt
```

Crea `backend/.env` (solo si usas ElevenLabs):
```env
ELEVENLABS_API_KEY=tu_api_key
ELEVEN_API_KEY=tu_api_key
```

### 3 — Frontend

```bash
cd ui
npm install
```

Crea `ui/.env.local` (solo si quieres el botón "Exportar a Drive"):
```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=<tu-client-id>.apps.googleusercontent.com
```
→ Obtén uno gratis en [Google Cloud Console](https://console.cloud.google.com/apis/credentials) · tipo **Aplicación web** · origin `http://localhost:3000`

### 4 — Arrancar

```bash
# Windows — todo a la vez:
.\start.ps1

# O por separado:
# Terminal 1:  cd backend && uvicorn main:app --reload
# Terminal 2:  cd ui     && npm run dev
```

Abre **http://localhost:3000**

---

## Uso

1. **Nuevo proyecto** — barra lateral → "Nuevo proyecto" → nombre + descripción
2. **Configurar video** — tab "Vista del flujo" → idea, idioma, formato (YouTube / TikTok), duración, voz, ciclos QA
3. **Lanzar** — el pipeline corre en tiempo real, puedes ver cada agente en el tab "Ejecución"
4. **Aprobar plugins** — el Researcher propone plugins; los instalas con un clic
5. **Revisar escenas** — cada escena se muestra con preview + feedback antes del render final
6. **Video final** — descarga el MP4 o expórtalo directo a Google Drive

---

## Formatos soportados

| | YouTube | TikTok |
|---|---|---|
| Resolución | 1920 × 1080 (16:9) | 1080 × 1920 (9:16) |
| Narrativa | Analítica, progresiva | Hook primeros 3s, retención hiperactiva |

---

## TTS soportado

| Backend | Configuración | Coste |
|---------|--------------|-------|
| **gTTS** (default) | Sin config extra | Gratis |
| **ElevenLabs** | `ELEVENLABS_API_KEY` en `backend/.env` | De pago |

---

## Estructura del repositorio

```
ManimEditorAgent/
├── backend/          # FastAPI + agentes + harness
│   ├── agents/       # researcher, planner, beat_writer, coder, visual_qa, editor, curator
│   ├── harness/      # retry, graders, telemetría, debug logging
│   └── tools/        # ffmpeg, format context, voice context
├── ui/               # Next.js 15 — interfaz web
│   ├── app/          # rutas: proyecto, plugins, review, learnings
│   └── components/   # pipeline view, skill editor, export to drive…
├── .agents/skills/manim/   # skill viva: reglas, cheatsheet, troubleshooting
└── projects/         # generado en runtime (gitignoreado)
```

---

## Licencia

MIT
