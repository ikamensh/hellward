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
from dataclasses import replace
from pathlib import Path

import pytest

from hellward.sim import fastsim, planner
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import Curse, Element, MONSTERS
from hellward.sim.items import Loadout
from hellward.sim.model import Bolt, DOOR_STOP, Hazard, Monster, World
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
from hellward.sim.campaign import CATHEDRAL, LOCATIONS
from hellward.sim.model import World
from hellward.sim.players.hands import Hands
from hellward.sim.players.ordinary import Ordinary

world = World(CATHEDRAL, seed=2, planner=planner.smart)   # a hundred seconds into a defence
player, hands = Ordinary(), Hands(world, react=0.6)
while world.time < 100.0:
    player.act(hands)
    world.step()
    hands.observe(world.events)
    world.events.clear()
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
    """A dense late defence with a forged loadout and an opened side entrance.

    The fixture starts at the authored breach wave and places a few threats beside a gate so
    clone and compiled parity exercise the active state without depending on a bot's build.
    """
    world = World(LOCATIONS["temple"], perks=perks(SKILLS), seed=5, hardness=4.0,
                  loadout=Loadout(("execution_bow", "blast_chamber", "forked_coil")))
    world.lives = 10_000
    world.gold = 10_000
    free = [(x, y) for y in range(world.level.height) for x in range(world.level.width)
            if world.level.buildable(x, y)]
    towers = [world.build(kind, tile) for kind, tile in zip(
        ("arrow", "pyre", "storm", "frost", "plague", "altar", "grove"), free)]
    world.build_door(0)
    spec = world.breach_spec
    assert spec is not None
    world.wave = spec.after_wave
    world.wave_alive[world.wave] = 0
    world.break_left = 10.0
    world.choose_breach("trophy")
    world.call_wave()
    for _ in range(20):
        world.step()
    assert world.schedule and world.breach_opened

    zombie = MONSTERS["zombie"]
    batterer = Monster(world._id(), zombie, world.wave, 0.0, 0.0, zombie.hp * 4, 0.0)
    batterer.s = world.doors[0].s - DOOR_STOP
    batterer.door = 0
    batterer.poison.append([1.0, 4.0])
    batterer.chill_left = 3.0
    batterer.frozen = 0.5
    world.monsters.append(batterer)
    priest = MONSTERS["priest"]
    leader = Monster(world._id(), priest, world.wave, 0.0, 0.0, priest.hp * 4, priest.leader.first_cast)
    leader.s = batterer.s + 1
    world.monsters.append(leader)
    world.wave_alive[world.wave] += 2
    world.doors[0].hp -= 1.0
    world.bolts.append(Bolt(world._id(), towers[0].id, "arrow", leader.id, 0.4,
                            towers[0].stats.damage, Element.PHYSICAL, 0.0, 0.0, 0.0,
                            towers[0].centre, world.position(leader), leader_bonus=towers[0].stats.leader_bonus))
    lx, ly = world.position(leader)
    world.hazards.append(Hazard(lx, ly, 1.0, 1.0, 3.0))
    world.mana = world.mana_max
    world.meteor(lx, ly)
    world.mana = world.mana_max
    world.orb(lx, ly)
    world.mana = world.mana_max
    world.smite(leader.id)
    batterer.door = 0
    towers[0].curses[Curse.DECREPIFY] = 5.0
    towers[1].curses[Curse.BONE_PRISON] = 3.0
    towers[2].ward = 4.0
    leader.chant_curse, leader.chant_spot, leader.chant_left = Curse.WEAKEN, towers[3].tile, 0.8
    towers[-1].timer = 3.5
    for m in world.monsters[:3]:
        m.amplified, m.amplify = 2.0, 0.3
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
    assert world.meteors and world.hazards and world.bolts and world.schedule and world.breach_opened
    assert any(m.frozen > 0 for m in world.monsters) and any(m.door >= 0 for m in world.monsters)
    assert any(d.built and d.hp < world.gate_life for d in world.doors)
    world.record = False
    twin = world.clone()
    for step in range(300):
        world.step()
        twin.step()
        assert sim_bench.state(twin) == sim_bench.state(world), f"parted at step {step + 1}"


