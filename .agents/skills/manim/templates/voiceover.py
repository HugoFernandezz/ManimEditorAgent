"""
Narrated scene template using manim-voiceover.

Install:
    pip install "manim-voiceover[gtts]"

Run:
    manim -pql voiceover.py NarratedScene

The animation's run_time follows the audio length automatically.
"""

from manim import *
from manim_voiceover import VoiceoverScene
from manim_voiceover.services.gtts import GTTSService

# To use a higher-quality provider, swap to one of:
#   from manim_voiceover.services.openai import OpenAIService
#   from manim_voiceover.services.azure import AzureService
#   from manim_voiceover.services.elevenlabs import ElevenLabsService
# (See references/narration.md)


class NarratedScene(VoiceoverScene):
    def construct(self):
        # Free, no API key, requires internet. Replace for production.
        self.set_speech_service(GTTSService(lang="en"))

        title = Text("A simple narrated example", font_size=44).to_edge(UP)
        circle = Circle(radius=1.5, color=BLUE, fill_opacity=0.5)

        # Each `with` block ties an animation to the spoken sentence.
        with self.voiceover(text="Let's begin with a title.") as tracker:
            self.play(Write(title), run_time=tracker.duration)

        with self.voiceover(text="Now we draw a blue circle in the middle.") as tracker:
            self.play(Create(circle), run_time=tracker.duration)

        with self.voiceover(
            text="Watch as it grows, and then settles into place."
        ) as tracker:
            self.play(circle.animate.scale(1.5), run_time=tracker.duration * 0.6)
            self.play(circle.animate.scale(1 / 1.5), run_time=tracker.duration * 0.4)

        # Bookmarks let you sync multiple animations to one block of narration.
        equation = MathTex(r"A = \pi r^2", font_size=64).shift(DOWN * 2)

        with self.voiceover(
            text=(
                "The area of this circle is given by <bookmark mark='eq'/>"
                " pi r squared, where r is the radius."
            )
        ) as tracker:
            self.wait(tracker.time_until_bookmark("eq"))
            self.play(Write(equation), run_time=tracker.get_remaining_duration())

        with self.voiceover(text="And that is the end of the demo.") as tracker:
            self.play(
                FadeOut(title),
                FadeOut(circle),
                FadeOut(equation),
                run_time=tracker.duration,
            )
