"""A person's acts during one defence: choices, accepted commands and their replay.

``BattleScene`` advances the rules and owns scene transitions. Orders turn keys and clicks into
world commands, keep the current selection, and record exactly the commands that took effect.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from saga2d import Scene

from hellward.sim.campaign import first_offering, offers
from hellward.sim.content import SPELLS
from hellward.sim.model import Monster, Refused, World
from hellward.sim.players.hands import Hands
from hellward.sim.skills import SKILLS
from hellward.ui.battle_presentation import BattlePresentation, BattleState
from hellward.ui.hud import BUILD, NEW_TOWERS, TOP
from hellward.ui.view import MAP_X, MAP_Y, T

_KEYS = tuple(str(n) for n in range(1, 9)) + (
    "space", "f", "p", "tab", "u", "s", "c", "escape", "q", "w", "e", "v")


class BattleOrders:
    """One player's input and replay, sharing only the small frame state with presentation."""

    def __init__(self, world: World, state: BattleState, hands: Hands, presentation: BattlePresentation,
                 sound: Any, replay: list[list], *, recording: Callable[[], bool], data_dir: Path, seed: int,
                 learned: frozenset[str], settings: Any, open_menu: Callable[[], None]) -> None:
        self.world = world
        self.location = world.location
        self.state = state
        self.hands = hands
        self.presentation = presentation
        self.sound = sound
        self.replay = replay
        self.recording = recording
        self.data_dir = data_dir
        self.seed = seed
        self.learned = learned
        self.settings = settings
        self._open_menu = open_menu
        self._replay_written = False

    def bind_keys(self, scene: Scene) -> None:
        """Use Saga2D's key dispatch phase, after UI and camera but before pointer input."""
        for key in _KEYS:
            scene.bind_key(key, lambda key=key: self.press(key))

    def press(self, key: str) -> None:
        if key in "12345678" and len(key) == 1:
            self.pick_slot(int(key) - 1)
        elif key in ("q", "w", "e"):
            self.spell({"q": "smite", "w": "meteor", "e": "orb"}[key])
        else:
            commands = {
                "space": self.call_wave, "f": self.toggle_speed, "p": self.toggle_pause,
                "tab": self.toggle_thoughts, "u": self.upgrade, "s": self.sell,
                "c": self.cleanse, "escape": self.cancel, "v": self.sell_salvage,
            }
            commands[key]()

    def refresh(self) -> None:
        if self.state.selected is not None and self.state.selected.id not in self.world.towers:
            self.state.selected = None

    # -- Accepted commands and replay -------------------------------------------------------

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
        if self.recording():
            self.replay.append([self.world.time, name, *args])

    def write_replay(self) -> None:
        """The moment the defence is decided: the person's commands as one JSON file in the ``replays``
        folder next to the saves. A player who leaves mid-fight never gets here, and writes nothing."""
        if self._replay_written or not self.recording():
            return
        self._replay_written = True
        folder = self.data_dir / "replays"
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
        self.state.selected = None
        self.state.placing = None if self.state.placing == key else key
        self.sound.play("click")

    def _refuse(self, why: str) -> None:
        self.presentation.refuse(why)

    # -- Spells ----------------------------------------------------------------------------------

    def spell(self, key: str) -> None:
        """Pick a spell to aim, as a tower is picked. Smite with a leader pondering or chanting strikes it at once."""
        if self.state.paused:
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
                    self.state.placing = None
                return
        self.state.selected = None
        self.state.placing = None if self.state.placing == f"spell:{key}" else f"spell:{key}"
        self.sound.play("click")

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
        if self.state.paused:
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

    def pick_slot(self, n: int) -> None:
        slots = self.slots()
        if n < len(slots):
            self.pick(slots[n])

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
        self.state.speed = 1.0 if self.state.speed > 1 else 2.0

    def toggle_pause(self) -> None:
        self.state.paused = not self.state.paused

    def toggle_thoughts(self) -> None:
        self.presentation.show_thoughts = not self.presentation.show_thoughts
        if self.settings is not None:
            self.settings["minds"] = self.presentation.show_thoughts
            self.settings.save()

    def upgrade(self) -> None:
        if self.state.selected is not None:
            tile = list(self.state.selected.tile)
            if self._try(lambda: self.world.upgrade(self.state.selected.id)):
                self._record("upgrade", tile)

    def sell(self) -> None:
        if self.state.selected is not None:
            tower, self.state.selected = self.state.selected, None
            if self._try(lambda: self.world.sell(tower.id)):
                self._record("sell", list(tower.tile))

    def cleanse(self) -> None:
        if self.state.selected is not None:
            tile = list(self.state.selected.tile)
            if self._try(lambda: self.world.cleanse(self.state.selected.id)):
                self._record("cleanse", tile)

    def cancel(self) -> None:
        """Escape lets go of what is held or selected; with nothing to let go of, it opens the menu."""
        if self.state.placing is not None or self.state.selected is not None:
            self.state.placing = None
            self.state.selected = None
        else:
            self._open_menu()

    # -- Pointer input ---------------------------------------------------------------------

    def handle_input(self, event) -> bool:
        if event.type == "click":
            if event.button == "right":
                self.state.placing = None
                self.state.selected = None
                return True
            control = self.presentation.hit_control(event.x, event.y)
            if control is not None:
                self._control(control.name, control.enabled)
                return True
            if event.y >= TOP:
                return True
            if self.state.placing is not None and self.state.placing.startswith("spell:"):
                if self._cast_at(self.state.placing[6:], event.world_x, event.world_y) and not event.shift:
                    self.state.placing = None
                return True
            tile = self.presentation.tile_at(event.world_x, event.world_y)
            if self.state.placing == "gate":
                door = self.presentation.door_at(tile)
                if door is not None and self._try(lambda: self.world.build_door(door)):
                    self._record("gate", door)
                    self.state.placing = None
                return True
            if self.state.placing is not None and tile is not None:
                kind = self.state.placing
                if self._try(lambda: self.world.build(kind, tile)):
                    self._record("build", kind, list(tile))
                    if not event.shift:
                        self.state.placing = None
                return True
            tower = self.world.tower_at(tile) if tile is not None else None
            self.state.selected = tower
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
            if name == "upgrade" and self.state.selected is not None:
                need = self.world.rank_needs(self.state.selected)
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
            self._open_menu()
        elif name in ("upgrade", "sell", "cleanse"):
            getattr(self, name)()