def busy_act2_world() -> World:
    """Temple (Act II) with Act II monsters: a risen Flayer, a marking Inquisitor, a Bone Priest burning mana."""
    world = busy_world()
    towers = sorted(world.towers.values(), key=lambda t: t.id)
    # Add Act II specific state: a risen flayer and a marking inquisitor
    flayer = MONSTERS["flayer"]
    flayer_hp = flayer.hp * world.waves[world.wave].hp * world.location.life
    risen_flayer = Monster(world._id(), flayer, world.wave, 0.0, 0.0, flayer_hp * 0.5, 0.0)
    risen_flayer.s = 15.0
    risen_flayer.risen = True
    risen_flayer.frozen = 0.5
    world.monsters.append(risen_flayer)
    world.wave_alive[world.wave] += 1

    inquisitor = MONSTERS["inquisitor"]
    inq_hp = inquisitor.hp * world.waves[world.wave].hp * world.location.life
    marking_inq = Monster(world._id(), inquisitor, world.wave, 0.0, 0.0, inq_hp, inquisitor.leader.first_cast)
    marking_inq.s = 20.0
    marking_inq.chant_curse = Curse.WEAKEN
    marking_inq.chant_spot = towers[0].tile
    marking_inq.chant_left = 0.8
    marking_inq.marking = True
    world.monsters.append(marking_inq)
    world.wave_alive[world.wave] += 1

    return world


def test_act2_clone_fidelity() -> None:
    """Clone fidelity for an Act II busy world with risen and marking monsters."""
    world = busy_act2_world()
    assert any(m.risen for m in world.monsters)
    assert any(m.marking for m in world.monsters)
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


SPAWN_ROUND_TRIP = """
import json, multiprocessing, sys
sys.path.insert(0, {root!r})
from concurrent.futures import ProcessPoolExecutor


def _init() -> None:
    from hellward.sim import fastsim
    fastsim.activate()   # the parent's build, through HELLWARD_FASTSIM


def _decide(world, leader_id):
    from hellward.sim import fastsim, planner
    return planner.decide(world, leader_id), fastsim.compiled()


def main() -> None:
    from hellward.sim import fastsim
    fastsim.attach({build!r})   # the compiled parent, before the simulation is imported
    from hellward.sim import planner
    from hellward.sim.campaign import CATHEDRAL
    from hellward.sim.model import World
    from hellward.sim.players.hands import Hands
    from hellward.sim.players.ordinary import Ordinary
    world = World(CATHEDRAL, seed=2, planner=planner.smart)   # a hundred seconds into a defence
    player, hands = Ordinary(), Hands(world, react=0.6)
    while world.time < 100.0 or not world.leaders():
        assert world.outcome is None
        player.act(hands)
        world.step()
        hands.observe(world.events)
        world.events.clear()
    probe = world.clone()   # what the game sends its workers
    leader = probe.leaders()[0].id
    inline = planner.decide(probe, leader)
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(1, mp_context=ctx, initializer=_init) as pool:
        back, worker_compiled = pool.submit(_decide, probe, leader).result(timeout=600)
    print(json.dumps({{"parent": fastsim.compiled(), "worker": worker_compiled, "same": back == inline}}))


if __name__ == "__main__":
    main()
"""


def test_a_spawned_worker_decides_as_its_compiled_parent(tmp_path: Path) -> None:
    """A world the compiled simulation built round-trips to a fresh spawn worker on the same build: pickled by
    the compiled parent, unpickled by the compiled worker (which activated the parent's build through
    ``HELLWARD_FASTSIM``), the planner decides there exactly what it decides inline."""
    try:
        build = fastsim.build()
    except fastsim.NoToolchain as missing:
        pytest.skip(f"this machine cannot compile the simulation: {missing}")
    env = {k: v for k, v in os.environ.items() if k not in (fastsim.ENV, fastsim.OPT_OUT)}
    driver = tmp_path / "spawn_decide.py"
    driver.write_text(SPAWN_ROUND_TRIP.format(root=str(ROOT), build=str(build)), encoding="utf-8")
    done = subprocess.run([sys.executable, str(driver)], cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=900)
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert report["parent"] and report["worker"]
    assert report["same"]
