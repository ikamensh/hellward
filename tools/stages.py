"""Staged moments of a battle, for frames to look at: the Ballista's bolt, a Hook's drag, a knife at a gate, Battle
Hymn's aura, a monster striking the shrine, a boss cast back, a monster's plate under the mouse.

    uv run python tools/stages.py NAME OUT.json      # then godot/tools/stage.sh renders it (it runs this first)
    uv run python tools/stages.py --list

A stage is a defence the server's demo plays as a ghost's log: towers and orders written here, or a scripted
player's own orders recorded and then changed (the boss's return sells the towers once the boss walks alone). This
plays the same defence directly, which the server reproduces step for step (tests/test_server.py), to find when the
moment comes and which event it is; ``godot/game/scripts/stage.gd`` runs the demo fast up to it, frames the camera on
it and saves its frames. It runs the source simulation: recording a player wraps the World's orders.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hellward.sim import planner, tuning  # noqa: E402
from hellward.sim.campaign import LOCATIONS, ORDER  # noqa: E402
from hellward.sim.items import Loadout  # noqa: E402
from hellward.sim.model import Refused, World  # noqa: E402
from hellward.sim.players import PLAYERS  # noqa: E402
from hellward.sim.players.ghost import Ghost  # noqa: E402
from hellward.sim.players.hands import defend  # noqa: E402

SEED = 1
BOSSES = ("azazel", "bone_priest")
STRIKE = tuning.integer("battle.boss_strike_lives")


class Found(Exception):
    """The moment came: the event and the time of its step."""

    def __init__(self, event: tuple, time: float) -> None:
        self.event, self.time = event, time


def lane_side(world: World, count: int, near: tuple[float, float] | None = None, route: int = 0) -> list[list[int]]:
    """Bare floor beside the monsters' halls, nearest `near` (default: the middle of a route) first."""
    level = world.level
    if near is None:
        trail = level.routes[route].waypoints
        near = trail[len(trail) // 2]
    hall = {(x, y) for y in range(level.height) for x in range(level.width) if level.tile(x, y).value == "P"}
    tiles = [(x, y) for y in range(level.height) for x in range(level.width) if level.tile(x, y).value == "."
             and any((x + dx, y + dy) in hall for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    tiles.sort(key=lambda t: math.hypot(t[0] - near[0], t[1] - near[1]))
    return [list(t) for t in tiles[:count]]


def ghost(location: str, commands: list[list]) -> dict:
    return {"version": 2, "location": location, "seed": SEED, "skills": [], "loadout": [], "outcome": None,
            "lives": 0, "time": 0.0, "commands": commands}


def first(log: dict, wanted: Callable[[World, tuple], bool]) -> tuple[tuple, float]:
    """Play the ghost's defence until an event `wanted` says is the moment."""
    location = str(log["location"])

    def watch(world: World) -> None:
        for e in world.events:
            if wanted(world, e):
                raise Found(e, world.time)

    try:
        world, _ = defend(LOCATIONS[location], Ghost(log), seed=int(log["seed"]), sigils=3 * ORDER.index(location),
                          planner=planner.smart, watch=watch)
    except Found as found:
        return found.event, found.time
    raise LookupError(f"the moment never came at {location} ({world.outcome} at {world.time:.0f} s)")


def _tile(world: World, tower: int) -> list[int]:
    return list(world.towers[tower].tile)


# a World order -> its ghost command's arguments (hellward.sim.players.ghost), taken before the order is carried out
ORDERS: dict[str, Callable[..., list]] = {
    "build": lambda w, kind, tile: ["build", kind, list(tile)],
    "upgrade": lambda w, tower: ["upgrade", _tile(w, tower)],
    "sell": lambda w, tower: ["sell", _tile(w, tower)],
    "build_door": lambda w, index: ["gate", index],
    "call_wave": lambda w: ["call_wave"],
    "choose_breach": lambda w, mode: ["breach", mode],
    "sell_salvage": lambda w, count: ["sell_salvage", count],
    "hymn": lambda w, tower: ["hymn", _tile(w, tower)],
    "smite": lambda w, monster: ["smite", *w.position(w.monster(monster))],
    "meteor": lambda w, x, y: ["meteor", x, y],
    "orb": lambda w, x, y: ["orb", x, y],
}


def recorded(location: str, player_name: str, until: Callable[[World], bool]) -> tuple[dict, float]:
    """A scripted player's defence as a ghost's log, up to the first step after which `until` holds (its time comes
    with it): every order the World carried out, at the time it took effect."""
    player = PLAYERS[player_name](SEED)
    commands: list[list] = []
    originals = {name: getattr(World, name) for name in ORDERS}

    def wrap(name: str) -> Callable:
        def order(world: World, *args: Any) -> Any:
            command = [world.time, *ORDERS[name](world, *args)]
            result = originals[name](world, *args)   # a refusal raises and logs nothing
            commands.append(command)
            return result
        return order

    def watch(world: World) -> None:
        if until(world):
            raise Found((), world.time)

    for name in ORDERS:
        setattr(World, name, wrap(name))
    try:
        world, _ = defend(LOCATIONS[location], player, seed=SEED, sigils=3 * ORDER.index(location),
                          planner=planner.smart, watch=watch)
        time = world.time
    except Found as found:
        time = found.time
    finally:
        for name, fn in originals.items():
            setattr(World, name, fn)
    log = ghost(location, commands)
    log["skills"] = sorted(player.skills(LOCATIONS[location], 3 * ORDER.index(location)))
    log["loadout"] = list(getattr(player, "loadout", Loadout()).equipped)
    return log, time


def replayed(log: dict, time: float) -> World:
    """The ghost's world after the step that reaches `time`."""
    def stop(world: World) -> None:
        if world.time >= time - 1e-9:
            raise Found((world,), world.time)

    location = str(log["location"])
    try:
        defend(LOCATIONS[location], Ghost(log), seed=int(log["seed"]), sigils=3 * ORDER.index(location),
               planner=planner.smart, watch=stop)
    except Found as found:
        return found.event[0]
    raise LookupError(f"the replay ended before {time:.1f} s")


def key(e: tuple) -> Any:
    """What tells the event apart in the client: a bolt's id, else its first field (a tower or a monster)."""
    return e[1].id if e[0] == "bolt" else e[1]


def stage(request: dict, wanted: Callable[[World, tuple], bool], *, frame: str, at: list[int],
          view: tuple[float, ...] = (40.0, 18.0), hud: bool = False, hover: str = "") -> dict:
    """A stage: the demo's request, the event (its name and key) and its step's time, how the camera frames it (on
    the `tower`, the `monster`, both as a `pair`, or the shrine's `door`), the frames to save after it, its pitch and
    distance (and bearing, where the scenery would stand in the way), whether the HUD shows, and a monster kind to
    hover the mouse over."""
    e, time = first(request["replay"], wanted)
    return {"request": request, "event": e[0], "key": key(e), "time": time, "frame": frame, "at": at,
            "view": list(view), "hud": hud, "hover": hover}


def _world(location: str) -> World:
    return World(LOCATIONS[location], seed=1, planner=None)


def ballista() -> dict:
    """The Catacombs: two Ballistas by the hall, the first heavy bolt in flight."""
    w = _world("catacombs")
    builds = [[0.5, "build", "ballista", t] for t in lane_side(w, 2)]
    log = ghost("catacombs", builds + [[1.0, "call_wave"]])
    return stage({"replay": log}, lambda w, e: e[0] == "bolt" and e[1].kind == "ballista",
                 frame="pair", at=[2, 5, 8], view=(32.0, 16.0))


def hook() -> dict:
    """Kurast Docks: Hook Towers by the quay, a Flayer caught and dragged back."""
    w = _world("docks")
    builds = [[0.5, "build", "hook", t] for t in lane_side(w, 3)]
    log = ghost("docks", builds + [[1.0, "call_wave"]])

    def flayer(world: World, e: tuple) -> bool:
        m = world.monster(e[2]) if e[0] == "hook" else None
        return m is not None and m.kind.key == "flayer"
    return stage({"replay": log}, flayer, frame="pair", at=[2, 5, 8, 11, 14], view=(34.0, 15.0))


def knife() -> dict:
    """Kurast Docks: a gate warded across an arch, Knife Posts beside it, a knife thrown at a monster stopped there."""
    w = _world("docks")
    door = w.doors[0]
    posts = lane_side(w, 2, near=door.tile)
    log = ghost("docks", [[0.5, "gate", door.index]] + [[0.6, "build", "knife", t] for t in posts]
                + [[1.0, "call_wave"]])

    def at_gate(world: World, e: tuple) -> bool:
        if e[0] != "bolt" or e[1].kind != "knife":
            return False
        m = world.monster(e[1].target)
        return m is not None and m.door >= 0
    return stage({"replay": log}, at_gate, frame="pair", at=[2, 5, 8], view=(42.0, 17.0, 200.0))


def hymn() -> dict:
    """The Graveyard: Battle Hymn sung over an Arrow Tower while the first wave walks by it."""
    w = _world("graveyard")
    towers = lane_side(w, 2)
    log = ghost("graveyard", [[0.5, "build", "arrow", t] for t in towers]
                + [[1.0, "call_wave"], [14.0, "hymn", towers[0]]])
    return stage({"replay": log}, lambda w, e: e[0] == "hymn", frame="tower", at=[6, 30],
                 view=(48.0, 16.0, 200.0))


def shrine() -> dict:
    """Tristram, undefended: the first Fallen up the steps, its blow on the shrine's gate, the light that answers."""
    log = ghost("tristram", [[1.0, "call_wave"]])
    return stage({"replay": log}, lambda w, e: e[0] == "leak", frame="door", at=[20, 40, 47, 56],
                 view=(30.0, 16.0))


def returned() -> dict:
    """A boss at the shrine, cast back to its portal: a strong scripted player's defence of a boss's location, its
    towers sold the moment the boss walks alone."""
    def alone(world: World) -> bool:   # and the shrine can take its strike: the fight goes on after it
        living = [m for m in world.monsters if m.hp > 0]
        return len(living) == 1 and living[0].kind.key in BOSSES and world.lives > STRIKE
    for location in [key for key in ORDER if {g.kind for w in LOCATIONS[key].waves for g in w.groups} & set(BOSSES)]:
        for player in ("veteran", "adaptive", "planned"):
            log, time = recorded(location, player, alone)
            world = replayed(log, time)
            if not alone(world):
                continue
            log["commands"] += [[world.time, "sell", list(t.tile)] for t in world.towers.values()]
            try:
                return stage({"replay": log}, lambda w, e: e[0] == "returned" and w.outcome is None, frame="door",
                             at=[1, 8, 36, 50],
                             view=(30.0, 22.0))
            except LookupError:
                continue
    raise LookupError("no scripted player's defence brings a boss to the shrine")


def portal() -> dict:
    """The boss after its return: out of its portal again, its strike counted over its bar."""
    spec = returned()
    spec.update(frame="monster", at=[50, 80], view=(46.0, 26.0))
    return spec


def plate() -> dict:
    """The Catacombs with Ballistas: the mouse on an Overlord, its plate with its armor and the hits it takes."""
    w = _world("catacombs")
    log = ghost("catacombs", [[0.5, "build", "ballista", t] for t in lane_side(w, 2)]
                + [[0.6, "build", "arrow", t] for t in lane_side(w, 4)[2:]] + [[1.0, "call_wave"]])

    def overlord(world: World, e: tuple) -> bool:
        if e[0] != "spawn":
            return False
        m = world.monster(e[1])
        return m is not None and m.kind.key == "overlord"
    return stage({"replay": log}, overlord, frame="monster", at=[75], view=(42.0, 22.0), hud=True,
                 hover="overlord")


STAGES: dict[str, Callable[[], dict]] = {"ballista": ballista, "hook": hook, "knife": knife, "hymn": hymn,
                                         "shrine": shrine, "returned": returned, "portal": portal,
                                         "plate": plate}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("name", nargs="?", choices=sorted(STAGES))
    parser.add_argument("out", nargs="?", type=Path)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list or args.name is None:
        print("\n".join(f"{name:10} {fn.__doc__}" for name, fn in STAGES.items()))
        return 0
    spec = STAGES[args.name]()
    text = json.dumps(spec)
    if args.out is None:
        print(text)
    else:
        args.out.write_text(text)
        print(f"{args.name}: {spec['event']} at {spec['time']:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
