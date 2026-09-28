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

from saga2d import Camera, RenderLayer, Scene

from hellward.art.sprites import Art
from hellward.audio.music import track_for
from hellward.sim.campaign import CATHEDRAL, Location, first_offering, offers
from hellward.sim.content import CURSES, DOOR, MONSTERS, SPELLS
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.model import SIM_DT, Monster, Refused, Tower, World
from hellward.sim.players.hands import Hands, Player
from hellward.sim.skills import NO_PERKS, SKILLS, Perks
from hellward.ui import style
from hellward.ui.effects import Effects
from hellward.ui.hud import BUILD, NEW_TOWERS, TOP, Hud
from hellward.ui.lighting import Lighting
from hellward.ui.menus import PauseScene
from hellward.ui.view import MAP_X, MAP_Y, T, TOWER_SCALE, WorldView, px

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
        self.door_clock: dict[int, float] = {}
        self.last_hold_note = -10.0

    def on_enter(self) -> None:
        self.world = World(self.location, perks=self.perks, seed=self.seed, planner=self.planner, loadout=self.loadout)
        level = self.world.level
        zoom = min(1.0, (WIDTH - 2 * MAP_X) / (level.width * T), (TOP - MAP_Y) / (level.height * T))
        self.camera = Camera((WIDTH, HEIGHT),
                             world_bounds=(MAP_X, MAP_Y, MAP_X + level.width * T, MAP_Y + level.height * T),
                             insets=(0, 0, 0, HEIGHT - TOP), zoom=zoom, min_zoom=min(0.25, zoom))
        self.view = WorldView(self, self.world, self.art)
        self.fx = Effects(self, self.view, self.world)
        self.hud = Hud(self, self.world, breach_claim=self.breach_claim)
        self.lighting = Lighting(self, (MAP_X, MAP_Y), (self.world.level.width * T, self.world.level.height * T))
        self.hands = Hands(self.world, react=0.6)
        if self.settings is not None:
            self.fx.show_thoughts = self.settings["minds"]
        self.hud.banner(self.location.name, "Hold the sanctuary. The first wave comes soon.", life=4.5)
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
                self.view.before_step()
                world.step(SIM_DT)
                self.hands.observe(world.events)
                self._route()
        if self.selected is not None and self.selected.id not in world.towers:
            self.selected = None
        self.fx.selected = self.selected.id if self.selected is not None else -1
        self.view.sync(self.acc / SIM_DT if not self.paused else 1.0, dt)
        self.fx.update(dt)
        self.hud.update(dt)
        self._door_blows(dt)
        self.lighting.render(self.view.lights() + self.fx.lights())
        if world.outcome is not None:
            if self.on_outcome is not None:
                callback, self.on_outcome = self.on_outcome, None
                callback(world)
            self._write_replay()
            self.ended += dt
            if self.ended > 3.0 and self.on_end is not None:
                self.hud.banners.clear()   # the reckoning is drawn over this scene
                callback, self.on_end = self.on_end, None
                callback(world)

    def _door_blows(self, dt: float) -> None:
        if self.paused:
            return
        for door in self.world.doors:
            if not door.built:
                continue
            batterers = sum(1 for m in self.world.monsters if m.door == door.index)
            if not batterers:
                continue
            left = self.door_clock.get(door.index, 0.0) - dt * self.speed
            if left <= 0:
                left = 0.55
                x, y = self.world.level.doors[door.index]
                self.sound.play("door_hit", volume=min(1.0, 0.5 + 0.1 * batterers))
                cx, cy = px(x + 0.5, y + 0.5)
                self.fx.burst("fx/dust", cx, cy - 18, 3, speed=(20, 60), size=(7, 7))
            self.door_clock[door.index] = left

    def _event(self, e: tuple) -> None:
        self.fx.event(e)
        kind = e[0]
        world = self.world
        sound = self.sound
        if kind == "wave":
            index = e[1]
            last = index == len(world.waves) - 1
            subtitle = "The last wave." if last else f"Wave {index + 1} of {len(world.waves)}"
            self.hud.banner(world.location.wave_names[index], subtitle, color=style.BLOOD if last else style.GOLD)
            sound.play("wave")
            if last and any(g.kind == "azazel" for g in world.waves[index].groups):
                sound.music("boss")
        elif kind == "cleared":
            if e[2]:
                mend = "" if not world.doors else " Gates mend fully." if world.perks.gate_mend >= 1 else " Gates mend by half."
                self.hud.banner("The wave is broken", f"+{e[2]} gold.{mend}", life=2.4)
            sound.play("cleared")
        elif kind == "bolt":
            cue = {"arrow": "arrow_cast", "pyre": "fire_cast", "frost": "frost", "plague": "venom_cast"}[e[1].kind]
            sound.play(cue, volume=0.6)
        elif kind == "impact":
            bolt = e[1]
            cue = ("fireball" if bolt.splash > 0 else "fire_hit") if bolt.kind == "pyre" else (
                "arrow_hit" if bolt.kind == "arrow" else "frost" if bolt.kind == "frost" else "venom_hit")
            sound.play(cue, volume=0.7)
        elif kind == "chain":
            sound.play("lightning", volume=0.7)
        elif kind == "nova":
            sound.play("frost", volume=0.7)
        elif kind == "amplify":
            sound.play("curse", volume=0.7)
        elif kind == "twister":
            sound.play("frost", volume=0.6)
        elif kind == "corpse_explosion":
            sound.play("fire_hit", volume=0.8)
        elif kind == "death":
            sound.play(f"death_{e[2]}", volume=0.8)
            if e[5] >= 3:
                sound.play("gold")
        elif kind == "salvage":
            self.hud.note(f"Salvage recovered ({world.salvage_held}). Bank it after victory or sell during a break.", style.GOLD)
        elif kind == "salvage_sold":
            self.hud.note(f"Sold {e[1]} salvage for {e[2]} battle gold.", style.GOLD)
            sound.play("gold")
        elif kind == "breach_choice":
            if e[1] == "decline":
                self.hud.note("The side entrance stays sealed.", style.DIM)
            else:
                self.hud.note(f"The side entrance opens for {'a trophy' if e[1] == 'trophy' else 'a cash cache'}.", style.UNIQUE)
        elif kind == "breach_elite":
            self.hud.banner(e[2], "An elite comes from the side entrance.", color=style.UNIQUE)
        elif kind == "breach_cleared":
            reward = "Its trophy is yours after a victory." if e[1] == "trophy" else "Its cash cache pays now."
            self.hud.note(f"Side pack defeated. {reward}", style.HOLY)
        elif kind == "breach_failed":
            self.hud.note("A side monster escaped. Its cache is lost.", style.BLOOD)
        elif kind == "breach_cash":
            self.hud.note(f"Side cache: +{e[1]} gold.", style.GOLD)
            sound.play("gold")
        elif kind == "leak":
            sound.play("leak")
            self.hud.note(f"{MONSTERS[e[2]].name} reached the sanctuary. -{e[3]} life.", style.BLOOD)
        elif kind == "door_broken":
            sound.play("door_break")
            self.hud.note("A warded gate has been broken.", style.BLOOD)
        elif kind == "door_built":
            sound.play("door_build")
        elif kind == "built":
            sound.play("build")
        elif kind == "upgraded":
            sound.play("upgrade")
        elif kind == "sold":
            sound.play("sell")
        elif kind == "cleansed":
            sound.play("cleanse")
        elif kind == "chant":
            leader = world.monster(e[1])
            sound.play("chant")
            if leader is not None:
                self.hud.note(f"{leader.kind.name} chants {CURSES[e[2]].name} on the marked spot.", style.CURSE)
        elif kind == "cursed":
            sound.play("curse")
        elif kind == "fizzle":
            sound.play("fizzle")
        elif kind == "smite":
            sound.play("smite")
        elif kind == "meteor_cast":
            sound.play("meteor_fall")
        elif kind == "meteor":
            sound.play("meteor")
        elif kind == "orb":
            sound.play("orb")
        elif kind == "broken":
            sound.play("broken")
            leader = world.monster(e[1])
            self.hud.note(f"{leader.kind.name if leader else 'The leader'} loses its curse, and its next will not break.",
                          style.HOLY)
        elif kind == "ward_holds":
            sound.play("ward")
            tower = world.towers.get(e[2])
            if tower is not None:
                self.hud.note(f"{CURSES[e[3]].name} breaks on the ward of the {tower.kind.name}.", style.HOLY)
        elif kind == "ponder":
            sound.play("ponder", volume=0.6)
        elif kind == "plan":
            decision = e[2]
            leader = world.monster(e[1])
            if leader is None:
                return
            if decision.cast is not None:
                self.hud.note(f"{leader.kind.name} weighed {decision.considered}: {CURSES[decision.cast.curse].name} "
                              f"on the marked spot, +{decision.cast.gain:.0f} life", style.UNIQUE)
            elif decision.later is not None and self.hud.clock - self.last_hold_note > 6:
                self.last_hold_note = self.hud.clock
                self.hud.note(f"{leader.kind.name} waits: in {decision.later.delay:.0f}s its curse is worth more", style.DIM)
        elif kind == "victory":
            sound.play("victory")
            sound.music("title")
        elif kind == "defeat":
            sound.play("defeat")

    # -- Commands --------------------------------------------------------------------------------

    def cost(self, key: str) -> int:
        return self.world.door_cost if key == "gate" else self.world.cost(key)

    def _route(self) -> None:
        """Hand the world's events to the effects and the sound, and clear them."""
        for event in self.world.events:
            self._event(event)
        self.world.events.clear()

    def _try(self, action: Callable[[], Any]) -> bool:
        try:
            action()
        except Refused as refusal:
            self.hud.note(str(refusal), style.DIM)
            self.sound.play("refuse")
            return False
        self.hands.observe(self.world.events, dt=0.0)   # a command's events now, not after a step that may be paused away
        self._route()
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
        self.hud.note(why, style.DIM)
        self.sound.play("refuse")

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
            target = self.monster_at(wx, wy) or self.nearest_monster(wx, wy, T)
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
        self.fx.show_thoughts = not self.fx.show_thoughts
        if self.settings is not None:
            self.settings["minds"] = self.fx.show_thoughts
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
        self.fx.show_thoughts = self.settings["minds"]

    # -- Pointer ---------------------------------------------------------------------------------

    def tile_at(self, wx: float, wy: float) -> tuple[int, int] | None:
        tx, ty = math.floor((wx - MAP_X) / T), math.floor((wy - MAP_Y) / T)
        level = self.world.level
        if 0 <= tx < level.width and 0 <= ty < level.height:
            return tx, ty
        return None

    def monster_at(self, wx: float, wy: float) -> Monster | None:
        best, best_d = None, 1e9
        for figure in self.view.figures.values():
            m = figure.monster
            cx, cy = self.view.chest(m)
            d = math.hypot(wx - cx, wy - cy)
            if d < m.kind.size * T * 0.7 and d < best_d:
                best, best_d = m, d
        return best

    def nearest_monster(self, wx: float, wy: float, within: float) -> Monster | None:
        """The monster nearest a point within ``within`` pixels, a leader before any other."""
        best, best_key = None, (True, within)
        for figure in self.view.figures.values():
            m = figure.monster
            cx, cy = self.view.chest(m)
            d = math.hypot(wx - cx, wy - cy)
            key = (m.kind.leader is None, d)
            if d <= within and key < best_key:
                best, best_key = m, key
        return best

    def door_at(self, tile: tuple[int, int] | None) -> int | None:
        if tile is None:
            return None
        for i, door in enumerate(self.world.level.doors):
            if abs(door[0] - tile[0]) + abs(door[1] - tile[1]) <= 1:
                return i
        return None

    def handle_input(self, event) -> bool:
        if event.type == "click":
            if event.button == "right":
                self.placing = None
                self.selected = None
                return True
            control = self.hud.hit(event.x, event.y)
            if control is not None:
                self._control(control.name, control.enabled)
                return True
            if event.y >= TOP:
                return True
            if self.placing is not None and self.placing.startswith("spell:"):
                if self._cast_at(self.placing[6:], event.world_x, event.world_y) and not event.shift:
                    self.placing = None
                return True
            tile = self.tile_at(event.world_x, event.world_y)
            if self.placing == "gate":
                door = self.door_at(tile)
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

    # -- Drawing ---------------------------------------------------------------------------------

    def draw(self) -> None:
        world = self.world
        mouse = self.game.mouse_position
        hovered = None
        if mouse is not None and mouse[1] < TOP:
            wx, wy = self.camera.screen_to_world(*mouse)
            hovered = self.monster_at(wx, wy)
            tile = self.tile_at(wx, wy)
            if self.placing == "gate":
                self._gate_sockets(self.door_at(tile))
            elif self.placing is not None and self.placing.startswith("spell:"):
                self._aim(self.placing[6:], wx, wy, hovered)
            elif self.placing is not None and tile is not None:
                self._ghost(self.placing, tile)
        if self.selected is not None:
            # an aura is not a reach: Dim Vision does nothing to it, so the ring shows the aura's own radius
            reach = self.selected.stats.range if self.selected.kind.key == "grove" else self.selected.reach
            self._ring(self.selected.centre, reach, (230, 190, 100, 220))
        self._bars()
        self.fx.draw()
        self.hud.draw(placing=self.placing, selected=self.selected, hovered=hovered, speed=self.speed, paused=self.paused,
                      mouse=mouse, costs=self.cost)
        if mouse is not None and mouse[1] < TOP and self.placing is None and hovered is None:
            tile = self.tile_at(*self.camera.screen_to_world(*mouse))
            tower = world.tower_at(tile) if tile is not None else None
            if tower is not None:
                self.hud.tower_tip(tower, mouse)
        if self.paused:
            with self.screen_layer(4):
                self.draw_text("Paused", 640, 330, style="banner", anchor_x="center", anchor_y="center")
                self.draw_text("P resumes", 640, 372, font_size=16, color=style.BONE, anchor_x="center", anchor_y="center")

    def _ring(self, centre: tuple[float, float], reach: float, color, fill: bool = True) -> None:
        cx, cy = px(*centre)
        r = reach * T
        if fill:
            self.draw_circle(cx, cy, r, color[:3] + (26,), space="world", layer=RenderLayer.EFFECTS)
        steps = 64
        for i in range(steps):
            a0, a1 = 2 * math.pi * i / steps, 2 * math.pi * (i + 1) / steps
            self.draw_line(cx + r * math.cos(a0), cy + r * math.sin(a0), cx + r * math.cos(a1), cy + r * math.sin(a1), color, 1.6,
                           space="world", layer=RenderLayer.EFFECTS)

    def _aim(self, key: str, wx: float, wy: float, hovered: Monster | None) -> None:
        """Where a held spell would strike: its circle on the floor, or the monster Smite would hit."""
        ready = self.world.mana >= self.world.spell_cost(key) and not self.paused
        if key == "smite":
            target = hovered or self.nearest_monster(wx, wy, T)
            if target is not None:
                x, y = self.view.chest(target)
                r = target.kind.size * T * 0.7
                self._ring(((x - MAP_X) / T, (y - MAP_Y) / T), r / T, (255, 226, 140, 230) if ready else (160, 140, 120, 160))
            return
        color = {"meteor": (255, 140, 60, 220), "orb": (150, 210, 255, 220)}[key] if ready else (160, 140, 120, 160)
        self._ring(((wx - MAP_X) / T, (wy - MAP_Y) / T), SPELLS[key].radius, color)

    def _ghost(self, key: str, tile: tuple[int, int]) -> None:
        level = self.world.level
        ok = level.buildable(*tile) and self.world.tower_at(tile) is None and self.world.gold >= self.cost(key)
        cx, cy = px(tile[0] + 0.5, tile[1] + 0.5)
        cell, k = self.art.tower, TOWER_SCALE
        if self.game.assets.has_image(f"tower/{key}/0"):
            self.draw_image(f"tower/{key}/0", cx - cell.origin[0] * k, cy + 0.25 * T - cell.origin[1] * k, cell.size[0] * k,
                            cell.size[1] * k, opacity=0.6, space="world", layer=RenderLayer.EFFECTS)
        else:   # no sprite for the kind yet: a coloured rune disc on its tile
            color = (214, 204, 176, 160) if key == "altar" else (120, 230, 60, 160)
            self.draw_circle(cx, cy, T * 0.42, color, space="world", layer=RenderLayer.EFFECTS)
        self.draw_rect(MAP_X + tile[0] * T + 2, MAP_Y + tile[1] * T + 2, T - 4, T - 4, (0, 0, 0, 0),
                       border_color=(120, 220, 120, 200) if ok else (230, 60, 60, 220), border_width=2, space="world",
                       layer=RenderLayer.EFFECTS)
        self._ring((tile[0] + 0.5, tile[1] + 0.5), self.world.tower_levels[key][0].range, (120, 220, 120, 200) if ok else (230, 60, 60, 200))

    def _gate_sockets(self, hovered: int | None) -> None:
        for i, (x, y) in enumerate(self.world.level.doors):
            door = self.world.doors[i]
            color = (255, 220, 120, 255) if i == hovered else (200, 160, 80, 160)
            if door.built:
                color = (120, 110, 100, 120)
            elif door.rubble:   # broken this wave: it takes a gate again once the wave is cleared
                color = (220, 70, 60, 220)
            self.draw_rect(MAP_X + x * T + 1, MAP_Y + y * T + 1, T - 2, T - 2, (255, 220, 120, 40 if i == hovered else 0),
                           border_color=color, border_width=2.5, space="world", layer=RenderLayer.EFFECTS)

    def _bars(self) -> None:
        world = self.world
        for figure in self.view.figures.values():
            m = figure.monster
            max_hp = m.max_hp
            x, y = self.view.chest(m)
            top = y - m.kind.size * T * 0.75 - 8
            if m.hp < max_hp or m.kind.leader is not None:
                w = 18 + 16 * m.kind.size
                self.draw_rect(x - w / 2 - 1, top - 1, w + 2, 5, (0, 0, 0, 200), space="world", layer=RenderLayer.EFFECTS)
                color = (200, 170, 70, 255) if m.kind.leader is not None else (200, 28, 28, 255)
                self.draw_rect(x - w / 2, top, w * max(0.0, m.hp / max_hp), 3, color, space="world", layer=RenderLayer.UI_WORLD)
            if m.asking is not None:
                dots = "." * (1 + int(self.view.clock * 4) % 3)
                self.draw_text(dots, x, top - 6, font_size=18, color=(220, 150, 255, 255), anchor_x="center", space="world",
                               layer=RenderLayer.UI_WORLD)
        for door in world.doors:
            if door.built and door.hp < world.gate_life:
                x, y = world.level.doors[door.index]
                cx, cy = px(x + 0.5, y + 0.5)
                self.draw_rect(cx - 20, cy - 52, 40, 5, (0, 0, 0, 200), space="world", layer=RenderLayer.EFFECTS)
                self.draw_rect(cx - 19, cy - 51, 38 * door.hp / world.gate_life, 3, (230, 190, 90, 255), space="world", layer=RenderLayer.UI_WORLD)
