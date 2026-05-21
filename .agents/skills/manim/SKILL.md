---
name: manim
description: |
  Trigger when: (1) the user wants to create a math/science/explainer animation or video, (2) the user mentions "Manim", "ManimCE", "ManimGL", "3b1b" or "3Blue1Brown style", (3) code in the conversation imports `from manim import *` or `from manimlib import *`, (4) the user asks to render a `Scene` class or run `manim`/`manimgl` CLI commands, (5) the user wants to visualize a mathematical concept, equation, geometric idea, or physics simulation.

  End-to-end Manim expert. Detects the installed version (Community Edition vs ManimGL), plans the scene when needed, writes code from tested templates, renders with an automated verify loop, and resolves the common LaTeX / ffmpeg / cairo / pango failures. Covers ManimCE (current, community) and ManimGL (3b1b, interactive). Includes the real 3Blue1Brown color palette, narrative patterns, and voiceover synchronization.
---

# Manim Skill

A single, complete workflow for turning an animation idea into a rendered, verified Manim video.

## Required workflow

Do not skip steps. Each one is cheap and prevents a class of failure.

### 1. Detect the environment

Before writing or running any Manim code:

```bash
python scripts/check_env.py
```

This reports the installed Manim version (CE / GL / both / none), and whether `ffmpeg`, a working LaTeX (`latex` and `dvisvgm`) and `pango` are reachable. If anything required is missing, stop and tell the user what to install — do not attempt to render.

### 2. Decide CE vs GL

- Only `manim` (Community) installed → ManimCE. Read `references/api-cheatsheet.md`.
- Only `manimgl` installed → ManimGL. Read `references/api-cheatsheet.md` then `references/manimgl-diff.md`.
- Both installed and the user did not specify → ask. Default to ManimCE unless the user said "3b1b", "interactive mode", "checkpoint_paste", or "self.embed".
- The user provided code → infer from the imports, do not switch versions.

### 3. Plan (only if the request is vague)

Skip planning when the request is concrete ("animate a sine wave"). When it is vague ("visualize Fourier series"), use `AskUserQuestion` to gather, in one round:

- audience level (high school / undergrad calculus / advanced)
- length target (short ~30s, medium 1-3 min, long 5 min+)
- focus (intuition / proof / application)
- narration (yes via `manim-voiceover` / no)

Then write a 3-7 line scene outline in plain prose before any code. Do not produce a long `scenes.md` document unless the user asks for one — the outline is enough to start coding.

### 4. Write

Copy the matching template from `templates/` and modify it. Do not write from scratch:

- `basic.py` — single 2D `Scene` with shapes, text, basic animations.
- `math.py` — LaTeX equations, color-coded math, derivations (uses `MathTex` / `TransformMatchingTex`).
- `threed.py` — `ThreeDScene` with surfaces, camera rotation, parametric curves.
- `voiceover.py` — narration synced to animations via `manim-voiceover`.

For 3b1b-style aesthetics, pull colors and font choices from `references/3b1b-style.md`. Do not invent hex codes.

### 5. Render and verify (mandatory)

After writing, always:

```bash
python scripts/render_verify.py <file.py> <SceneName>
```

This renders at `-ql --save_last_frame` (low quality, fast, single PNG), parses stderr, and reports either OK with the path to the last frame, or a categorized error. If it fails:

1. Match the error against `references/troubleshooting.md`.
2. Apply the fix.
3. Re-run `render_verify.py`.
4. Repeat until clean. Maximum 3 cycles before stopping and reporting to the user.

### 6. Final render

Once the low-quality render is clean and the user is happy with the composition:

```bash
manim -pqh <file.py> <SceneName>          # ManimCE, 1080p preview
manimgl <file.py> <SceneName> -w          # ManimGL, write to file
```

## Anti-patterns to avoid

- **Do not** call `self.play(mob.animate.X())` on a mobject that was never added or animated in. Use `self.add(mob)` or `self.play(Create(mob))` first.
- **Do not** reuse a mobject after `Transform(a, b)` — it mutates `a` in place. Use `ReplacementTransform(a, b)` and reference `b` afterwards.
- **Do not** leave updaters attached across unrelated animations. Call `mob.clear_updaters()` before the next `self.play()` block if the updater is no longer needed — orphan updaters are the #1 cause of jittery output.
- **Do not** render at `-qh`/`-qk` during iteration. Always `-ql` until the scene is correct.
- **Do not** mix `from manim import *` and `from manimlib import *` in the same project. They are not API-compatible.
- **Do not** hand-position mobjects with magic numbers when `.next_to()`, `.to_edge()`, `.align_to()` or `VGroup(...).arrange()` would do it. Magic numbers break when run_time, font size, or aspect ratio changes.
- **Do not** use `Tex(r"$x$")` in ManimCE for math — use `MathTex(r"x")`. `Tex` is text mode by default in CE.

## When the user wants 3b1b-style

3Blue1Brown is more than colors. The style has three pillars; see `references/3b1b-style.md` for details:

1. **Visual continuity** — `Transform` over `FadeOut + FadeIn` whenever the same idea persists.
2. **Pause for insight** — every `aha` deserves a `self.wait(1.5)` or longer.
3. **Two representations** — show algebra and geometry of the same thing side-by-side.

## References

- `references/api-cheatsheet.md` — ManimCE essential API, dense and example-driven
- `references/manimgl-diff.md` — ManimGL deltas vs CE (imports, `frame`, `ShowCreation`, interactive mode)
- `references/3b1b-style.md` — Real 3b1b color hex values, fonts, narrative patterns, pacing
- `references/narration.md` — `manim-voiceover` setup and synchronized speech
- `references/troubleshooting.md` — Error → diagnosis → fix table for the 15 most common failures

## Templates

- `templates/basic.py`
- `templates/math.py`
- `templates/threed.py`
- `templates/voiceover.py`

## Scripts

- `scripts/check_env.py` — environment detection, run first
- `scripts/render_verify.py` — render at low quality, parse stderr, report

## Tested with

- ManimCE 0.18.x
- ManimGL 1.7.x
- manim-voiceover 0.3.x
- Python 3.10+

If the installed version differs significantly, check the official changelogs before trusting these templates.
