"""
Basic 2D Manim scene template.

Run:
    manim -pql basic.py BasicScene
"""

from manim import *


class BasicScene(Scene):
    def construct(self):
        # Title
        title = Text("Title goes here", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))
        self.wait(0.5)

        # A single focal shape
        circle = Circle(radius=1.5, color=BLUE, fill_opacity=0.4)
        self.play(Create(circle))
        self.wait(0.5)

        # Transform / interact
        square = Square(side_length=2.5, color=YELLOW, fill_opacity=0.4)
        self.play(ReplacementTransform(circle, square))
        self.wait(0.5)

        # Move it
        self.play(square.animate.shift(RIGHT * 2).rotate(PI / 4))
        self.wait()

        # Clean exit
        self.play(FadeOut(title), FadeOut(square))
        self.wait(0.5)
