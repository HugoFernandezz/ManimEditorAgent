"""
3D scene template.

Demonstrates:
  - ThreeDScene with camera orientation
  - 3D axes and a parametric surface
  - Ambient camera rotation
  - Fixed-in-frame title that does not rotate with the camera

Run:
    manim -pql threed.py ThreedScene
"""

from manim import *
import numpy as np


class ThreedScene(ThreeDScene):
    def construct(self):
        # Title that stays anchored to the screen, not the 3D world
        title = Text("z = sin(x) · cos(y)", font_size=36).to_edge(UP)
        self.add_fixed_in_frame_mobjects(title)
        self.play(Write(title))

        # Camera position
        self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES, zoom=0.9)

        # 3D axes
        axes = ThreeDAxes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            z_range=[-2, 2, 1],
        )

        # Parametric surface
        surface = Surface(
            lambda u, v: axes.c2p(u, v, np.sin(u) * np.cos(v)),
            u_range=[-3, 3],
            v_range=[-3, 3],
            resolution=(40, 40),
        )
        surface.set_style(fill_opacity=0.7, stroke_width=0.5)
        surface.set_fill_by_value(axes=axes, colors=[(BLUE_E, -2), (TEAL, 0), (YELLOW, 2)], axis=2)

        self.play(Create(axes))
        self.play(Create(surface), run_time=3)
        self.wait(0.5)

        # Slow rotation while the viewer absorbs the shape
        self.begin_ambient_camera_rotation(rate=0.15)
        self.wait(6)
        self.stop_ambient_camera_rotation()

        # Zoom in a bit
        self.move_camera(phi=55 * DEGREES, theta=-30 * DEGREES, zoom=1.2, run_time=2)
        self.wait()

        # Clean exit
        self.play(FadeOut(surface), FadeOut(axes), FadeOut(title))
        self.wait(0.3)
