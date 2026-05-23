from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService
import numpy as np


class Scene02(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="es"))

        # Background grid (deformable cuadrícula)
        plane = NumberPlane(
            x_range=[-8, 8, 1],
            y_range=[-5, 5, 1],
            background_line_style={
                "stroke_color": BLUE_D,
                "stroke_width": 1,
                "stroke_opacity": 0.4,
            },
            faded_line_ratio=0,
        )

        # Unit square (semitransparent blue)
        square = Polygon(
            [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        ).set_fill(BLUE, opacity=0.5).set_stroke(BLUE, width=2)

        # Basis vectors i-hat (green) and j-hat (red)
        i_hat = Arrow(
            ORIGIN, [1, 0, 0], buff=0, color=GREEN,
            stroke_width=6, max_tip_length_to_length_ratio=0.25,
        )
        j_hat = Arrow(
            ORIGIN, [0, 1, 0], buff=0, color=RED,
            stroke_width=6, max_tip_length_to_length_ratio=0.25,
        )

        # Transformation matrix [[2,1],[0,2]] -> i_hat:(2,0), j_hat:(1,2)
        matrix = np.array([[2, 1, 0], [0, 2, 0], [0, 0, 1]])
        new_i = Arrow(
            ORIGIN, [2, 0, 0], buff=0, color=GREEN,
            stroke_width=6, max_tip_length_to_length_ratio=0.25,
        )
        new_j = Arrow(
            ORIGIN, [1, 2, 0], buff=0, color=RED,
            stroke_width=6, max_tip_length_to_length_ratio=0.25,
        )

        with self.voiceover(
            text="Esta matriz es una máquina que transforma el espacio."
        ) as tracker:
            self.play(
                FadeIn(plane),
                FadeIn(square),
                GrowArrow(i_hat),
                GrowArrow(j_hat),
                run_time=tracker.duration,
            )

        with self.voiceover(
            text="La cuadrícula se deforma y el cuadrado se vuelve paralelogramo."
        ) as tracker:
            self.play(
                ApplyMatrix(matrix, plane),
                ApplyMatrix(matrix, square),
                Transform(i_hat, new_i),
                Transform(j_hat, new_j),
                run_time=tracker.duration,
            )

        with self.voiceover(
            text="Algo ha cambiado claramente, pero ¿cuánto?"
        ) as tracker:
            self.wait(tracker.duration)