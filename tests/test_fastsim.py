"""The compiled simulation is the simulation: a defence it plays is the source's, event for event and to the bit,
and a clone steps as the world it was copied from.

The compiled half builds the simulation with mypyc once per change to its sources (about fifteen seconds) and
plays in a process of its own; a machine without mypyc or a C compiler skips it and says which is missing."""

from __future__ import annotations

import ast
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

from hellward.sim import fastsim, planner
from hellward.sim.campaign import HELL, LOCATIONS
from hellward.sim.content import Curse
from hellward.sim.model import World
from hellward.sim.players.hands import Hands
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.skills import SKILLS, perks
from hellward.sim.sums import float_sum

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import sim_bench  # noqa: E402

COMPILED = """
import json, pickle, sys
sys.path[:0] = [{root!r}, {tools!r}, {tests!r}]
from hellward.sim import fastsim
fastsim.attach({build!r})
import sim_bench
from test_fastsim import full_fight
from hellward.sim import planner
from hellward.sim.campaign import CATHEDRAL, LOCATIONS, NORMAL
from hellward.sim.players.hands import defend
from hellward.sim.players.ordinary import Ordinary

world, _ = defend(CATHEDRAL, NORMAL, Ordinary(), seed=2, sigils=0, planner=planner.smart, limit=100.0)
kept = world.clone()
back = pickle.loads(pickle.dumps(kept))   # what tools/curse_quality.py sends its workers
same = [sim_bench.state(back) == sim_bench.state(kept)]
for _ in range(200):
    kept.step()
    back.step()
same.append(sim_bench.state(back) == sim_bench.state(kept))
print(json.dumps({{"compiled": fastsim.compiled(), "pickled": same, "full_fight": full_fight(),
                  "digests": {{key: sim_bench.defence(key)[1] for key in LOCATIONS}}}}))
"""


@pytest.fixture(scope="module")
def compiled() -> dict:
    """What the compiled simulation made of every location's defence, and of a pickled world."""
    try:
        build = fastsim.build()
    except fastsim.NoToolchain as missing:
        pytest.skip(f"this machine cannot compile the simulation: {missing}")
    env = {k: v for k, v in os.environ.items() if k not in (fastsim.ENV, fastsim.OPT_OUT)}
    script = COMPILED.format(root=str(ROOT), tools=str(ROOT / "tools"), tests=str(ROOT / "tests"), build=str(build))
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.mark.parametrize("key", list(LOCATIONS))
def test_a_compiled_defence_is_the_source_defence(key: str, compiled: dict) -> None:
    """The ordinary player against smart leaders: every event with its time, and the world at the end."""
    assert compiled["compiled"]
    _, digest = sim_bench.defence(key)
    assert compiled["digests"][key] == digest


def test_a_compiled_fight_with_every_skill_and_spell_is_the_sources(compiled: dict) -> None:
    """The ordinary player learns no skill and casts nothing but Cleanse: this fight has them all."""
    assert compiled["full_fight"] == full_fight()


def test_a_compiled_world_survives_pickling(compiled: dict) -> None:
    """A compiled frozen dataclass refuses its fields one by one, so fastsim pickles it by its constructor."""
    assert compiled["pickled"] == [True, True]


def busy_world() -> World:
    """Hell's Gate on Hell with the whole skill tree, at a moment when its fight is full: towers of every kind,
    gates under blows, venom and frost on the monsters, bolts in flight and burning floor, two waves on the map and
    one still coming. Then a meteor is cast (in the air), a frozen orb (monsters frozen) and a smite, and a warded
    tower, two cursed ones and a leader chanting are set by hand. Like a clone, it has no planner and no leader
    waiting for one."""
    world = World(LOCATIONS["hells_gate"], difficulty=HELL, perks=perks(SKILLS), seed=5, planner=planner.smart)
    player, hands = Ordinary(), Hands(world, react=0.6)

    def full() -> bool:
        m = world.monsters
        return (world.wave >= 2 and bool(world.leaders()) and bool(world.bolts) and bool(world.hazards)
                and any(x.door >= 0 for x in m) and any(x.poison for x in m) and any(x.chill_left > 0 for x in m))

    while not full():
        assert world.outcome is None
        player.act(hands)
        world.step()
        hands.observe(world.events)
        world.events.clear()
    world.call_wave()
    world.planner = None
    for m in world.monsters:
        m.asking, m.ask_left = None, 0.0
    world.mana = world.mana_max
    world.meteor(*world.position(world.monsters[0]))
    world.mana = world.mana_max
    world.orb(*world.position(next(m for m in reversed(world.monsters) if m.door < 0)))
    world.mana = world.mana_max
    world.smite(world.monsters[1].id)
    towers = sorted(world.towers.values(), key=lambda t: t.id)
    towers[0].curses[Curse.DECREPIFY] = 5.0
    towers[1].curses[Curse.BONE_PRISON] = 3.0
    towers[2].ward = 4.0
    leader = world.leaders()[0]
    leader.chant_curse, leader.chant_tower, leader.chant_left = Curse.WEAKEN, towers[3].id, 0.8
    return world


