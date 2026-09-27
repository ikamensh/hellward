"""The story on screen: story pages, the prologue comic, and the Chronicle.

A :class:`StoryScene` shows one story's painted panels full screen, a few paragraphs fading in over a dark
band. A :class:`PrologueScene` plays the intro comic in ``hellward/assets/story/prologue`` (its timeline, its
recorded voice, its music). A :class:`ChronicleScene` plays the prologue and then every story whose moment has
come. The pictures are painted later: when a file does not exist the scene draws a dark gradient instead and
never crashes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PIL import Image as PILImage
from saga2d import Scene

from hellward.sim.campaign import ACT_ENDS, LOCATIONS
from hellward.story import STORIES, Page, Story
from hellward.ui import style

if TYPE_CHECKING:
    from hellward.ui.flow import Flow
    from hellward.ui.progress import Progress

WIDTH, HEIGHT = 1280, 800

#: How long a screen shown right after a story page or the prologue ignores Enter, Esc and clicks, so a key
#: held through the transition never starts a fight unread. BriefingScene and MapScene honour this.
INPUT_GUARD = 0.3

STORY_DIR = Path(__file__).resolve().parent.parent / "assets" / "story"
PROLOGUE_DIR = STORY_DIR / "prologue"

def _picture(game, name: str, path: Path) -> str | None:
    """Register a painted picture under ``name`` the first time it is asked for; ``None`` while it is not painted."""
    if not game.assets.has_image(name):
        if not path.exists():
            return None
        game.assets.image_from_pil(name, PILImage.open(path).convert("RGB"))
    return name


def story_image(game, key: str) -> str | None:
    """``hellward/assets/story/<key>.jpg`` as the image ``story/<key>``."""
    return _picture(game, f"story/{key}", STORY_DIR / f"{key}.jpg")


def prologue_image(game, key: str) -> str | None:
    """``hellward/assets/story/prologue/<key>.jpg`` as the image ``prologue/<key>``."""
    return _picture(game, f"prologue/{key}", PROLOGUE_DIR / f"{key}.jpg")


def image_size(game, name: str) -> tuple[float, float]:
    w, h = game.backend.get_image_size(game.assets.image(name))
    return float(w), float(h)


def draw_gradient(scene: Scene) -> None:
    """The dark stand-in for a picture not painted yet."""
    bands = 40
    for i in range(bands):
        t = i / (bands - 1)
        color = (int(26 - 20 * t), int(14 - 10 * t), int(20 - 14 * t), 255)
        scene.draw_rect(0, i * HEIGHT / bands, WIDTH, HEIGHT / bands + 1, color)


def draw_cover(scene: Scene, name: str | None, zoom: float = 1.0, pan: float = 0.0) -> None:
    """A picture filling the screen, centred and cover-fit; *pan* drifts it sideways (0 to 1 of the spare
    width). A missing picture draws the gradient instead."""
    if name is None:
        draw_gradient(scene)
        return
    w, h = image_size(scene.game, name)
    scale = max(WIDTH / w, HEIGHT / h) * zoom
    dw, dh = w * scale, h * scale
    x = (WIDTH - dw) / 2 if dw <= WIDTH else -(dw - WIDTH) * max(0.0, min(1.0, pan))
    scene.draw_image(name, x, (HEIGHT - dh) / 2, dw, dh)


def due_stories(progress: Progress) -> list[Story]:
    """Every story in :data:`hellward.story.STORIES` whose moment has come, in dict order: a before page when
    its location is opened, an after page when it is held, an act's ending when its last location is held."""
    out = []
    for story in STORIES.values():
        place, _, when = story.key.partition("/")
        if when == "end":
            due = progress.held(ACT_ENDS[story.act])
        elif when == "before":
            due = progress.opened(LOCATIONS[place])
        else:
            due = progress.held(place)
        if due:
            out.append(story)
    return out


