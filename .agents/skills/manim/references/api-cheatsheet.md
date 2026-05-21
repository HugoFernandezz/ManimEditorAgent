# ManimCE API Cheatsheet

Dense reference. Every snippet runs as-is inside `construct()` of a `Scene`.

## Scene skeleton

```python
from manim import *

class MyScene(Scene):
    def construct(self):
        # Build mobjects, position them, then animate.
        c = Circle(color=BLUE).shift(LEFT)
        s = Square(color=YELLOW).shift(RIGHT)
        self.play(Create(c), Create(s))
        self.wait()
```

Scene subclasses:
- `Scene` — default 2D.
- `MovingCameraScene` — gives you `self.camera.frame` for zoom/pan.
- `ThreeDScene` — 3D, see `references/api-cheatsheet.md` 3D section.
- `ZoomedScene` — picture-in-picture zoom window.

## Mobjects you will use 90% of the time

### Geometry
```python
Circle(radius=1, color=BLUE, fill_opacity=0.5)
Square(side_length=2)
Rectangle(width=4, height=2)
Triangle()
Polygon([-1, 0, 0], [1, 0, 0], [0, 2, 0])
Dot(point=ORIGIN, radius=0.08)
Line(start=LEFT, end=RIGHT)
Arrow(start=ORIGIN, end=RIGHT*2, buff=0)        # buff=0 critical, else shrinks
DashedLine(LEFT, RIGHT)
Vector([1, 2])                                   # arrow from origin
```

### Text & math
```python
Text("Hello", font_size=48, color=WHITE)         # uses pango, supports any font
MarkupText("<b>bold</b> normal <i>italic</i>")   # pango markup
MathTex(r"e^{i\pi} + 1 = 0")                     # math mode auto
MathTex(r"a", r"+", r"b", r"=", r"c")            # split into parts for animation
Tex(r"Plain text with $x^2$ inline math")        # text mode, $...$ for math
```

`MathTex` indexing: each comma-separated argument is one submobject accessible by `eq[0]`, `eq[1]`, etc. Use this for color-coding and `TransformMatchingTex`.

### Coordinate systems
```python
ax = Axes(
    x_range=[-3, 3, 1],
    y_range=[-2, 2, 1],
    axis_config={"include_numbers": True},
)
graph = ax.plot(lambda x: x**2, color=YELLOW)
label = ax.get_graph_label(graph, label="x^2")
self.add(ax, graph, label)

# Parametric
curve = ax.plot_parametric_curve(
    lambda t: np.array([np.cos(t), np.sin(t), 0]),
    t_range=[0, TAU],
)
```

`NumberPlane` is like `Axes` with a full grid — use for vector visualizations.

## Animations

### Creation
```python
Create(mob)                       # draws stroke progressively (vector mobjects)
Write(mob)                        # for Text and Tex — pen-stroke effect
DrawBorderThenFill(mob)           # border first, then fill
FadeIn(mob, shift=UP, scale=0.5)  # appear with optional motion
GrowFromCenter(mob)
SpinInFromNothing(mob)
```

### Movement / transformation
```python
mob.animate.shift(RIGHT * 2)               # any method becomes animated
mob.animate.scale(2).rotate(PI/4)          # chainable
Transform(a, b)                            # mutates a into b — DO NOT reuse a after
ReplacementTransform(a, b)                 # a is removed, b takes its place — prefer this
TransformMatchingTex(eq1, eq2)             # smart morph that keeps matching glyphs
TransformMatchingShapes(a, b)              # for non-Tex mobjects
ApplyMethod(mob.set_color, RED)            # older syntax, mob.animate is preferred
```

### Disappearance
```python
FadeOut(mob, shift=DOWN)
Uncreate(mob)                              # reverse of Create
Unwrite(mob)
```

### Grouping animations
```python
self.play(AnimationGroup(a1, a2, a3, lag_ratio=0))           # simultaneous
self.play(LaggedStart(a1, a2, a3, lag_ratio=0.3))            # staggered
self.play(Succession(a1, a2, a3))                            # one after another
```

`lag_ratio`: 0 = simultaneous, 1 = fully sequential, intermediate values overlap.

### Timing per animation
```python
self.play(Create(c), run_time=2)
self.play(c.animate.shift(UP), rate_func=smooth)      # default
self.play(c.animate.shift(UP), rate_func=there_and_back)
self.play(c.animate.shift(UP), rate_func=linear)
self.play(c.animate.shift(UP), rate_func=rate_functions.ease_in_out_cubic)
```

## Positioning

```python
mob.move_to(ORIGIN)                # absolute
mob.shift(UP * 2 + LEFT)           # relative
mob.next_to(other, RIGHT, buff=0.5)
mob.to_edge(UP, buff=0.3)          # snap to scene edge
mob.to_corner(UR)
mob.align_to(other, LEFT)          # align one edge
mob.scale(1.5)
mob.rotate(PI / 4)                 # radians

VGroup(a, b, c).arrange(RIGHT, buff=0.5)
VGroup(a, b, c, d).arrange_in_grid(rows=2, cols=2, buff=0.4)
```

