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

from hellward.server import protocol
from hellward.sim.balance import BALANCE
from hellward.sim.campaign import ORDER, Location, first_offering, offers
from hellward.sim.content import SPELLS
from hellward.sim.items import EMPTY_LOADOUT, Loadout
from hellward.sim.model import SIM_DT, Monster, Planner, Refused, World
from hellward.sim.players.hands import AIM_GAP, REACT, Hands, Player, react_for
from hellward.sim.skills import perks

PERSON_REACT = 0.6   # the person's hands: only their record of the leaders' signs uses it


class Battle:
    def __init__(self, location: Location, *, learned: frozenset[str] = frozenset(), loadout: Loadout = EMPTY_LOADOUT,
                 seed: int = 0, planner: Planner | None, player: Player | None = None,
                 breach_claim: str | None = None, replays: Path | None = None,
                 on_outcome: Callable[[World], dict] | None = None) -> None:
        self.location = location
        self.player = player
        if player is not None:
            learned = player.skills(location, 3 * ORDER.index(location.key))
            loadout = getattr(player, "loadout", EMPTY_LOADOUT)
        self.learned = learned
        self.seed = seed
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

    def start(self) -> dict:
        message = protocol.battle_start(self.world, demo=self.player is not None and self.on_outcome is None,
                                        breach_claim=self.breach_claim)
        message["scripted"] = self.player is not None   # a scripted player plays: the client only watches
        stage = self.world.stage
        message["salvage_sale_gold"] = BALANCE.salvage_sale_gold(stage)
        message["breach_cash"] = BALANCE.breach_cache(stage)
        message["skills"] = sorted(self.learned)
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

    def _flush(self, dt: float) -> dict:
        world = self.world
        self.hands.observe(world.events, dt=dt)
        message = protocol.frame(world, self.steps, world.events)
        world.events.clear()
        if world.outcome is not None and self.result is None:
            self.result = self.on_outcome(world) if self.on_outcome is not None else {}
            self._write_replay()
            message["result"] = self.result
        return message

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
        try:
            logged = handler(**args)
        except Refused as refusal:
            return str(refusal), None
        if logged is not None:
            self.commands.append([self.world.time, name if name != "smite_threat" else "smite", *logged])
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

    def _cleanse(self, tower: int) -> list:
        t = self._tower(tower)
        self.world.cleanse(t.id)
        return [list(t.tile)]

    def _gate(self, door: int) -> list:
        if not offers(self.location, "gate"):
            raise Refused(_not_here(self.location, "gate"))
        self.world.build_door(int(door))
        return [int(door)]

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

    def _smite_threat(self) -> list:
        """The panel's Q: smite the leader closest to cursing, as the 2D game's Q did."""
        self._ready("smite")
        leader = self.threat()
        if leader is None:
            raise Refused("No leader is pondering or chanting a curse Smite can break.")
        x, y = self.world.position(leader)
        self.world.smite(leader.id)
        return [x, y]

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

    def _ready(self, key: str) -> None:
        """An aimed spell is cast in the fight's own time, and only where it is offered; the world refuses the rest
        (recharge, mana)."""
        if self.paused:
            raise Refused("Spells are cast in the fight's own time: resume it first (P).")
        if not offers(self.location, key):
            raise Refused(f"{SPELLS[key].name} is not yet yours: you learn it for {first_offering(key).called}.")

    def threat(self) -> Monster | None:
        """The leader closest to cursing whose curse Smite can still break: the chant nearest its end, else the
        pondering nearest its end. A marking or resolute leader's curse lands whatever is struck."""
        leaders = self.world.leaders()
        chanting = [m for m in leaders if m.chant_curse is not None and not m.marking]
        if chanting:
            return min(chanting, key=lambda m: (m.chant_left, m.id))
        pondering = [m for m in leaders if m.asking is not None and not m.resolute]
        return min(pondering, key=lambda m: (m.ask_left, m.id)) if pondering else None

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
