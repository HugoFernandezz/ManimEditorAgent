from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
import numpy as np


class Scene04(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="es"))

        # Background grid
        plane = NumberPlane(
            x_range=[-7, 7, 1],
            y_range=[-4, 4, 1],
            background_line_style={"stroke_opacity": 0.35, "stroke_width": 1},
            axis_config={"stroke_opacity": 0.6},
        )

        # Fresh unit square at (0,0), (1,0), (1,1), (0,1)
        square = Polygon(
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
            color=BLUE,
        ).set_fill(BLUE, opacity=0.5).set_stroke(BLUE, width=2)

        # Basis vectors
        i_hat = Arrow(ORIGIN, [1, 0, 0], buff=0, color=GREEN, stroke_width=6)
        j_hat = Arrow(ORIGIN, [0, 1, 0], buff=0, color=RED, stroke_width=6)

        self.add(plane, square, i_hat, j_hat)

        matrix = np.array([[1, 2], [0.5, 1]])

        # Beat 4.1 — apply the singular matrix; the square flattens onto y = 0.5x
        with self.voiceover(text="¿Y si el determinante es cero?") as tracker:
            self.play(
                ApplyMatrix(matrix, square),
                ApplyMatrix(matrix, i_hat),
                ApplyMatrix(matrix, j_hat),
                ApplyMatrix(matrix, plane),
                run_time=tracker.duration,
            )

        # Beat 4.2 — show the determinant calculation and the collapse message
        det_eq = MathTex(
            r"\det\begin{pmatrix}1 & 2 \\ 0{,}5 & 1\end{pmatrix}"
            r" = 1\cdot 1 - 2\cdot 0{,}5 = 0",
            font_size=40,
            color=RED,
        ).to_edge(UP)
        det_eq.add_background_rectangle(color=BLACK, opacity=0.85, buff=0.15)

        msg = Text(
            "det = 0 → el espacio colapsa a una línea",
            font_size=30,
            color=RED,
        ).to_edge(DOWN)
        msg.add_background_rectangle(color=BLACK, opacity=0.85, buff=0.15)

        with self.voiceover(
            text="El espacio se aplana a una sola línea."
        ) as tracker:
            self.play(FadeIn(det_eq), run_time=tracker.duration * 0.5)
            self.play(Write(msg), run_time=tracker.duration * 0.5)