Direction constants: `UP`, `DOWN`, `LEFT`, `RIGHT`, `UL`, `UR`, `DL`, `DR`, `ORIGIN`, `IN`, `OUT` (3D only).

## Color

```python
# Built-in palette — use these names for consistency
RED, ORANGE, YELLOW, GREEN, TEAL, BLUE, PURPLE, PINK, MAROON, GOLD
# Variants: BLUE_A (lightest) → BLUE_E (darkest), etc. for most colors
WHITE, BLACK, GRAY, LIGHT_GRAY, DARK_GRAY

# Custom
mob.set_color("#FF5733")
mob.set_fill(BLUE, opacity=0.5)
mob.set_stroke(YELLOW, width=4)

# Gradient
mob.set_color_by_gradient(BLUE, YELLOW, RED)
mob.set_fill_by_gradient(GREEN, PURPLE)

# Color part of MathTex
eq = MathTex(r"E", r"=", r"m", r"c^2")
eq[0].set_color(BLUE)
eq[2].set_color(GREEN)
eq[3].set_color(YELLOW)
```

For real 3Blue1Brown palette hex values, see `references/3b1b-style.md`.

## Updaters and ValueTracker

Updaters fire every frame and let mobjects depend on other mobjects or values.

```python
# Label that follows a dot
dot = Dot()
label = always_redraw(lambda: MathTex("P").next_to(dot, UP))
self.add(dot, label)
self.play(dot.animate.shift(RIGHT * 3))

# ValueTracker — animatable number
t = ValueTracker(0)
number = always_redraw(
    lambda: DecimalNumber(t.get_value(), num_decimal_places=2).to_edge(UP)
)
self.add(number)
self.play(t.animate.set_value(10), run_time=3)

# Always remove updaters when you no longer need them
mob.clear_updaters()
```

`always_redraw` is the safest pattern — it rebuilds the mobject each frame and avoids stale-state bugs. Use it instead of raw `add_updater` whenever possible.

## 3D (ThreeDScene)

```python
class MyScene3D(ThreeDScene):
    def construct(self):
        self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES)
        axes = ThreeDAxes()
        surface = Surface(
            lambda u, v: np.array([u, v, np.sin(u) * np.cos(v)]),
            u_range=[-3, 3], v_range=[-3, 3],
            resolution=(30, 30),
        )
        surface.set_style(fill_opacity=0.7, stroke_width=0.5)
        self.add(axes, surface)
        self.begin_ambient_camera_rotation(rate=0.2)
        self.wait(5)
```

Key 3D APIs: `set_camera_orientation(phi, theta, gamma)`, `begin_ambient_camera_rotation`, `move_camera`, `Surface`, `ParametricFunction`, `Sphere`, `Cube`, `Torus`, `Arrow3D`.

`add_fixed_in_frame_mobjects(mob)` keeps a mobject (typically a title) anchored to the screen during 3D camera moves.

## CLI

```bash
manim -pql scene.py MyScene             # preview, low quality (480p, 15fps)
manim -pqm scene.py MyScene             # medium (720p, 30fps)
manim -pqh scene.py MyScene             # high (1080p, 60fps)
manim -pqk scene.py MyScene             # 4k

manim --save_last_frame scene.py MyScene    # PNG of last frame only — great for iteration
manim --format=gif scene.py MyScene
manim --flush_cache scene.py MyScene        # nuke cache (use after LaTeX/Text changes)
manim checkhealth                            # verify install
```

Quality matters: `-ql` renders ~10x faster than `-qh`. Iterate at `-ql`.

## Common patterns

### Color-coded equation derivation
```python
eq1 = MathTex(r"a^2 + b^2", r"=", r"c^2")
eq2 = MathTex(r"c^2 - a^2", r"=", r"b^2")
eq1[0].set_color_by_tex("a", BLUE)
eq1[0].set_color_by_tex("b", GREEN)
self.play(Write(eq1))
self.play(TransformMatchingTex(eq1, eq2))
```

### Trace a moving dot
```python
dot = Dot().move_to(LEFT * 3)
trace = TracedPath(dot.get_center, stroke_color=YELLOW)
self.add(dot, trace)
self.play(dot.animate.shift(RIGHT * 6), run_time=3)
```

### Vector that updates with a ValueTracker
```python
plane = NumberPlane()
angle = ValueTracker(0)
arrow = always_redraw(
    lambda: Arrow(
        ORIGIN,
        2 * np.array([np.cos(angle.get_value()), np.sin(angle.get_value()), 0]),
        buff=0, color=YELLOW,
    )
)
self.add(plane, arrow)
self.play(angle.animate.set_value(TAU), run_time=4)
```

## Constants worth knowing

```python
PI, TAU, DEGREES                # math
ORIGIN, UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT
config.frame_width              # ~14.22 in scene units, default
config.frame_height             # ~8.0
config.pixel_width, config.pixel_height
```

Frame: x ∈ [-7.11, 7.11], y ∈ [-4, 4] by default. Anything outside is clipped.
