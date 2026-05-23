"""Format-specific context injected into agent prompts.

Two formats are supported: "youtube" (default) and "tiktok".
Each returns different narrative/structural rules (for Planner, Beat Writer)
and technical/layout rules (for Coder).
"""

# ── Planning context (Planner + Beat Writer) ─────────────────────────────────

_TIKTOK_PLANNING = """FORMAT: TikTok (vertical 9:16 — 1080×1920)
PACING Y ESTRUCTURA:
- Retención hiperactiva: el gancho debe ocurrir en los primeros 2 segundos (primer beat, escena 1).
- Jump cuts continuos: ninguna escena puede quedarse estática; cada beat exige cambio visual inmediato.
- Sin tiempos muertos: transiciones directas, sin pausas vacías entre animaciones.
- Dinamismo visual constante: el objetivo es maximizar la retención inmediata y el engagement impulsivo.
- Duración: 3-5 escenas de 15-30 s cada una (total ≤ 90 s).
DISEÑO DE ESCENAS (Safe Zones):
- Toda la información crítica (texto, ecuaciones, gráficos) debe estar en el 60 % central del frame.
  • Evitar margen derecho — zona de UI de interacción (likes, comentarios, compartir).
  • Evitar tercio inferior — zona de descripción, hashtags y título de canción.
  • Evitar margen superior — barra de estado y buscador.
- Ningún elemento vital en zonas de peligro."""

_YOUTUBE_PLANNING = """FORMAT: YouTube (horizontal 16:9 — 1920×1080)
PACING Y ESTRUCTURA:
- Enfoque narrativo y analítico: ritmo calmado y deliberado.
- Desarrollo profundo de ideas: construir autoridad, conexión emocional y aprendizaje real.
- No sobreestimular: el objetivo es retención de conocimiento, no de pantalla.
- Duración flexible: formato largo (>3 min) es apropiado; beats extensos son bienvenidos.
DISEÑO DE ESCENAS:
- Aprovechar casi la totalidad del frame horizontal 16:9.
- Evitar esquina inferior derecha (marca de agua del canal e indicador de tiempo).
- Dejar margen inferior para controles de reproducción y timeline."""

# ── Coding context (Coder) ───────────────────────────────────────────────────

_TIKTOK_CODING = """FORMAT: TikTok (vertical 9:16 — 1080×1920)
CONFIGURACIÓN DE CÁMARA — añade estas líneas justo después de los imports, antes de la clase:
  from manim import config
  config.pixel_width = 1080
  config.pixel_height = 1920
  config.frame_width = 9
  config.frame_height = 16

SAFE ZONES (coordenadas ManimCE en el espacio 9×16):
  - Horizontal: sitúa los elementos en x ∈ [-3.5, 3.5] (el margen derecho tiene la UI de TikTok).
  - Vertical: sitúa los elementos en y ∈ [-4.5, 5.0] (tercio inferior = descripción; margen superior = status bar).
  - Para contenido importante: desplaza con UP * 1 para elevar ligeramente al centro alto del frame.
  - PROHIBIDO: texto o ecuaciones fuera de x ∈ [-3, 3] o y ∈ [-4, 5].

DINAMISMO (obligatorio — retención hiperactiva):
  - Cada beat debe tener cambios visuales activos durante toda su duración.
  - Usa self.wait() ≤ 0.3 s entre animaciones dentro de un beat. Sin frames estáticos.
  - Usa FadeOut / Transform / ReplacementTransform para transiciones rápidas entre beats.
  - El primer beat (beat 1.1 de la escena 1) es el gancho: debe ser visualmente impactante desde el frame 1."""

_YOUTUBE_CODING = """FORMAT: YouTube (horizontal 16:9 — 1920×1080)
CONFIGURACIÓN DE CÁMARA: usa el frame por defecto de ManimCE (frame_width≈14.2, frame_height=8).
No modificar config a menos que sea explícitamente necesario.

LAYOUT:
  - Aprovecha la totalidad del frame horizontal.
  - Evita la zona (x > 5.5, y < -3.2): ahí aparecen marca de agua del canal y timestamp.
  - Margen inferior temporal para controles de reproducción: evita y < -3.8 para texto crítico.

DINAMISMO: el ritmo puede ser deliberado. self.wait(1.0 - 2.0) entre beats es aceptable para
dar tiempo al espectador de procesar el contenido matemático."""


def get_planning_context(fmt: str) -> str:
    """Context for Planner and Beat Writer: narrative/structural rules."""
    return _TIKTOK_PLANNING if fmt == "tiktok" else _YOUTUBE_PLANNING


def get_coding_context(fmt: str) -> str:
    """Context for Coder: Manim config + layout safe zones + dynamism rules."""
    return _TIKTOK_CODING if fmt == "tiktok" else _YOUTUBE_CODING