class StoryScene(Scene):
    """One story's pages, one painted panel at a time. Enter or a left click first shows every paragraph at
    once, then goes to the next page; Esc skips the rest. After the last page calls ``then``."""

    background_color = (6, 4, 6, 255)
    controls = {("return", "enter"): "advance", ("escape", "esc"): "skip"}

    BAND = 280          # the dark band over the bottom holding the paragraphs
    FADE = 0.8          # seconds each paragraph fades in over, one after another

    def __init__(self, flow: Flow, pages: tuple[Page, ...], then: Callable[[], None]) -> None:
        self.flow = flow
        self.pages = pages
        self.then = then
        self.index = 0
        self.clock = 0.0
        self.revealed = False
        self._done = False

    def advance(self) -> None:
        if self._done:
            return
        if not self.revealed:
            self.revealed = True
            return
        self.index += 1
        self.clock = 0.0
        self.revealed = False
        if self.index >= len(self.pages):
            self.finish()

    def skip(self) -> None:
        self.finish()

    def finish(self) -> None:
        if not self._done:
            self._done = True
            self.then()

    def handle_input(self, event) -> bool:
        if event.type == "click":
            self.advance()
            return True
        return False

    def update(self, dt: float) -> None:
        self.clock += dt

    def draw(self) -> None:
        if self.index >= len(self.pages):
            return
        page = self.pages[self.index]
        zoom = 1.0 + 0.04 * min(1.0, self.clock / 12.0)
        draw_cover(self, story_image(self.game, page.key), zoom=zoom)
        with self.screen_layer(1):   # over the picture: within one layer, shapes sit under images
            self.draw_rect(0, HEIGHT - self.BAND, WIDTH, self.BAND, (0, 0, 0, 200))
            self.draw_rect(0, HEIGHT - self.BAND, WIDTH, 2, (92, 76, 58, 200))
            y = HEIGHT - self.BAND + 22
            for i, paragraph in enumerate(page.text):
                alpha = 255 if self.revealed else int(255 * min(1.0, max(0.0, (self.clock - i * self.FADE) / self.FADE)))
                if alpha <= 0:
                    break
                y += self.draw_paragraph(paragraph, 140, y, 1000, font_size=18,
                                         color=style.BONE[:3] + (alpha,)) + 12
            self.draw_text("Enter: continue  ·  Esc: skip", WIDTH / 2, HEIGHT - 14, font_size=12, color=style.DIM,
                           anchor_x="center", anchor_y="center")


class PrologueScene(Scene):
    """The intro comic: ``prologue/timeline.json`` drives the pictures, the captions and the voice lines."""

    background_color = (6, 4, 6, 255)
    controls = {("return", "enter"): "finish", ("escape", "esc"): "finish"}

    COLUMNS = ("fire", "thunder", "frost", "dead")   # the upright pictures, side by side as four columns

    def __init__(self, flow: Flow, then: Callable[[], None]) -> None:
        self.flow = flow
        self.then = then
        self.clock = 0.0
        self._done = False
        self._played: set[int] = set()
        self._music = False
        timeline = json.loads((PROLOGUE_DIR / "timeline.json").read_text())
        self.shots: list[dict] = timeline["shots"]
        self.words: list[dict] = timeline["words"]
        self.end = max(shot["start"] + shot["length"] for shot in self.shots)

    # -- Sound -------------------------------------------------------------------------------

    def begin(self) -> None:
        """Start the music; also called when the Chronicle opens this scene without pushing it."""
        if self._music:
            return
        self._music = True
        self.game.audio.play_music(str(PROLOGUE_DIR / "music.wav"), loop=False)

    def on_enter(self) -> None:
        self.begin()

    def _voice(self, index: int, voice: str) -> None:
        if index in self._played:
            return
        self._played.add(index)
        self.game.audio.play_sound(str(PROLOGUE_DIR / f"voice-{voice}.wav"))

    def finish(self) -> None:
        if self._done:
            return
        self._done = True
        self.quiet()
        self.then()

    def quiet(self) -> None:
        """Stop the voice and fade the music out, without ending the scene."""
        self.game.backend.stop_sounds()
        self.game.audio.stop_music(fade=1.0)

    # -- Input and the clock -------------------------------------------------------------------

    def handle_input(self, event) -> bool:
        if event.type == "click":
            self.finish()
            return True
        return False

    def update(self, dt: float) -> None:
        self.clock += dt
        for i, word in enumerate(self.words):
            if word.get("voice") and self.clock >= word["at"]:
                self._voice(i, word["voice"])
        if self.clock >= self.end:
            self.finish()

    def _shot(self) -> dict | None:
        for shot in self.shots:
            if shot["start"] <= self.clock < shot["start"] + shot["length"]:
                return shot
        return None

    def _start(self, key: str) -> float:
        for shot in self.shots:
            if shot["key"] == key:
                return shot["start"]
        return 0.0

    # -- Drawing ---------------------------------------------------------------------------------

    def draw(self) -> None:
        shot = self._shot()
        if shot is None:
            draw_gradient(self)
            return
        key = shot["key"]
        progress = (self.clock - shot["start"]) / shot["length"] if shot["length"] else 1.0
        if key in self.COLUMNS:
            self._columns()
        elif key == "bones":
            self._bones(shot, progress)
        elif key == "title":
            self._title()
        else:
            draw_cover(self, prologue_image(self.game, key), zoom=1.06, pan=progress)
        if key != "title":
            self._caption()

    def _columns(self) -> None:
        """The four upright pictures, each appearing at its shot's start while the earlier ones stay."""
        for i, key in enumerate(self.COLUMNS):
            if self.clock < self._start(key):
                continue
            name = prologue_image(self.game, key)
            if name is None:
                self.draw_rect(i * 320, 0, 320, HEIGHT, (10, 6, 8, 255))
                continue
            w, h = image_size(self.game, name)
            scale = max(320 / w, HEIGHT / h)
            dw, dh = w * scale, h * scale
            self.draw_image(name, i * 320 + (320 - dw) / 2, (HEIGHT - dh) / 2, dw, dh)

    def _bones(self, shot: dict, progress: float) -> None:
        """Flicker through the three bone visions faster and faster, ending on the bones themselves."""
        if progress >= 0.8:
            draw_cover(self, prologue_image(self.game, "bones"), zoom=1.06)
            return
        interval = 0.5 * (1.0 - progress) + 0.08
        variant = int((self.clock - shot["start"]) / interval) % 3
        draw_cover(self, prologue_image(self.game, f"bones-v{variant}"), zoom=1.06)

    def _title(self) -> None:
        if self.game.assets.has_image("title"):
            self.draw_image("title", 0, 0, WIDTH, HEIGHT)
        else:
            draw_gradient(self)
        with self.screen_layer(1):
            self.draw_rect(0, HEIGHT - 190, WIDTH, 190, (0, 0, 0, 200))
            self.draw_text("HELLWARD", WIDTH / 2, HEIGHT - 130, style="title", anchor_x="center", anchor_y="center")
            self.draw_text("Keep it burning.", WIDTH / 2, HEIGHT - 62, font_size=22, color=style.PALE_GOLD,
                           anchor_x="center", anchor_y="center")

    def _caption(self) -> None:
        text = ""
        for word in self.words:
            if word["at"] <= self.clock < word["at"] + word["length"]:
                text = word["text"]
        if not text:
            return
        with self.screen_layer(1):
            self.draw_rect(0, HEIGHT - 116, WIDTH, 116, (0, 0, 0, 200))
            self.draw_text(text, WIDTH / 2, HEIGHT - 58, font_size=20, color=style.BONE, anchor_x="center",
                           anchor_y="center")


