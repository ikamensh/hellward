"""One defence on the server: the world, the client's orders, the person's replay, or a scripted player at the controls.

The client keeps the clock: it asks for whole steps (:meth:`Battle.advance`) as its frames pass, scaled by the pace
it shows, and nothing moves while it asks for none (paused, or a window that is not drawing). Each step answers with
a frame (:func:`hellward.server.protocol.frame`). An order (:meth:`Battle.order`) takes effect at once, between
steps, as a click did in the 2D game: it is accepted, and its events go out in a frame of their own, or refused
with the reason the client plays. Accepted orders by a person go to the replay log, in the form
:class:`~hellward.sim.players.ghost.Ghost` replays (towers by tile, monsters by where they stood).

A scripted player plays exactly as :func:`hellward.sim.players.hands.defend` plays it: the same hands, the same
reaction time for the seed, acting before every step. That is the demo, and what the protocol test checks.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hellward.run import Drawn
from hellward.run import describe as describe_goal
from hellward.run import make as make_goal
from hellward.server import protocol
from hellward.sim import tuning
from hellward.sim.balance import BALANCE
from hellward.sim.bonus import draw as draw_pack
from hellward.sim.campaign import ORDER, Location, first_offering, offers
from hellward.sim.content import SPELLS, Curse
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.modes import MODES
from hellward.sim.kit import Kit
from hellward.sim.model import SIM_DT, Planner, Refused, World
from hellward.sim.planner import Decision, Option
from hellward.sim.players.ghost import issue as replay_command
from hellward.sim.players.hands import AIM_GAP, REACT, Hands, Player, react_for
from hellward.sim.skills import perks

PERSON_REACT = 0.6   # the person's hands: only their record of the leaders' signs uses it


class _LoggedDecision:
    """One logged decision, answered as the planner's handle would answer it."""

    def __init__(self, logged: dict) -> None:
        self.logged = logged

    def result(self) -> Decision:
        cast = self.logged["cast"]
        return Decision(leader=0, cast=None if cast is None else Option(Curse(cast[0]), tuple(cast[1])),
                        retry=float(self.logged["retry"]))


class _ReplayPlanner:
    """The resume's planner: the logged decisions, in order, per leader. No rollouts, no processes, and an
    empty queue is a bug: the replayed world asks exactly what the played world asked."""

    def __init__(self, decisions: dict) -> None:
        self.queues = {int(leader): list(queue) for leader, queue in decisions.items()}

    def __call__(self, world: World, leader: int):
        queue = self.queues.get(leader)
        if not queue:
            raise RuntimeError(f"the log holds no more decisions for leader {leader}")
        return _LoggedDecision(queue.pop(0))


