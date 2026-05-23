from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService


class Scene01(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="es"))

        title = Text("El Determinante", font_size=60)
        formula = MathTex(
            r"\det\begin{pmatrix}a & b \\ c & d\end{pmatrix} = ad - bc",
            font_size=56,
        )
        formula.next_to(title, DOWN, buff=0.5)

        with self.voiceover(
            text="El determinante: una fórmula que todos memorizan."
        ) as tracker:
            self.play(Write(title), run_time=tracker.duration)

        with self.voiceover(text="¿Pero qué significa realmente?") as tracker:
            self.play(FadeIn(formula), run_time=tracker.duration)