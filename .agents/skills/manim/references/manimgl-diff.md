# ManimGL — deltas vs ManimCE

ManimGL is Grant Sanderson's (3b1b) OpenGL-based fork. It is faster, supports interactive development with `self.embed()`, but the API differs from Community Edition in concrete ways. Read this AFTER `api-cheatsheet.md` if the project uses ManimGL.

## Import and CLI

```python
# ManimGL
from manimlib import *
```

```bash
manimgl scene.py MyScene             # render and preview (default behavior)
manimgl scene.py MyScene -w           # write to file
manimgl scene.py MyScene -l           # low quality
manimgl scene.py MyScene -hd          # 1080p
manimgl scene.py MyScene -uhd         # 4k
manimgl scene.py MyScene -se 25       # start interactive shell at line 25
```

There is no `-pql` style flag. Quality is a single flag, not combined with preview.

## API differences (the ones that bite)

| Concept | ManimCE | ManimGL |
|---|---|---|
| Default scene class | `Scene` | `InteractiveScene` |
| Create animation | `Create(mob)` | `ShowCreation(mob)` |
| Math text | `MathTex(r"x^2")` | `Tex(R"x^2")` (raw string with capital R) |
| Plain text math wrapper | `Tex(r"$x$")` | `Tex(R"x")` (math by default) |
| Camera frame | `self.camera.frame` (in `MovingCameraScene`) | `self.frame` (always available) |
| Reorient camera in 3D | `self.set_camera_orientation(phi=..., theta=...)` | `self.frame.reorient(theta, phi, gamma)` (note arg order) |
| Fix mobject to screen in 3D | `self.add_fixed_in_frame_mobjects(mob)` | `mob.fix_in_frame()` |
| Color map on Tex | `set_color_by_tex` | `t2c={"x": BLUE}` arg on `Tex(...)` |
| Save last frame | `manim --save_last_frame ...` | not built-in — use `-w` + frame extraction |

## Interactive mode (the killer feature)

```bash
manimgl scene.py MyScene -se 30
```

Drops into an IPython shell *with scene state preserved* at line 30. Inside:

```python
# Copy code lines to clipboard, then:
checkpoint_paste()                # run them with animations
checkpoint_paste(skip=True)       # run instantly, no animation
checkpoint_paste(record=True)     # write to file as you iterate
touch()                           # mark current state as a checkpoint to return to
```

`self.embed()` placed anywhere in `construct()` opens the shell at that point too:

```python
def construct(self):
    c = Circle()
    self.play(ShowCreation(c))
    self.embed()   # drop into shell here
```

## Camera (`self.frame`)

The frame is a mobject. You animate it like any other.

```python
# Static reorientation (theta, phi, gamma, center=ORIGIN, height=8)
self.frame.reorient(30, 70, 0)

# Animated camera move
self.play(self.frame.animate.reorient(60, 80, 0).move_to(target))

# Zoom by changing height
self.play(self.frame.animate.set_height(4))     # zoom in (smaller height = closer)
```

Argument order for `reorient` is `(theta, phi, gamma, center, height)` — *not* `(phi, theta)` like ManimCE.

## Tex with t2c (text-to-color)

```python
eq = Tex(
    R"E = mc^2",
    t2c={"E": BLUE, "m": GREEN, "c": YELLOW},
)
self.play(Write(eq))
```

`t2c` matches substrings. For overlapping substrings, isolate them explicitly:

```python
eq = Tex(R"\sum_{n=1}^N n^2", isolate=["n", "N"])
eq.set_color_by_tex("n", BLUE)
```

## Styling extras

ManimGL has a few visual properties ManimCE doesn't:

```python
text.set_backstroke(BLACK, width=5)     # outline behind text for readability over busy backgrounds
sphere.set_gloss(0.5)                    # specular highlight (3D)
sphere.set_shadow(0.3)                   # shadow
```

## 3D specifics

```python
sphere = Sphere(radius=1).set_color(BLUE)
torus = Torus(r1=2, r2=0.5)

surface = ParametricSurface(
    lambda u, v: np.array([
        np.cos(u) * np.cos(v),
        np.cos(u) * np.sin(v),
        np.sin(u),
    ]),
    u_range=(0, TAU), v_range=(0, TAU),
)

self.set_floor_plane("xz")               # change which plane is "the floor"
```

## When to choose GL over CE

Choose ManimGL when:
- You want interactive development with `checkpoint_paste` / `self.embed`.
- You are reusing code from `3b1b/videos` (it is all ManimGL).
- You need OpenGL performance on complex 3D scenes.
- The user explicitly says "3b1b version" or "ManimGL".

Choose ManimCE otherwise. It has better docs, more active community, more plugins (including `manim-voiceover`), and is what most tutorials assume.

## Anti-patterns specific to GL

- Don't use `r"..."` for `Tex`. Use `R"..."`. `Tex` in GL treats lowercase `r` raw strings inconsistently with some LaTeX escapes — capital `R` is the convention in 3b1b's own code.
- Don't expect `Create`. Use `ShowCreation`. `Create` does not exist in GL.
- Don't call `self.add_fixed_in_frame_mobjects` — that's CE. Call `mob.fix_in_frame()`.
- `self.camera.frame` is not the GL way. `self.frame` is.
