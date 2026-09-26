"""The ways between the screens: the title, the world map, a location's intro, its defence, the reckoning and the
skill tree. One :class:`Flow` holds what they share (the art, the sound, the leaders' planner, the settings and the
campaign's progress) and every screen asks it where to go next.
"""

from __future__ import annotations

from typing import Any, Callable

from saga2d import Game, Scene

from hellward.art.sprites import Art
from hellward.sim.campaign import CATHEDRAL, DIFFICULTIES, Location
from hellward.sim.model import World
from hellward.sim.players.hands import Player
from hellward.sim.skills import perks
from hellward.ui.battle import BattleScene
from hellward.ui.briefing import BriefingScene
from hellward.ui.mapscreen import MapScene
from hellward.ui.progress import Progress
from hellward.ui.skilltree import SkillTreeScene
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
        self.game.clear_and_push(MapScene(self))
        self.sound.music("title")

    def descend(self) -> None:
        """The title's Descend: the map, and on a new campaign the lantern walks straight on to Tristram."""
        self.game.clear_and_push(MapScene(self, first=self.progress.sigils == 0))
        self.sound.music("title")

    def intro(self, location: Location) -> None:
        self.progress.move(location.key)
        self.game.clear_and_push(BriefingScene(self, location))

    def skills(self, location: Location | None = None) -> None:
        self.game.push(SkillTreeScene(self, location))

    def defend(self, location: Location) -> None:
        if not self.progress.opened(location):
            self.world_map()   # the way there is not open on this difficulty
            return
        self.game.clear_and_push(BattleScene(
            self.art, location, difficulty=DIFFICULTIES[self.progress.difficulty], perks=perks(self.progress.learned),
            seed=self.seed, planner=self.planner, sound=self.sound, on_outcome=self.keep, on_end=self.reckon,
            settings=self.settings, restart=lambda: self.defend(location), to_title=self.title, to_map=self.world_map))

    def demo(self) -> None:
        self.game.clear_and_push(self.demo_scene())

    def demo_scene(self) -> Scene:
        """The title's "Watch the leaders at work": the strongest scripted player defends the Cathedral."""
        return BattleScene(self.art, CATHEDRAL, seed=self.seed, planner=self.planner, sound=self.sound, autopilot=self.demo_player(),
                           on_end=lambda world: self.title(), settings=self.settings, restart=self.demo, to_title=self.title,
                           to_map=self.world_map)

    def keep(self, world: World) -> None:
        """The moment a defence is decided: its sigils are won, even if the player leaves before the reckoning."""
        self.gained = self.progress.record(world.location.key, world.outcome, world.lives)

    def reckon(self, world: World) -> None:
        self.game.push(ReckoningScene(self, world, self.gained))