class ChronicleScene(Scene):
    """The prologue first, then every story whose moment has come, in dict order. Esc leaves to ``then``."""

    background_color = (6, 4, 6, 255)
    controls = {("return", "enter"): "press", ("escape", "esc"): "leave"}

    def __init__(self, flow: Flow, then: Callable[[], None]) -> None:
        self.flow = flow
        self.then = then
        self._done = False
        self._prologue: PrologueScene | None = PrologueScene(flow, then=self._begin_stories)
        self._stories = due_stories(flow.progress)
        self._story: StoryScene | None = None
        self._index = -1

    def on_enter(self) -> None:
        assert self._prologue is not None
        self.flow.progress.see("prologue")   # seen here, Descend won't show it again
        self._prologue.game = self.game
        self._prologue.begin()

    def _begin_stories(self) -> None:
        self._prologue = None
        self._index = -1
        self._next_story()

    def _next_story(self) -> None:
        self._index += 1
        if self._index >= len(self._stories):
            self._story = None
            self.leave()
            return
        story = self._stories[self._index]
        self.flow.progress.see(story.key)
        self._story = StoryScene(self.flow, story.pages, then=self._next_story)
        self._story.game = self.game

    def press(self) -> None:
        if self._prologue is not None:
            self._prologue.finish()   # skip the prologue to the first story
        elif self._story is not None:
            self._story.advance()

    def leave(self) -> None:
        if self._prologue is not None:
            self._prologue._done = True
            self._prologue.quiet()
            self._prologue = None
        if not self._done:
            self._done = True
            self.then()

    def handle_input(self, event) -> bool:
        if event.type == "click":
            self.press()
            return True
        return False

    def update(self, dt: float) -> None:
        if self._prologue is not None:
            self._prologue.update(dt)
        elif self._story is not None:
            self._story.update(dt)

    def draw(self) -> None:
        if self._prologue is not None:
            self._prologue.draw()
        elif self._story is not None:
            self._story.draw()
        else:
            draw_gradient(self)