def full_fight() -> str:
    """The busy world played on for 300 steps with every skill, written out with every event on the way."""
    world = busy_world()
    for _ in range(300):
        world.step()
    return sim_bench.digest(world, [(0.0, world.events)])


def test_a_clone_steps_as_its_world() -> None:
    """Everything a world carries, a clone carries: stepped side by side, the two stay the same world. A field that
    ``clone()`` or a ``copy()`` forgets shows here, since the state is read from every attribute there is."""
    world = busy_world()
    assert world.meteors and world.hazards and world.bolts and world.schedule and len(world.unpaid) == 2
    assert any(m.frozen > 0 for m in world.monsters) and any(m.door >= 0 for m in world.monsters)
    assert any(d.built and d.hp < world.gate_life for d in world.doors)
    world.record = False
    twin = world.clone()
    for step in range(300):
        world.step()
        twin.step()
        assert sim_bench.state(twin) == sim_bench.state(world), f"parted at step {step + 1}"


def test_float_sum_adds_as_the_builtin_sum_does() -> None:
    """Property: to the bit, on sums that cancel, that carry, and that are ordinary."""
    rng = random.Random(9)
    for _ in range(20_000):
        values = [rng.choice((rng.uniform(-1, 1), rng.uniform(0, 500), rng.uniform(-1e16, 1e16), 1e-300, -0.0))
                  for _ in range(rng.randrange(0, 12))]
        assert float_sum(values).hex() == float(sum(values)).hex()
    assert float_sum([1e16, 1.0, -1e16]) == sum([1e16, 1.0, -1e16]) == 1.0
    assert math.isinf(float_sum([1e308, 1e308, -1e308])) and math.isinf(sum([1e308, 1e308, -1e308]))


@pytest.mark.parametrize("module", fastsim.MODULES)
def test_a_compiled_module_calls_no_builtin_sum(module: str) -> None:
    path = fastsim.PACKAGE / fastsim.source(module)
    calls = [node.lineno for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sum"]
    assert not calls, f"hellward/{fastsim.source(module)}, lines {calls}: use sums.float_sum or sums.int_sum"


def test_a_build_of_other_sources_is_refused(tmp_path: Path) -> None:
    (tmp_path / "0123456789abcdef0123").mkdir()
    with pytest.raises(ImportError, match="other sources"):
        fastsim.attach(tmp_path / "0123456789abcdef0123")


def test_a_new_build_prunes_what_no_process_has_started_on_for_days(tmp_path: Path, monkeypatch) -> None:
    """Old builds, the staging of an interrupted one and what an earlier prune left half removed go; a recent build,
    the one just made and the one this process runs stay."""
    monkeypatch.setattr(fastsim, "BUILDS", tmp_path)
    day = 24 * 3600

    def made(name: str, days: float) -> Path:
        (tmp_path / name / "hellward" / "sim").mkdir(parents=True)
        os.utime(tmp_path / name, (time.time() - days * day,) * 2)
        return tmp_path / name

    old, interrupted, half_pruned = made("a" * 20, 4), made("b" * 20 + "-x1y2z3", 5), made("c" * 20 + ".pruned", 9)
    recent, running, new = made("d" * 20, 2.5), made("e" * 20, 30), made("f" * 20, 30)
    monkeypatch.setenv(fastsim.ENV, str(running))
    fastsim.prune(keep=new)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(p.name for p in (recent, running, new))
    assert not any(p.exists() for p in (old, interrupted, half_pruned))
