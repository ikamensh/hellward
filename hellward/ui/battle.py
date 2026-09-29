"""The defence itself: the map, the fight and the panel, stepped at the rules' fixed rate.

Input: a build slot (or 1–5) picks a tower or a gate to place, a click on the floor or on an arch places
it, a click on a tower selects it (U upgrades, S sells, C cleanses), right click or Esc lets go; Esc with
nothing to let go of opens the menu. Q, W and E pick Smite, Meteor and Frozen Orb, aimed with a click; Q with
a leader pondering or chanting smites the one closest to cursing at once. Spells wait while the fight is
paused. Space calls the next wave, F doubles the pace, P pauses, Tab shows or hides what the leaders were
thinking.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Callable

from saga2d import Camera, Scene

from hellward.art.sprites import Art
from hellward.audio.music import track_for
from hellward.sim.campaign import CATHEDRAL, Location, first_offering, offers
from hellward.sim.content import SPELLS
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.model import SIM_DT, Monster, Refused, Tower, World
from hellward.sim.players.hands import Hands, Player
from hellward.sim.skills import NO_PERKS, SKILLS, Perks
from hellward.ui.battle_presentation import BattlePresentation, BattleState
from hellward.ui.hud import BUILD, NEW_TOWERS, TOP
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
    controls = {
        "1": "slot_1", "2": "slot_2", "3": "slot_3", "4": "slot_4", "5": "slot_5", "6": "slot_6", "7": "slot_7", "8": "slot_8",
        "space": "call_wave", "f": "toggle_speed", "p": "toggle_pause", "tab": "toggle_thoughts",
        "u": "upgrade", "s": "sell", "c": "cleanse", "escape": "cancel",
        "q": "spell_smite", "w": "spell_meteor", "e": "spell_orb",
        "v": "sell_salvage",
    }

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
        self._replay_written = False
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
        self.placing: str | None = None
        self.selected: Tower | None = None
        self.speed = 1.0
        self.paused = False
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
        if self.selected is not None and self.selected.id not in world.towers:
            self.selected = None
        self.presentation.update(dt, self.acc / SIM_DT if not self.paused else 1.0, self._presentation_state())
        if world.outcome is not None:
            if self.on_outcome is not None:
                callback, self.on_outcome = self.on_outcome, None
                callback(world)
            self._write_replay()
            self.ended += dt
            if self.ended > 3.0 and self.on_end is not None:
                self.presentation.clear_banners()   # the reckoning is drawn over this scene
                callback, self.on_end = self.on_end, None
                callback(world)

    # -- Commands --------------------------------------------------------------------------------

    def _try(self, action: Callable[[], Any]) -> bool:
        try:
            action()
        except Refused as refusal:
            self.presentation.refuse(str(refusal))
            return False
        self.hands.observe(self.world.events, dt=0.0)   # a command's events now, not after a step that may be paused away
        self.presentation.route_events()
        return True

    def _record(self, name: str, *args: Any) -> None:
        """Keep one of the person's commands with the time it took effect. Towers by tile, monsters by
        where they stood; refused commands never reach here. Nothing while the autopilot plays."""
        if self.autopilot is None:
            self.replay.append([self.world.time, name, *args])

    def _write_replay(self) -> None:
        """The moment the defence is decided: the person's commands as one JSON file in the ``replays``
        folder next to the saves. A player who leaves mid-fight never gets here, and writes nothing."""
        if self._replay_written or self.autopilot is not None:
            return
        self._replay_written = True
        folder = self.game.data_dir / "replays"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = folder / f"{stamp}-{self.location.key}.json"
        n = 1
        while path.exists():
            n += 1
            path = folder / f"{stamp}-{self.location.key}-{n}.json"
        world = self.world
        path.write_text(json.dumps({"version": 2, "location": self.location.key, "seed": self.seed,
                                    "skills": sorted(self.learned), "loadout": list(world.loadout.equipped),
                                    "outcome": world.outcome,
                                    "lives": world.lives, "time": world.time, "commands": self.replay}))

    def pick(self, key: str) -> None:
        if not offers(self.location, key):
            try:
                arrival = first_offering(key).called
            except KeyError:
                arrival = None
            note = f"it arrives in {arrival}." if arrival is not None else "it is not offered yet."
            self._refuse(f"Not in {self.location.called}: {note}")
            return
        self.selected = None
        self.placing = None if self.placing == key else key
        self.sound.play("click")

    def _refuse(self, why: str) -> None:
        self.presentation.refuse(why)

    # -- Spells ----------------------------------------------------------------------------------

    def spell(self, key: str) -> None:
        """Pick a spell to aim, as a tower is picked. Smite with a leader pondering or chanting strikes it at once."""
        if self.paused:
            self._refuse("Spells are cast in the fight's own time: resume it first (P).")
            return
        if not offers(self.location, key):
            self._refuse(f"{SPELLS[key].name} is not yet yours: you learn it for {first_offering(key).called}.")
            return
        left = self.world.recharge.get(key, 0.0)
        if left > 0:
            self._refuse(f"{SPELLS[key].name} gathers itself again: {math.ceil(left)} s.")
            return
        cost = self.world.spell_cost(key)
        if self.world.mana < cost:
            self._refuse(f"{SPELLS[key].name} takes {cost:.0f} mana.")
            return
        if key == "smite":
            leader = self.threat()
            if leader is not None:
                x, y = self.world.position(leader)
                if self._try(lambda: self.world.smite(leader.id)):
                    self._record("smite", x, y)
                    self.placing = None
                return
        self.selected = None
        self.placing = None if self.placing == f"spell:{key}" else f"spell:{key}"
        self.sound.play("click")

    def spell_smite(self) -> None:
        self.spell("smite")

    def spell_meteor(self) -> None:
        self.spell("meteor")

    def spell_orb(self) -> None:
        self.spell("orb")

    def threat(self) -> Monster | None:
        """The leader closest to cursing whose curse Smite can still break: the chant nearest its end, else the
        pondering nearest its end. A marking or resolute leader's curse lands whatever is struck, so Q passes it by."""
        leaders = self.world.leaders()
        chanting = [m for m in leaders if m.chant_curse is not None and not m.marking]
        if chanting:
            return min(chanting, key=lambda m: (m.chant_left, m.id))
        pondering = [m for m in leaders if m.asking is not None and not m.resolute]
        return min(pondering, key=lambda m: (m.ask_left, m.id)) if pondering else None

    def _cast_at(self, key: str, wx: float, wy: float) -> bool:
        if self.paused:
            self._refuse("Spells are cast in the fight's own time: resume it first (P).")
            return False
        world = self.world
        x, y = (wx - MAP_X) / T, (wy - MAP_Y) / T
        if key == "smite":
            target = self.presentation.monster_at(wx, wy) or self.presentation.nearest_monster(wx, wy, T)
            if target is None:
                self._refuse("Smite strikes a monster: click on one.")
                return False
            x, y = world.position(target)
            if self._try(lambda: world.smite(target.id)):
                self._record("smite", x, y)
                return True
            return False
        if key == "meteor":
            if self._try(lambda: world.meteor(x, y)):
                self._record("meteor", x, y)
                return True
            return False
        if self._try(lambda: world.orb(x, y)):
            self._record("orb", x, y)
            return True
        return False

    def slots(self) -> tuple[str, ...]:
        """The build bar here: the ordinary slots, and the new towers where this location offers them."""
        return tuple(BUILD) + tuple(key for key in NEW_TOWERS if offers(self.location, key))

    def _slot(self, n: int) -> None:
        slots = self.slots()
        if n < len(slots):
            self.pick(slots[n])

    def slot_1(self) -> None:
        self._slot(0)

    def slot_2(self) -> None:
        self._slot(1)

    def slot_3(self) -> None:
        self._slot(2)

    def slot_4(self) -> None:
        self._slot(3)

    def slot_5(self) -> None:
        self._slot(4)

    def slot_6(self) -> None:
        self._slot(5)

    def slot_7(self) -> None:
        self._slot(6)

    def slot_8(self) -> None:
        self._slot(7)

    def call_wave(self) -> None:
        if self.world.can_call_wave:
            if self._try(self.world.call_wave):
                self._record("call_wave")

    def choose_breach(self, mode: str) -> None:
        if self._try(lambda: self.world.choose_breach(mode)):
            self._record("breach", mode)

    def sell_salvage(self) -> None:
        if self.world.salvage_held and self._try(lambda: self.world.sell_salvage(1)):
            self._record("sell_salvage", 1)

    def toggle_speed(self) -> None:
        self.speed = 1.0 if self.speed > 1 else 2.0

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def toggle_thoughts(self) -> None:
        self.presentation.show_thoughts = not self.presentation.show_thoughts
        if self.settings is not None:
            self.settings["minds"] = self.presentation.show_thoughts
            self.settings.save()

    def upgrade(self) -> None:
        if self.selected is not None:
            tile = list(self.selected.tile)
            if self._try(lambda: self.world.upgrade(self.selected.id)):
                self._record("upgrade", tile)

    def sell(self) -> None:
        if self.selected is not None:
            tower, self.selected = self.selected, None
            if self._try(lambda: self.world.sell(tower.id)):
                self._record("sell", list(tower.tile))

    def cleanse(self) -> None:
        if self.selected is not None:
            tile = list(self.selected.tile)
            if self._try(lambda: self.world.cleanse(self.selected.id)):
                self._record("cleanse", tile)

    def cancel(self) -> None:
        """Escape lets go of what is held or selected; with nothing to let go of, it opens the menu."""
        if self.placing is not None or self.selected is not None:
            self.placing = None
            self.selected = None
        else:
            self.open_menu()

    def open_menu(self) -> None:
        if self.restart is None or self.to_title is None or self.to_map is None:
            self.paused = True   # a scene without a game around it (tests, clips) can only pause; P resumes
            return
        self.game.push(PauseScene(restart=self.restart, to_map=self.to_map, to_title=self.to_title, on_settings=self.settings_changed))

    def settings_changed(self) -> None:
        self.presentation.show_thoughts = self.settings["minds"]

    def _presentation_state(self) -> BattleState:
        return BattleState(self.placing, self.selected, self.speed, self.paused)

    def draw(self) -> None:
        self.presentation.draw(self._presentation_state())

    # -- Pointer ---------------------------------------------------------------------------------

    def handle_input(self, event) -> bool:
        if event.type == "click":
            if event.button == "right":
                self.placing = None
                self.selected = None
                return True
            control = self.presentation.hit_control(event.x, event.y)
            if control is not None:
                self._control(control.name, control.enabled)
                return True
            if event.y >= TOP:
                return True
            if self.placing is not None and self.placing.startswith("spell:"):
                if self._cast_at(self.placing[6:], event.world_x, event.world_y) and not event.shift:
                    self.placing = None
                return True
            tile = self.presentation.tile_at(event.world_x, event.world_y)
            if self.placing == "gate":
                door = self.presentation.door_at(tile)
                if door is not None and self._try(lambda: self.world.build_door(door)):
                    self._record("gate", door)
                    self.placing = None
                return True
            if self.placing is not None and tile is not None:
                kind = self.placing
                if self._try(lambda: self.world.build(kind, tile)):
                    self._record("build", kind, list(tile))
                    if not event.shift:
                        self.placing = None
                return True
            tower = self.world.tower_at(tile) if tile is not None else None
            self.selected = tower
            if tower is not None:
                self.sound.play("click")
            return True
        return False

    def _control(self, name: str, enabled: bool) -> None:
        kind, _, key = name.partition(":")
        if kind == "spell":
            self.spell(key)   # it says why when it cannot
        elif kind == "build" and not offers(self.location, key):
            self.pick(key)    # it says where the slot's tower arrives
        elif not enabled:
            if name == "upgrade" and self.selected is not None:
                need = self.world.rank_needs(self.selected)
                if need is not None:
                    self._refuse(f"Learn {SKILLS[need].name} in the skill tree (K)")
                    return
            self.sound.play("refuse")
        elif kind == "build":
            self.pick(key)
        elif name == "call":
            self.call_wave()
        elif kind == "breach":
            self.choose_breach(key)
        elif name == "salvage:sell":
            self.sell_salvage()
        elif name == "speed":
            self.toggle_speed()
        elif name == "menu":
            self.open_menu()
        elif name in ("upgrade", "sell", "cleanse"):
            getattr(self, name)()
