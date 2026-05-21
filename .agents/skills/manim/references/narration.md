# Synchronized narration with manim-voiceover

`manim-voiceover` is the standard plugin for adding spoken narration to ManimCE animations, with the audio length driving animation timing automatically.

## Install

```bash
pip install "manim-voiceover[azure,gtts]"
# Or one provider at a time:
pip install "manim-voiceover[gtts]"           # free, gTTS (Google Translate)
pip install "manim-voiceover[openai]"         # OpenAI TTS
pip install "manim-voiceover[elevenlabs]"     # ElevenLabs
pip install "manim-voiceover[recorder]"       # record your own voice
```

System dependencies: `ffmpeg`, `sox` (for the recorder).

## Basic pattern

```python
from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

class Narrated(VoiceoverScene):
    def construct(self):
        self.set_speech_service(GTTSService(lang="en"))

        circle = Circle()

        with self.voiceover(text="Let's start with a circle.") as tracker:
            self.play(Create(circle), run_time=tracker.duration)

        with self.voiceover(text="Now we move it to the right.") as tracker:
            self.play(circle.animate.shift(RIGHT * 3), run_time=tracker.duration)

        with self.voiceover(text="And finally, we let it spin.") as tracker:
            self.play(Rotate(circle, TAU), run_time=tracker.duration)
```

Key idea: `tracker.duration` is the spoken audio length in seconds. Passing it as `run_time` ties the animation to the speech.

## Picking a service

| Service | Cost | Quality | Use when |
|---|---|---|---|
| `GTTSService` | free | acceptable | prototyping, drafts |
| `OpenAIService` | per char | high | production English narration |
| `AzureService` | per char | high, many voices/languages | non-English, voice variety |
| `ElevenLabsService` | per char | best | publishable production |
| `RecorderService` | free | your voice | final recordings |

### OpenAI example

```python
from manim_voiceover.services.openai import OpenAIService
self.set_speech_service(OpenAIService(voice="onyx", model="tts-1-hd"))
# Voices: alloy, echo, fable, onyx, nova, shimmer
```

Requires `OPENAI_API_KEY` env var.

### Azure example

```python
from manim_voiceover.services.azure import AzureService
self.set_speech_service(AzureService(voice="en-US-AriaNeural", style="default"))
```

Requires `AZURE_SUBSCRIPTION_KEY` and `AZURE_SERVICE_REGION`.

## SSML for prosody

OpenAI and Azure accept SSML for fine control of pauses and emphasis:

```python
with self.voiceover(
    text="""<speak>
        This is <emphasis level='strong'>important</emphasis>.
        <break time='500ms'/>
        Pay attention.
    </speak>"""
) as tracker:
    self.play(...)
```

## Bookmarks (precise timing inside one block)

```python
with self.voiceover(
    text="""Here is the equation: <bookmark mark='eq'/>
            and here is the result: <bookmark mark='res'/>."""
) as tracker:
    self.play(Write(equation), run_time=tracker.time_until_bookmark("eq"))
    self.play(Write(result), run_time=tracker.time_until_bookmark("res"))
```

## Caching

Audio is cached in `media/voiceovers/<hash>.mp3`. Edit text → new hash → re-synthesized. Identical text is cheap on re-runs.

## Common pitfalls

- **Don't use `run_time=` longer than `tracker.duration`** if you want audio to end with the animation. The narration will end early and you'll get silence at the end.
- **Animations that take less than the audio**: split them with `lag_ratio` or add `self.wait(tracker.duration - elapsed)` to consume the remainder.
- **No internet for gTTS**: gTTS hits the Google Translate endpoint. Fails offline.
- **Recorder requires `sox`**: install `sudo apt install sox` on Linux, `brew install sox` on macOS.
- **CE only**: `manim-voiceover` does NOT support ManimGL. If the project uses GL, narration must be added in post-production with a separate audio editor.

## Workflow for a narrated video

1. Write the narration script (one paragraph per scene moment).
2. Decide animation per paragraph.
3. Wrap each (animation, narration) pair in `with self.voiceover(text=...)` blocks.
4. Render with `-ql` first — gTTS calls are made on first render and cached.
5. When narration text is finalized, switch to a production service (OpenAI/Azure/ElevenLabs).
6. Render at `-qh` for the final.
