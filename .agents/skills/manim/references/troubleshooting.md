# Troubleshooting

Error → diagnosis → fix. Ordered by frequency. Match the error message snippet against the headings.

## 1. `LaTeX Error: File 'standalone.cls' not found.`

**Cause:** LaTeX is installed but missing the `standalone` package that Manim uses to render math.

**Fix (Linux):**
```bash
sudo apt-get install texlive-latex-extra texlive-fonts-extra texlive-latex-recommended texlive-science tipa
```

**Fix (macOS, MacTeX):** Already included. If broken, `sudo tlmgr update --self && sudo tlmgr install standalone preview doublestroke`.

**Fix (Windows, MiKTeX):** Open MiKTeX Console → Packages → install `standalone`, `preview`, `doublestroke`, `setspace`, `relsize`, `everysel`, `physics`. Or `mpm --install=standalone preview doublestroke`.

## 2. `latex error converting to dvi`

**Cause:** Syntax error in the LaTeX string passed to `MathTex` / `Tex`.

**Diagnosis:** Look at the `.log` file that Manim mentions in the traceback — it contains the actual LaTeX error.

**Common causes:**
- Forgot raw string: `MathTex("\\frac{1}{2}")` works, `MathTex("\frac{1}{2}")` does not. Always use `r"..."`.
- Unescaped `&`, `%`, `#`, `_` in `Tex(...)` text mode. Escape with `\&`, `\%`, `\#`, `\_`.
- Math command used outside math mode. In `Tex`, wrap math in `$...$`. In `MathTex`, you're already in math mode.
- Missing package: e.g. `\mathbb{R}` needs `amssymb`. Add `tex_template` with extra preamble or install `texlive-science`.

## 3. `ModuleNotFoundError: No module named 'manimpango'`

**Cause:** Pango bindings failed to install.

**Fix:**
```bash
pip install --upgrade manimpango
# On Linux, you may need:
sudo apt-get install libpango1.0-dev
```

If still failing on macOS Apple Silicon:
```bash
brew install pango pkg-config
pip install --no-cache-dir manimpango
```

## 4. `ffmpeg: command not found` or `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`

**Fix:**
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: download from https://ffmpeg.org/download.html, add the `bin/` folder to `PATH`.

Verify: `ffmpeg -version`.

## 5. `Cairo.Error` or import failure on `cairo`

**Cause:** Native Cairo library missing.

**Fix:**
- Linux: `sudo apt-get install libcairo2-dev pkg-config python3-dev`
- macOS: `brew install cairo`
- Windows: usually shipped with Pillow / pycairo wheel — try `pip install --upgrade pycairo`.

## 6. `TransformMatchingTex` produces garbled morphing

**Cause:** The matcher pairs glyphs by visual similarity. If the same symbol appears multiple times, it pairs wrong.

**Fix:** Split your `MathTex` into explicit parts so the matcher pairs by index, not visual content.

```python
# Bad
eq1 = MathTex(r"x^2 + 2x + 1")
eq2 = MathTex(r"(x + 1)^2")

# Good — explicit parts
eq1 = MathTex(r"x^2", r"+", r"2x", r"+", r"1")
eq2 = MathTex(r"(", r"x", r"+", r"1", r")", r"^2")
```

Or pass `key_map={"old": "new"}` to `TransformMatchingTex`.

## 7. Render cache shows old version after editing LaTeX

**Cause:** Manim caches rendered LaTeX as SVG. Cache key sometimes misses small changes.

**Fix:**
```bash
manim --flush_cache scene.py MyScene
```

Or delete `media/Tex/` and re-render.

## 8. Mobject is invisible / off-screen

**Cause:** Position is outside the default frame. Default frame in CE: x ∈ [-7.11, 7.11], y ∈ [-4, 4].

**Fix:** 
- Add to scene with `self.add(mob)` — easy to forget.
- Check position: `print(mob.get_center())`.
- Bring back: `mob.move_to(ORIGIN)` or `mob.to_edge(UP)`.
- For 3D scenes, ensure camera orientation includes the mobject — use `self.set_camera_orientation(...)` before placing.

## 9. Animation has jitter / objects ghost / wrong positions

**Cause:** Orphan updater still attached to a mobject after you no longer need it.

**Fix:**
```python
mob.clear_updaters()
```
Call this before any `self.play()` that should NOT keep the previous update behavior. Or use `always_redraw(...)` which is scoped automatically.

## 10. `AttributeError: 'Mobject' object has no attribute 'animate'` (or similar)

**Cause:** Using ManimGL syntax in ManimCE or vice versa.

**Fix:** Check imports.
- `from manim import *` → ManimCE.
- `from manimlib import *` → ManimGL.

Common slip-ups:
- `Create` (CE) vs `ShowCreation` (GL).
- `MathTex` (CE) vs `Tex` (GL).
- `self.camera.frame` (CE MovingCameraScene) vs `self.frame` (GL).

## 11. `manim` command not found (Windows)

**Cause:** Python's `Scripts/` dir not in `PATH`.

**Fix:**
```bash
python -m manim -pql scene.py MyScene
```
Or add `C:\Users\<you>\AppData\Local\Programs\Python\Python3X\Scripts` to `PATH`.

## 12. Black rectangle instead of text

**Cause:** Pango can't find the font you specified.

**Fix:**
- List available fonts: `manim --help` doesn't list, but `fc-list` (Linux/macOS) or check Font Book / Windows Fonts.
- Use a font you know is installed: omit `font=` and accept the system default.
- If you need a specific font, install it system-wide first.

## 13. `ValueError: zero-size array to reduction operation` on `plot`

**Cause:** `t_range` is empty or the function returns NaN/inf inside the range.

**Fix:** Check `t_range`. For singularities (e.g., `1/x` at 0), restrict the range:
```python
ax.plot(lambda x: 1/x, x_range=[0.1, 5])   # avoid 0
```

## 14. `manim-voiceover` fails with no audio output

**Cause:** Speech service can't reach the provider, or API key missing.

**Fix:**
- gTTS: check internet.
- OpenAI: `export OPENAI_API_KEY=...`
- Azure: `export AZURE_SUBSCRIPTION_KEY=...` and `export AZURE_SERVICE_REGION=...`
- Check `media/voiceovers/` is being created — if not, the service failed before caching.

## 15. Final render is fine but `-ql` looks wrong (or vice versa)

**Cause:** Quality flags change `pixel_width`, `pixel_height`, and `frame_rate`. Layouts that depend on these via `config.*` will differ.

**Fix:** Position everything with scene-unit math (the default frame is always ~14.22 × 8 scene units), not pixels. Don't read `config.pixel_*` for layout.

## Generic debugging recipe

When stuck:

1. Run `python scripts/check_env.py` to verify the toolchain.
2. Reduce the scene to the smallest failing case (one mobject, one animation).
3. Run with `-v DEBUG` for verbose output: `manim -ql -v DEBUG scene.py MyScene`.
4. Check the `.log` file under `media/` for LaTeX errors.
5. Try `--flush_cache` if behavior is inconsistent with the code.
