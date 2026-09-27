"""The ways between the screens: the title, the world map, a location's intro, its defence, the reckoning and the
skill tree. One :class:`Flow` holds what they share (the art, the sound, the leaders' planner, the settings and the
campaign's progress) and every screen asks it where to go next.
"""

from __future__ import annotations

from typing import Any, Callable

from saga2d import Game, Scene

from hellward.art.sprites import Art
from hellward.audio.music import track_for
from hellward.sim.campaign import ACT_ENDS, CATHEDRAL, LOCATIONS, ORDER, Location
from hellward.sim.model import World
from hellward.sim.players.hands import Player
from hellward.sim.skills import perks
from hellward.story import LAST_PAGES, STORIES
from hellward.ui.battle import BattleScene
from hellward.ui.briefing import BriefingScene
from hellward.ui.mapscreen import MapScene
from hellward.ui.progress import Progress
from hellward.ui.skilltree import SkillTreeScene
from hellward.ui.story import ChronicleScene, PrologueScene, StoryScene
from hellward.ui.title import ReckoningScene, TitleScene


class Flow:
    def __init__(self, game: Game, art: Art, *, sound: Any, planner: Callable, settings: Any, progress: Progress,
                 demo_player: Callable[[], Player], seed: int = 0) -> None:
        self.game = game
        self.art = art
        self.sound = sound
        self.planner = planner
        self.settings = settings
        self.progress = progress
        self.demo_player = demo_player
        self.seed = seed
        self.gained = 0   # the sigils the last defence added

    def title(self) -> None:
        self.game.clear_and_push(TitleScene(self))
        self.sound.music("title")

    def world_map(self) -> None:
        """Before the map shows, play one due and unseen story (:meth:`due`), then the map."""
        key = self.due()
        if key is None:
            self._open_map()
            return
        self.progress.see(key)
        self.game.clear_and_push(StoryScene(self, STORIES[key].pages, then=self._after(key)))

    def _after(self, key: str) -> Callable[[], None]:
        """Where a story leaves the map: after Act I's ending, on Act II's map, the lantern walking to the Docks."""
        if key == LAST_PAGES[1]:
            return lambda: self._open_map(act=2, first=True)
        return self._open_map

    def due(self) -> str | None:
        """The story a map opening owes the player, if any: an act's ending once its last location is held, else the
        after page of a held location in an act not yet finished (a finished act's pages wait in the Chronicle), in
        campaign order. A player who quit at the reckoning gets it here."""
        seen = self.progress.seen
        for act, end in ACT_ENDS.items():
            if self.progress.held(end) and LAST_PAGES[act] not in seen:
                return LAST_PAGES[act]
        for key in ORDER:
            page = f"{key}/after"
            if (page in STORIES and page not in seen and self.progress.held(key)
                    and not self.progress.held(ACT_ENDS[LOCATIONS[key].act])):
                return page
        return None

    def _open_map(self, act: int | None = None, first: bool = False) -> None:
        self.game.clear_and_push(MapScene(self, act=act, first=first))
        self.sound.music("title")

    def descend(self) -> None:
        """The title's Descend: the prologue on a new campaign, then the map, the lantern walking straight on
        to Tristram when nothing is won yet."""
        if "prologue" not in self.progress.seen:
            self.progress.see("prologue")
            self.game.clear_and_push(PrologueScene(self, then=self._descend))
        else:
            self._descend()

    def _descend(self) -> None:
        if self.progress.sigils == 0:
            self._open_map(act=1, first=True)
        else:
            self.world_map()

    def intro(self, location: Location) -> None:
        """A location's before page on the first arrival, then its intro."""
        key = f"{location.key}/before"
        story = STORIES.get(key)
        if story is not None and key not in self.progress.seen:
            self.progress.see(key)
            self.game.clear_and_push(StoryScene(self, story.pages, then=lambda: self._open_intro(location)))
        else:
            self._open_intro(location)

    def _open_intro(self, location: Location) -> None:
        self.progress.move(location.key)
        self.game.clear_and_push(BriefingScene(self, location))
        self.sound.music(track_for(location.key))

    def story(self, location: Location) -> None:
        """Replay a location's before page from its intro, back to the intro."""
        tale = STORIES.get(f"{location.key}/before")
        if tale is None:
            self._open_intro(location)
            return
        self.progress.see(tale.key)
        self.game.clear_and_push(StoryScene(self, tale.pages, then=lambda: self._open_intro(location)))

    def chronicle(self) -> None:
        self.game.clear_and_push(ChronicleScene(self, then=self.title))

    def skills(self, location: Location | None = None) -> None:
        self.game.push(SkillTreeScene(self, location))

    def defend(self, location: Location) -> None:
        if not self.progress.opened(location):
            self.world_map()   # the way there is not open
            return
        self.game.clear_and_push(BattleScene(
            self.art, location, perks=perks(self.progress.learned), learned=self.progress.learned,
            seed=self.seed, planner=self.planner, sound=self.sound, on_outcome=self.keep, on_end=self.reckon,
            settings=self.settings, restart=lambda: self.defend(location), to_title=self.title, to_map=self.world_map))

    def demo(self) -> None:
        self.game.clear_and_push(self.demo_scene())

    def demo_scene(self) -> Scene:
        """The title's "Watch the leaders at work": the strongest scripted player defends the Cathedral, with the skills
        the sigils won on the way there buy."""
        player = self.demo_player()
        learned = player.skills(CATHEDRAL, 3 * ORDER.index(CATHEDRAL.key))
        return BattleScene(self.art, CATHEDRAL, perks=perks(learned), learned=learned, seed=self.seed, planner=self.planner,
                           sound=self.sound, autopilot=player,
                           on_end=lambda world: self.title(), settings=self.settings, restart=self.demo, to_title=self.title,
                           to_map=self.world_map)

    def keep(self, world: World) -> None:
        """The moment a defence is decided: its sigils are won, even if the player leaves before the reckoning."""
        self.gained = self.progress.record(world.location.key, world.outcome, world.lives)

    def reckon(self, world: World) -> None:
        self.game.push(ReckoningScene(self, world, self.gained))

    def leave_reckoning(self, world: World, *, again: bool) -> None:
        """Leave the reckoning by either button: after a victory the act ending (at the last location) or the
        location's after page plays first when unseen, then the button's way."""
        if world.outcome == "victory":
            act = world.location.act
            key = LAST_PAGES[act] if world.location.key == ACT_ENDS[act] else f"{world.location.key}/after"
            story = STORIES.get(key)
            finished = world.location.key != ACT_ENDS[act] and self.progress.held(ACT_ENDS[act])
            if story is not None and key not in self.progress.seen and not finished:   # a finished act's pages wait in the Chronicle
                self.progress.see(key)
                if key == LAST_PAGES[1]:
                    dest = self._after(key)
                else:
                    dest = (lambda: self.intro(world.location)) if again else self.world_map
                self.game.clear_and_push(StoryScene(self, story.pages, then=dest))
                return
        if again:
            self.intro(world.location)
        else:
            self.world_map()
