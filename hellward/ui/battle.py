"""The defence itself: the map, the fight and the panel, stepped at the rules' fixed rate.

Input: a build slot (or 1–8) picks a tower or a gate to place, a click on the floor or on an arch places
it, a click on a tower selects it (U upgrades, S sells, C cleanses), right click or Esc lets go; Esc with
nothing to let go of opens the menu. Q, W and E pick Smite, Meteor and Frozen Orb, aimed with a click; Q with
a leader pondering or chanting smites the one closest to cursing at once. Spells wait while the fight is
paused. Space calls the next wave, F doubles the pace, P pauses, Tab shows or hides what the leaders were
thinking.
"""

from __future__ import annotations

from typing import Any, Callable

from saga2d import Camera, Scene

from hellward.art.sprites import Art
from hellward.audio.music import track_for
from hellward.sim.campaign import CATHEDRAL, Location
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.model import SIM_DT, Tower, World
from hellward.sim.players.hands import Hands, Player
from hellward.sim.skills import NO_PERKS, Perks
from hellward.ui.battle_orders import BattleOrders
from hellward.ui.battle_presentation import BattlePresentation, BattleState
from hellward.ui.hud import TOP
from hellward.ui.menus import PauseScene
from hellward.ui.view import MAP_X, MAP_Y, T

WIDTH, HEIGHT = 1280, 800


class Silent:
    def play(self, cue: str, **_: Any) -> None:
        pass

    def music(self, mood: str) -> None:
        pass


class BattleScene(Scene):
    background_color = (8, 6, 8, 255)

    def __init__(self, art: Art, location: Location = CATHEDRAL, *, perks: Perks = NO_PERKS,
                 learned: frozenset[str] | None = None, loadout: Loadout = EMPTY_LOADOUT,
                 breach_claim: str | None = None,
                 seed: int = 0, planner: Callable | None = None, sound: Any = None,
                 autopilot: Player | None = None, on_end: Callable[[World], None] | None = None,
                 on_outcome: Callable[[World], None] | None = None,
                 settings: Any = None, restart: Callable[[], None] | None = None,
                 to_title: Callable[[], None] | None = None, to_map: Callable[[], None] | None = None) -> None:
        self.art = art
        self.location = location
        self.perks = perks
        self.learned = frozenset(learned) if learned is not None else frozenset()
        self.loadout = loadout
        self.breach_claim = breach_claim
        self.replay: list[list] = []     # the person's commands, [time, name, args...], for a ghost to replay
        self.settings = settings
        self.restart = restart
        self.to_title = to_title
        self.to_map = to_map
        self.seed = seed
        self.planner = planner
        self.sound = sound or Silent()
        self.autopilot = autopilot
        self.on_end = on_end            # three seconds after the fight is decided: the reckoning
        self.on_outcome = on_outcome    # the moment it is decided: the result is kept, whatever the player does next
        self.state = BattleState(None, None, 1.0, False)
        self.acc = 0.0
        self.ended = 0.0

    def on_enter(self) -> None:
        self.world = World(self.location, perks=self.perks, seed=self.seed, planner=self.planner, loadout=self.loadout)
        level = self.world.level
        zoom = min(1.0, (WIDTH - 2 * MAP_X) / (level.width * T), (TOP - MAP_Y) / (level.height * T))
        self.camera = Camera((WIDTH, HEIGHT),
                             world_bounds=(MAP_X, MAP_Y, MAP_X + level.width * T, MAP_Y + level.height * T),
                             insets=(0, 0, 0, HEIGHT - TOP), zoom=zoom, min_zoom=min(0.25, zoom))
        self.presentation = BattlePresentation(
            self, self.world, self.art, self.sound, breach_claim=self.breach_claim,
            show_thoughts=self.settings["minds"] if self.settings is not None else True)
        self.view, self.fx, self.hud = self.presentation.view, self.presentation.fx, self.presentation.hud
        self.hands = Hands(self.world, react=0.6)
        self.orders = BattleOrders(
            self.world, self.state, self.hands, self.presentation, self.sound, self.replay,
            recording=lambda: self.autopilot is None, data_dir=self.game.data_dir, seed=self.seed,
            learned=self.learned, settings=self.settings, open_menu=self.open_menu)
        self.orders.bind_keys(self)
        self.sound.music(track_for(self.location.key))

    def on_background(self) -> None:
        """A player who looks away comes back to the pause menu, whose Resume resumes."""
        if self.autopilot is None and self.game.scenes[-1] is self:
            self.open_menu()

    def on_reveal(self) -> None:
        self.paused = False   # closing the menu resumes, whatever paused the fight before it opened

    # -- The clock -------------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        world = self.world
        if not self.paused:
            self.acc += min(dt, 0.1) * self.speed
            while self.acc >= SIM_DT:
                self.acc -= SIM_DT
                if self.autopilot is not None:
                    self.autopilot.act(self.hands)
                self.presentation.before_step()
                world.step(SIM_DT)
                self.hands.observe(world.events)
                self.presentation.route_events()
        self.orders.refresh()
        self.presentation.update(dt, self.acc / SIM_DT if not self.paused else 1.0, self.state)
        if world.outcome is not None:
            if self.on_outcome is not None:
                callback, self.on_outcome = self.on_outcome, None
                callback(world)
            self.orders.write_replay()
            self.ended += dt
            if self.ended > 3.0 and self.on_end is not None:
                self.presentation.clear_banners()   # the reckoning is drawn over this scene
                callback, self.on_end = self.on_end, None
                callback(world)

    def call_wave(self) -> None:
        """Used by replay-driving tools as well as the bound Space key."""
        self.orders.call_wave()

    # -- Scene navigation ------------------------------------------------------------------------

    def open_menu(self) -> None:
        if self.restart is None or self.to_title is None or self.to_map is None:
            self.paused = True   # a scene without a game around it (tests, clips) can only pause; P resumes
            return
        self.game.push(PauseScene(restart=self.restart, to_map=self.to_map, to_title=self.to_title, on_settings=self.settings_changed))

    def settings_changed(self) -> None:
        self.presentation.show_thoughts = self.settings["minds"]

    @property
    def placing(self) -> str | None:
        return self.state.placing

    @property
    def selected(self) -> Tower | None:
        return self.state.selected

    @property
    def speed(self) -> float:
        return self.state.speed

    @speed.setter
    def speed(self, value: float) -> None:
        self.state.speed = value

    @property
    def paused(self) -> bool:
        return self.state.paused

    @paused.setter
    def paused(self, value: bool) -> None:
        self.state.paused = value

    def handle_input(self, event) -> bool:
        return self.orders.handle_input(event)

    def draw(self) -> None:
        self.presentation.draw(self.state)
