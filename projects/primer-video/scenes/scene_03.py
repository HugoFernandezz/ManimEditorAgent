from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
import numpy as np


class Scene03(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="es"))

        # Background plane (continuity with previous transformation scene)
        plane = NumberPlane(
            x_range=[-7, 7, 1],
            y_range=[-4, 4, 1],
            background_line_style={"stroke_opacity": 0.3, "stroke_width": 1},
        )
        self.add(plane)

        # Basis vectors at their transformed positions (continuity)
        i_hat = Arrow(plane.c2p(0, 0), plane.c2p(2, 0), buff=0, color=GREEN, stroke_width=6)
        j_hat = Arrow(plane.c2p(0, 0), plane.c2p(1, 2), buff=0, color=RED, stroke_width=6)
        self.add(i_hat, j_hat)

        # Parallelogram vertices in plane coordinates
        A = plane.c2p(0, 0)
        B = plane.c2p(2, 0)
        C = plane.c2p(3, 2)
        D = plane.c2p(1, 2)

        parallelogram = Polygon(A, B, C, D)
        parallelogram.set_fill(YELLOW, opacity=0.4).set_stroke(YELLOW, width=2)

        # === Beat 3.1 ===
        with self.voiceover(
            text="Coloreamos el paralelogramo y medimos su área."
        ) as tracker:
            self.play(FadeIn(parallelogram), run_time=tracker.duration)

        # === Beat 3.2 ===
        base_line = Line(A, B)
        base_brace = Brace(base_line, direction=DOWN, buff=0.1)
        base_label = MathTex(r"\text{base} = 2", font_size=32).next_to(base_brace, DOWN, buff=0.1)

        # Lateral brace on left slanted edge (A -> D)
        left_line = Line(A, D)
        left_brace = Brace(left_line, direction=LEFT, buff=0.1)
        altura_label = MathTex(r"\text{altura} = 2", font_size=32).next_to(left_brace, LEFT, buff=0.1)

        area_eq = MathTex(
            r"\text{Área}", r"=", r"2", r"\times", r"2", r"=", r"4",
            r"=", r"\det\!\begin{pmatrix}2 & 1 \\ 0 & 2\end{pmatrix}",
            font_size=36,
        )
        area_eq.to_edge(DOWN, buff=0.4)

        with self.voiceover(
            text="Base dos por altura dos: el área es cuatro."
        ) as tracker:
            d = tracker.duration
            self.play(
                GrowFromCenter(base_brace),
                FadeIn(base_label),
                run_time=d * 0.3,
            )
            self.play(
                GrowFromCenter(left_brace),
                FadeIn(altura_label),
                run_time=d * 0.3,
            )
            self.play(FadeIn(area_eq), run_time=d * 0.4)

        # === Beat 3.3 ===
        four_token = area_eq[6]  # the "4"
        rect = SurroundingRectangle(four_token, color=YELLOW, buff=0.08)
        comment = Text("× 4 el área original", font_size=24, color=YELLOW)
        comment.next_to(area_eq, UP, buff=0.25)

        with self.voiceover(
            text="Cuatro: el valor exacto del determinante. No es casualidad."
        ) as tracker:
            d = tracker.duration
            self.play(Create(rect), run_time=d * 0.5)
            self.play(FadeIn(comment), run_time=d * 0.5)