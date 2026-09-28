"""A ghost: the replay of one person's logged defence, as a scripted player.

A log is what :class:`~hellward.ui.battle.BattleScene` writes for a defence a person plays: the location, the
seed, the skills learned and every command with the time it took effect. The ghost learns the log's skills and
issues each command through the hands when the world's time reaches the logged time: builds, upgrades, sells,
gates and wave calls as they were given, a cleanse on the tower standing on the logged tile, a smite on the
monster nearest the logged point, a meteor or an orb at the logged point. Whatever the world refuses (a tower
the ghost cannot yet afford, since the monsters were made tougher) is tried again every step for ten seconds of
game time, then let go, so a harder location still plays out to its end.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hellward.sim.campaign import Location
from hellward.sim.items import Loadout
from hellward.sim.model import Refused, World
from hellward.sim.players.hands import Hands
from hellward.sim.skills import cost

RETRY = 10.0    # how long a refused command is tried again, in seconds of game time, before it is dropped


def _tile(value: Any) -> tuple[int, int]:
    return (int(value[0]), int(value[1]))


class Ghost:
    """Replays the defence in a battle scene's log (its path, or the log itself)."""

    reaction = (0.0, 0.0)   # the log already holds the person's own timing: the hands add no delay of theirs
    aim_gap = 0.0

    def __init__(self, path_or_dict: str | Path | dict[str, Any]) -> None:
        data: dict[str, Any] = path_or_dict if isinstance(path_or_dict, dict) else json.loads(Path(path_or_dict).read_text())
        if data.get("version") != 2:
            raise ValueError(f"a ghost only replays a version 2 log, not {data.get('version')!r}")
        self.location: str = str(data["location"])
        self.seed: int = int(data["seed"])
        self.learned: frozenset[str] = frozenset(str(key) for key in data["skills"])
        self.loadout = Loadout(tuple(data["loadout"]))
        self.commands: list[tuple[float, str, tuple[Any, ...]]] = [
            (float(entry[0]), str(entry[1]), tuple(entry[2:])) for entry in data["commands"]]
        self.name = f"ghost:{Path(path_or_dict).stem}" if not isinstance(path_or_dict, dict) else "ghost"
        self._next = 0
        self._pending: tuple[str, tuple[Any, ...]] | None = None
        self._since = 0.0

    def skills(self, location: Location, sigils: int) -> frozenset[str]:
        """The log's skills, all of them: a ghost trims nothing to fit, so too few sigils is an error."""
        if cost(self.learned) > sigils:
            raise ValueError(f"{self.name} learned {cost(self.learned)} sigils' worth of skills with {sigils}")
        return self.learned

    def act(self, hands: Hands) -> None:
        world = hands.world
        if self._pending is not None:
            if self._issue(hands, self._pending):
                self._pending = None
                self._next += 1
            elif world.time - self._since > RETRY:
                self._pending = None    # ten seconds without effect: let it go and play on
                self._next += 1
            else:
                return                  # still waiting: what comes next waits too, in the logged order
        while self._next < len(self.commands):
            when, name, args = self.commands[self._next]
            if when > world.time + 1e-9:
                break
            if self._issue(hands, (name, args)):
                self._next += 1
            else:
                self._pending = (name, args)
                self._since = world.time
                break

    def _issue(self, hands: Hands, command: tuple[str, tuple[Any, ...]]) -> bool:
        """Give one logged command, through the hands. Whether it took effect (a refusal is retried later)."""
        world = hands.world
        name, args = command
        try:
            if name == "build":
                world.build(str(args[0]), _tile(args[1]))
            elif name == "upgrade":
                tower = world.tower_at(_tile(args[0]))
                if tower is None:
                    raise Refused("No tower stands there yet.")
                world.upgrade(tower.id)
            elif name == "sell":
                tower = world.tower_at(_tile(args[0]))
                if tower is None:
                    raise Refused("No tower stands there yet.")
                world.sell(tower.id)
            elif name == "gate":
                world.build_door(int(args[0]))
            elif name == "call_wave":
                world.call_wave()
            elif name == "breach":
                world.choose_breach(str(args[0]))
            elif name == "sell_salvage":
                world.sell_salvage(int(args[0]))
            elif name == "cleanse":
                tower = world.tower_at(_tile(args[0]))
                if tower is None:
                    raise Refused("No tower stands there yet.")
                hands.cleanse(tower.id)
            elif name == "smite":
                target = self._nearest(world, float(args[0]), float(args[1]))
                if target is None:
                    raise Refused("No monster walks there yet.")
                hands.smite(target)
            elif name == "meteor":
                hands.meteor(float(args[0]), float(args[1]))
            elif name == "orb":
                hands.orb(float(args[0]), float(args[1]))
            else:
                raise ValueError(f"unknown replay command {name!r}")
        except Refused:
            return False
        return True

    @staticmethod
    def _nearest(world: World, x: float, y: float) -> int | None:
        """The monster nearest a logged point, as a person clicking there would strike it: any monster on the
        map, the closest first, the earliest raised breaking a tie."""
        best: int | None = None
        best_d = 0.0
        for m in world.monsters:
            mx, my = world.position(m)
            d = (mx - x) * (mx - x) + (my - y) * (my - y)
            if best is None or d < best_d:
                best, best_d = m.id, d
        return best
