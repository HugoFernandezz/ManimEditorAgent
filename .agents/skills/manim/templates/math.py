"""
Math derivation template.

Demonstrates:
  - MathTex with isolated parts for color-coding
  - TransformMatchingTex for clean morphing between equations
  - Plotting a function with axes and label

Run:
    manim -pql math.py MathScene
"""

from manim import *


class MathScene(Scene):
    def construct(self):
        # ---------- Equation derivation ----------
        eq1 = MathTex(r"a^2", r"+", r"b^2", r"=", r"c^2")
        eq1[0].set_color(BLUE)
        eq1[2].set_color(GREEN)
        eq1[4].set_color(YELLOW)
        eq1.scale(1.5).to_edge(UP, buff=0.8)

        self.play(Write(eq1))
        self.wait(1.5)  # let the viewer read it

        eq2 = MathTex(r"c^2", r"-", r"a^2", r"=", r"b^2")
        eq2[0].set_color(YELLOW)
        eq2[2].set_color(BLUE)
        eq2[4].set_color(GREEN)
        eq2.scale(1.5).to_edge(UP, buff=0.8)

        self.play(TransformMatchingTex(eq1, eq2))
        self.wait(1.5)

        # ---------- Companion graph ----------
        ax = Axes(
            x_range=[-3, 3, 1],
            y_range=[-1, 5, 1],
            x_length=7,
            y_length=4,
            axis_config={"include_numbers": True, "include_tip": True},
        ).shift(DOWN * 0.5)

        graph = ax.plot(lambda x: x ** 2, x_range=[-2.2, 2.2], color=BLUE)
        graph_label = ax.get_graph_label(graph, label=MathTex(r"y = x^2"))

        self.play(Create(ax), run_time=1.5)
        self.play(Create(graph), Write(graph_label))
        self.wait()

        # ---------- Highlight a point ----------
        x_val = 1.5
        dot = Dot(ax.coords_to_point(x_val, x_val ** 2), color=RED)
        v_line = ax.get_vertical_line(dot.get_center(), color=YELLOW)
        h_line = ax.get_horizontal_line(dot.get_center(), color=YELLOW)

        self.play(Create(dot))
        self.play(Create(v_line), Create(h_line))
        self.wait(1.5)

        # ---------- Fade out ----------
        self.play(
            *[FadeOut(m) for m in [eq2, ax, graph, graph_label, dot, v_line, h_line]]
        )
        self.wait(0.5)