class Battle:
    def __init__(self, location: Location, *, learned: frozenset[str] = frozenset(), loadout: Loadout = EMPTY_LOADOUT,
                 seed: int = 0, planner: Planner | None, player: Player | None = None,
                 breach_claim: str | None = None, replays: Path | None = None,
                 on_outcome: Callable[[World], dict] | None = None, kit: Kit | None = None,
                 run_seed: int | None = None, run_index: int | None = None,
                 drawn: tuple[Drawn, ...] = (), on_save: Callable[[], None] | None = None,
                 modes: frozenset[str] = frozenset()) -> None:
        if kit is not None:   # a run's defence: the Kit deals everything, down to the pool as its lives
            location, learned, loadout, seed = kit.location, kit.learned, kit.loadout, kit.seed
        self.location = location
        self.kit = kit
        self.player = player
        self.modes = modes | {"first"}   # the profile's taught strategies, foremost always among them
        if player is not None:
            learned = player.draft(location, 3 * ORDER.index(location.key))
            loadout = getattr(player, "loadout", EMPTY_LOADOUT)
        self.learned = learned
        self.seed = seed
        if kit is not None:
            self.world = kit.world(planner=planner)
        else:
            self.world = World(location, perks=perks(learned, ORDER.index(location.key)), seed=seed, planner=planner,
                               loadout=loadout)
        if player is not None:
            self.hands = Hands(self.world, react_for(seed, getattr(player, "reaction", REACT)),
                               getattr(player, "aim_gap", AIM_GAP))
        else:
            self.hands = Hands(self.world, PERSON_REACT)
        self.hands.record.skills = learned
        self.breach_claim = breach_claim
        self.replays = replays
        self.on_outcome = on_outcome
        self.result: dict | None = None    # what on_outcome made of the decided defence: the campaign's rewards
        self.paused = False
        self.steps = 0
        self.commands: list[list] = []      # the person's accepted orders, [time, name, args...]
        self.run_seed, self.run_index = run_seed, run_index
        self.repeats = 0                    # bonus waves summoned: the draw counts them down in price
        self.drawn = drawn
        self.folds = [make_goal(goal) for goal in drawn]
        if kit is not None:
            for fold in self.folds:
                fold.start(kit)
        self.all_events: list[tuple] = []   # every event, for the run's settling at the outcome
        self.log: dict = {"commands": self.commands, "decisions": {}, "marks": []}
        self.on_save = on_save
        self._dirty = False                 # the log grew since the last save
        self._warnings: list[str] = []
        self._second = -1
        self._skip: tuple[tuple, dict | None] | None = None   # the grind offer's memo: key, offer
        self._replaying = False           # a resume's replay steps the world: no offers are predicted

    def start(self) -> dict:
        message = protocol.battle_start(self.world, demo=self.player is not None and self.on_outcome is None,
                                        breach_claim=self.breach_claim)
        message["scripted"] = self.player is not None   # a scripted player plays: the client only watches
        message["salvage_sale_gold"] = BALANCE.salvage_sale_gold()
        message["breach_cash"] = BALANCE.breach_cache()
        message["skills"] = sorted(self.learned)
        message["run"] = self.kit is not None
        message["boss_strike_lives"] = tuning.integer("battle.boss_strike_lives")
        message["goals"] = [{"key": goal.key, "arg": goal.arg, "line": describe_goal(goal),
                             "verdict": fold.verdict()}
                            for goal, fold in zip(self.drawn, self.folds)]
        message["modes"] = [{"key": key, "name": MODES[key].name, "words": MODES[key].words}
                            for key in MODES if key in self.modes]
        return message

    # -- The clock ------------------------------------------------------------------------------

    def advance(self, steps: int) -> list[dict]:
        """Play whole steps; a frame for each. A paused or decided fight does not move."""
        frames = []
        world = self.world
        for _ in range(steps):
            if self.paused or world.outcome is not None:
                break
            if self.player is not None:
                self.player.act(self.hands)
            world.step(SIM_DT)
            self.steps += 1
            frames.append(self._flush(SIM_DT))
        return frames

    def _refresh_skip(self) -> None:
        """The grind's offer, predicted at most once per wave, orders and wave state: a person's battle
        only, never a replay (its leaders read their decisions from the log, which a prediction must not
        drink). A prediction stands while no orders land: the live wave walks the predicted steps."""
        world = self.world
        if self.player is not None or self._replaying:
            self._skip = None
            return
        key = (world.wave, len(self.commands), bool(world.schedule), world.bonus is None,
               world.breach_remaining)
        if self._skip is not None and self._skip[0] == key:
            return
        offer = {"wave": world.wave, "bonus": BALANCE.income_unit()} if world.predict_clean() else None
        self._skip = (key, offer)

    def _flush(self, dt: float) -> dict:
        world = self.world
        self.hands.observe(world.events, dt=dt)
        if self.kit is not None:
            self.all_events.extend(world.events)
            if int(world.time) > self._second:   # a step mark at least once a second, for the resume
                self._second = int(world.time)
                world.events.append(("step", round(world.time, 3)))
                self.all_events.append(world.events[-1])
                self.log["marks"].append(round(world.time, 3))
                self._dirty = True
            for e in world.events:
                if e[0] == "plan":
                    by_leader = self.log["decisions"].setdefault(e[1], [])
                    cast = e[2].cast
                    by_leader.append({"cast": None if cast is None else [cast.curse.value, list(cast.spot)],
                                      "retry": e[2].retry})
                    self._dirty = True
                elif e[0] == "wave":
                    self._dirty = True   # the save is written at every wave's start
            synth: list[tuple] = []
            for goal, fold in zip(self.drawn, self.folds):
                before = fold.verdict()
                for e in world.events:
                    fold.observe(e)
                if fold.verdict() != before:
                    synth.append(("goal", goal.key, fold.verdict()))
            world.events.extend(synth)
            self.all_events.extend(synth)
            message = protocol.frame(world, self.steps, world.events)
            world.events.clear()
        else:
            message = protocol.frame(world, self.steps, world.events)
            world.events.clear()
        if self._warnings:
            message["warnings"] = self._warnings
            self._warnings = []
        if world.outcome is not None and self.result is None:
            if self.kit is not None:
                world.events = self.all_events   # the settling replays the whole defence
            self.result = self.on_outcome(world) if self.on_outcome is not None else {}
            self._write_replay()
            message["result"] = self.result
        elif self._dirty and self.on_save is not None:
            self.on_save()
            self._dirty = False
        self._refresh_skip()
        message["state"]["skip_offer"] = self._skip[1] if self._skip is not None else None
        return message

    def resume_from(self, log: dict, planner: Planner | None) -> None:
        """Replay the save's log on to its last mark: its commands through the hands, its leaders' decisions
        from the log instead of a live planner. Quitting never rewinds more than a second: whatever came
        after the last mark is let go. The live planner takes over from the mark."""
        assert self.kit is not None
        self.log = {"commands": [list(entry) for entry in log["commands"]], "decisions": {}, "marks": []}
        self.commands = self.log["commands"]
        saved, self.on_save = self.on_save, None   # the replay regrows the log; it writes nothing
        self.world.planner = _ReplayPlanner(log["decisions"])
        self._replaying = True
        try:
            end = log["marks"][-1] if log["marks"] else 0.0
            pending = sorted(self.log["commands"], key=lambda entry: entry[0])
            while self.world.time < end - 1e-9 and self.world.outcome is None:
                while pending and pending[0][0] <= self.world.time + 1e-9:
                    _, name, *rest = pending.pop(0)
                    if name == "summon":
                        self._summon(int(rest[0]))
                    elif not replay_command(self.world, self.hands, name, tuple(rest)):
                        raise RuntimeError(f"the replayed {name} was refused")
                self.advance(1)
        finally:
            self.world.planner = planner
            self.on_save = saved
            self._replaying = False

    # -- Orders ---------------------------------------------------------------------------------

    def order(self, name: str, args: dict[str, Any]) -> tuple[str | None, dict | None]:
        """Carry out one of the client's orders: (None, its frame) when accepted, (why, None) when refused."""
        if self.player is not None and name not in ("pause",):
            return "The leaders' watcher is playing this defence.", None
        if self.world.outcome is not None and name != "pause":
            return "The defence is decided.", None
        handler = getattr(self, f"_{name}", None)
        if handler is None or name.startswith("_"):
            raise ValueError(f"unknown battle order {name!r}")
        self._warnings = [warned for fold in self.folds
                          if (warned := fold.warn(name, args)) is not None]
        at = self.world.time   # before the handler: a skip jumps the clock it is logged at
        try:
            logged = handler(**args)
        except Refused as refusal:
            self._warnings = []
            return str(refusal), None
        if logged is not None:
            self.commands.append([at, name, *logged])
            self._dirty = True   # every accepted order joins the resume's log
        return None, self._flush(0.0)

    def _tower(self, tower: int):
        found = self.world.towers.get(tower)
        if found is None:
            raise Refused("That tower is gone.")
        return found

    def _build(self, kind: str, tile: list[int]) -> list:
        if not offers(self.location, kind):
            raise Refused(_not_here(self.location, kind))
        self.world.build(kind, (int(tile[0]), int(tile[1])))
        return [kind, [int(tile[0]), int(tile[1])]]

    def _upgrade(self, tower: int) -> list:
        t = self._tower(tower)
        self.world.upgrade(t.id)
        return [list(t.tile)]

    def _sell(self, tower: int) -> list:
        t = self._tower(tower)
        self.world.sell(t.id)
        return [list(t.tile)]

    def _gate(self, door: int) -> list:
        if not offers(self.location, "gate"):
            raise Refused(_not_here(self.location, "gate"))
        self.world.build_door(int(door))
        return [int(door)]

    def _clear(self, tile: list[int]) -> list:
        self.world.clear((int(tile[0]), int(tile[1])))
        return [[int(tile[0]), int(tile[1])]]

    def _call_wave(self) -> list:
        if not self.world.can_call_wave:
            raise Refused("The next wave is already coming." if self.world.wave + 1 < len(self.world.waves)
                          else "That was the last wave.")
        self.world.call_wave()
        return []

    def _breach(self, mode: str) -> list:
        self.world.choose_breach(mode)
        return [mode]

    def _sell_salvage(self) -> list:
        if not self.world.salvage_held:
            raise Refused("No salvage to sell.")
        self.world.sell_salvage(1)
        return [1]

    def _smite(self, monster: int) -> list:
        self._ready("smite")
        target = self.world.monster(int(monster))
        if target is None or target.hp <= 0:
            raise Refused("Smite strikes a monster: click on one.")
        x, y = self.world.position(target)
        self.world.smite(target.id)
        return [x, y]

    def _hymn(self, tower: int) -> list:
        self._ready("hymn")
        t = self._tower(tower)
        self.world.hymn(t.id)
        return [list(t.tile)]

    def _meteor(self, x: float, y: float) -> list:
        self._ready("meteor")
        self.world.meteor(float(x), float(y))
        return [float(x), float(y)]

    def _orb(self, x: float, y: float) -> list:
        self._ready("orb")
        self.world.orb(float(x), float(y))
        return [float(x), float(y)]

    def _pause(self, paused: bool) -> None:
        self.paused = bool(paused)
        return None

    def _summon(self, stake: int) -> list:
        """Wager the stake's bonus wave: a run's bet, drawn from its seed."""
        if self.kit is None or self.run_seed is None or self.run_index is None:
            raise Refused("Bonus waves are a run's wager.")
        pack = draw_pack(self.location, int(stake), self.run_seed, self.run_index, self.repeats,
                         self.world.wave)
        self.world.summon(pack)
        self.repeats += 1
        return [int(stake)]

    def _set_mode(self, tower: int, mode: str) -> list:
        """Teach a tower its strategy for this defence; untaught strategies are refused."""
        if mode not in self.modes:
            name = MODES[mode].name if mode in MODES else mode
            raise Refused(f"{name} is not taught: learn it in the forge.")
        t = self._tower(tower)
        self.world.set_mode(t.id, mode)
        return [list(t.tile), mode]

    def _skip_grind(self) -> list:
        """Skip the surely clean wave: the offer must stand for this wave and these orders."""
        key = (self.world.wave, len(self.commands), bool(self.world.schedule),
               self.world.bonus is None, self.world.breach_remaining)
        if self._skip is None or self._skip[1] is None or self._skip[0] != key:
            raise Refused("No wave is surely clean: the grind must be fought.")
        self.world.skip_grind()
        return []

    def _ready(self, key: str) -> None:
        """An aimed spell is cast in the fight's own time, and only where it is offered; the world refuses the rest
        (recharge, mana)."""
        if self.paused:
            raise Refused("Spells are cast in the fight's own time: resume it first (P).")
        if not offers(self.location, key):
            raise Refused(f"{SPELLS[key].name} is not yet yours: you learn it for {first_offering(key).called}.")

    # -- The replay -----------------------------------------------------------------------------

    def replay(self) -> dict:
        world = self.world
        return {"version": 2, "location": self.location.key, "seed": self.seed, "skills": sorted(self.learned),
                "loadout": list(world.loadout.equipped), "outcome": world.outcome, "lives": world.lives,
                "time": world.time, "commands": self.commands}

    def _write_replay(self) -> None:
        """The moment a person's defence is decided: their orders as one JSON file in the replays folder.
        A player who leaves mid-fight writes nothing; a scripted player writes nothing."""
        if self.replays is None or self.player is not None:
            return
        self.replays.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.replays / f"{stamp}-{self.location.key}.json"
        n = 1
        while path.exists():
            n += 1
            path = self.replays / f"{stamp}-{self.location.key}-{n}.json"
        path.write_text(json.dumps(self.replay()))


def _not_here(location: Location, thing: str) -> str:
    try:
        arrival = first_offering(thing).called
    except KeyError:
        return f"Not in {location.called}: it is not offered yet."
    return f"Not in {location.called}: it arrives in {arrival}."
