# 3Blue1Brown Style Guide

Hex values, font choices, narrative patterns and pacing taken from `3b1b/manim` source and observed across `3b1b/videos`. Use these to make output look like 3b1b instead of generic Manim.

## Colors

The actual constants from `manimlib/constants.py`. The Community Edition has the same names with slightly different shades — these are the originals.

| Name | Hex | Use |
|---|---|---|
| `BLUE_E` | `#1C758A` | Darkest blue, backgrounds, secondary axes |
| `BLUE_D` | `#29ABCA` | Standard blue for emphasis |
| `BLUE_C` | `#58C4DD` | Default `BLUE` — primary visual element |
| `BLUE_B` | `#9CDCEB` | Light blue, highlights |
| `BLUE_A` | `#C7E9F1` | Lightest, washes |
| `TEAL_C` | `#5CD0B3` | Default `TEAL` — secondary objects |
| `GREEN_C` | `#83C167` | Default `GREEN` — positive / correct |
| `YELLOW_C` | `#FFFF00` | Default `YELLOW` — emphasis, key terms |
| `GOLD_C` | `#F0AC5F` | Default `GOLD` — important constants |
| `RED_C` | `#FC6255` | Default `RED` — wrong / warning / contrast |
| `MAROON_C` | `#C55F73` | Default `MAROON` — softer red |
| `PURPLE_C` | `#9A72AC` | Default `PURPLE` — abstract concepts |
| `LIGHT_GRAY` | `#BBBBBB` | Inert text, faded reference |
| `GRAY` | `#888888` | Mid-tone |
| `DARK_GRAY` | `#444444` | Inactive elements |

Background is **black** (`#000000`), not white. Don't fight this — it is the look.

Default text color is **off-white**, not pure white: `WHITE = "#FFFFFF"` in code, but stroke widths and a slight glow effect make pure white read as "default". Don't override unless you have a reason.

### Palette principles

1. **One accent color per scene.** Pick ONE of BLUE / YELLOW / GREEN as the focus. Use others sparingly for contrast.
2. **Color encodes meaning, not decoration.** If `x` is blue in scene 1, it stays blue in scene 5.
3. **Red is reserved for errors, warnings, or wrong answers.** Don't use it for ordinary objects.

## Fonts

3b1b uses LaTeX directly for math (Computer Modern, the default). For plain `Text(...)`:

- **Default** — `Text("...")` uses the system default. Don't override unless required.
- **Code / mono** — `Text("def f(x):", font="Consolas")` or `"Menlo"`, `"Monaco"`. 
- **Serif body** — `Text("...", font="CMU Serif")` if the LaTeX font is installed system-wide.

Avoid sans-serif fonts for math-adjacent content. The aesthetic is academic.

## Narrative patterns

Each scene should fit one of these arcs. Pick consciously.

### 1. Mystery → Investigation → Resolution

1. Present a paradox or counterintuitive result (`MathTex` of a strange equation, or a visual oddity).
2. Pause (`self.wait(2)`). Let the viewer be confused.
3. Slowly build the explanation — usually by zooming in, decomposing, or showing the geometric meaning.
4. Land on the "aha" moment with emphasis: stroke flash, scale up, or sudden color change.

Use for: Euler's identity, Bayes' theorem, infinite series, the Monty Hall problem.

### 2. Two perspectives → unity

1. Show concept A (e.g. algebraic).
2. Move it aside, show concept B (e.g. geometric).
3. Animate them into the same position — `TransformMatchingTex` or `ReplacementTransform`.
4. Reveal they are the same.

Use for: dot product as projection AND coordinate sum, determinant as area AND product of eigenvalues.

### 3. Wrong → less wrong → right

1. Show the naive guess.
2. Break it with a counterexample.
3. Patch it. Break it again.
4. Arrive at the correct formulation.

Use for: definitions of limit, derivative, area, distance metrics.

### 4. Build up → payoff

1. Introduce simple pieces.
2. Combine them.
3. Combine the combinations.
4. Reveal the structure (Fourier series, neural network forward pass, RSA).

## Pacing rules

- **Wait after a key reveal.** Minimum `self.wait(1.5)`. 3b1b often waits 2–3 seconds. Silence is part of the explanation.
- **Animate transitions, don't cut.** Prefer `ReplacementTransform` over `FadeOut` + `FadeIn` when the same idea persists.
- **Vary run_time.** Quick movements (`run_time=0.5`) for setup, slower (`run_time=2`) for insight moments.
- **End every scene cleanly.** Either fade out everything, or transform the final state into the setup of the next scene.

## Visual continuity rules

- **Persistent objects stay on screen.** If a variable `x` was blue and labelled, it stays blue and labelled across scenes.
- **Transform, don't replace.** When `f(x) = x^2` becomes `f(x) = x^3`, use `TransformMatchingTex` — the `f(x) =` part should stay put while the `^2` morphs into `^3`.
- **Group related objects with `VGroup`.** Move them together. Don't animate parts independently when they should feel like one thing.

## Typography for math

- Use `MathTex` for any equation. Never `Text("E = mc^2")`.
- Use raw strings: `r"\frac{1}{2}"`, not `"\\frac{1}{2}"`.
- Split equations by parts for animation:
  ```python
  eq = MathTex(r"\int_a^b", r"f(x)", r"\,dx", r"=", r"F(b)", r"-", r"F(a)")
  ```
  Now `eq[1]` is the integrand, `eq[4]` and `eq[6]` are the antiderivative evaluations.
- Color the parts that mean something. Don't color everything.

## Scene composition rules

- **Title at top.** `title.to_edge(UP, buff=0.5)`.
- **Equations centered vertically** unless they need space for graphs below.
- **Graphs on one side, text/equations on the other.** Avoid stacking unrelated content.
- **Leave 0.5 unit margins.** Don't push to the absolute edge.
