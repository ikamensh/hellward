"""Real-time reflexes for the LLM player: named auto behaviors that cast spells in the fight.

The LLM cannot watch every step, so it arms reflexes (`auto smite_leader on`) and they
act through :class:`~hellward.sim.players.hands.Hands` like a person's hands: leaders
only by their delayed signs, aimed spells at most one per aim gap, mana and recharge
as the panel shows. Nothing here reads a leader's planner or clones the world.
"""

from __future__ import annotations

from collections.abc import Callable

from hellward.sim.content import SPELLS, Element, felt_hit
from hellward.sim.model import Monster, Refused, World
from hellward.sim.players.hands import Hands, ready
from hellward.sim.sums import float_sum

RULES = ("smite_leader", "smite_leak", "hymn", "meteor", "orb")

LEAK_SECONDS = 2.5   # a foe this close to the shrine, one Smite kills, is smitten
HYMN_LOAD = 3.0      # foes in or near a tower's reach that earn it the hymn
HYMN_NEAR = 3.0      # tiles past a tower's reach whose foes count as its work to come
METEOR_BITE = 3.0    # a Meteor must be worth this many of its blows in queued life
METEOR_PACK = 3      # ... and catch at least this many foes
ORB_GATE_SHARE = 0.5  # a gate below this share of life, mobbed, earns the orb


def smite_damage(world: World, m: Monster) -> int:
    return felt_hit(SPELLS["smite"].damage * world.power(), None, m.kind)


def meteor_damage(world: World) -> float:
    return SPELLS["meteor"].damage * world.power()


class Autos:
    """The armed reflexes; :meth:`act` runs them before a step, in a fixed order.

    ``log`` is the battle's command log: every cast joins it in the form
    :class:`~hellward.sim.players.ghost.Ghost` replays, so a logged defence —
    autos and all — fights the identical battle again.
    """

    def __init__(self, hands: Hands, enabled: set[str] | None = None,
                 log: list[list] | None = None) -> None:
        self.hands = hands
        self.enabled: set[str] = set(enabled) if enabled else set()
        self.log = log
        self.cast: list[str] = []   # spells cast since last taken, for the digest

    def act(self) -> None:
        world = self.hands.world
        if world.outcome is not None:
            return
        if "smite_leader" in self.enabled:
            self._smite_leader(world)
        if "smite_leak" in self.enabled:
            self._smite_leak(world)
        if "hymn" in self.enabled:
            self._hymn(world)
        if "meteor" in self.enabled:
            self._meteor(world)
        if "orb" in self.enabled:
            self._orb(world)

    def take(self) -> list[str]:
        cast, self.cast = self.cast, []
        return cast

    def _smite_leader(self, world: World) -> None:
        if not ready(world, "smite"):
            return
        for sign in self.hands.threats():
            if sign.kind not in ("chant", "mark"):
                continue
            m = world.monster(sign.leader)
            if m is not None and m.hp > 0 and m.hp <= smite_damage(world, m):
                x, y = world.position(m)
                self._cast("smite", lambda: self.hands.smite(m.id), [x, y])
                return

    def _smite_leak(self, world: World) -> None:
        if not ready(world, "smite"):
            return
        foes = sorted(world.monsters, key=lambda m: world.remaining(m))
        for m in foes:
            pace = m.kind.speed * m.speed_factor
            seconds = world.remaining(m) / pace if pace > 0 else float("inf")
            if seconds <= LEAK_SECONDS and 0 < m.hp <= smite_damage(world, m):
                x, y = world.position(m)
                self._cast("smite", lambda: self.hands.smite(m.id), [x, y])
                return

    def _hymn(self, world: World) -> None:
        spare = world.spell_cost("smite") if "smite" in world.arsenal.spells else 0.0
        if not ready(world, "hymn", spare=spare):
            return
        best, load = None, HYMN_LOAD
        for tower in world.towers.values():
            if tower.hymn > 0 or tower.curses:
                continue
            cx, cy = tower.centre
            work = 0
            for m in world.monsters:
                x, y = world.position(m)
                if (x - cx) ** 2 + (y - cy) ** 2 <= (tower.reach + HYMN_NEAR) ** 2:
                    work += 1
            if work > load:
                best, load = tower, work
        if best is not None:
            self._cast("hymn", lambda: self.hands.hymn(best.id), [list(best.tile)])

    def _meteor(self, world: World) -> None:
        if not ready(world, "meteor"):
            return
        spec = SPELLS["meteor"]
        bite = METEOR_BITE * meteor_damage(world)
        best: tuple[float, float] | None = None
        for m in world.monsters:
            x, y = world.position(m)
            pack = [o for o in world.monsters if _dist2(world.position(o), (x, y)) <= spec.radius ** 2]
            if len(pack) < METEOR_PACK:
                continue
            felt = float_sum(felt_hit(meteor_damage(world), Element.FIRE, o.kind) for o in pack)
            if felt >= bite:
                best = (x, y)
                break
        if best is not None:
            self._cast("meteor", lambda: self.hands.meteor(best[0], best[1]), [best[0], best[1]])

    def _orb(self, world: World) -> None:
        if not ready(world, "orb"):
            return
        for door in world.doors:
            if not door.built or door.hp >= world.gate_life * ORB_GATE_SHARE:
                continue
            mob = [m for m in world.monsters if m.door == door.index]
            if len(mob) >= 2:
                x, y = door.tile[0] + 0.5, door.tile[1] + 0.5
                self._cast("orb", lambda: self.hands.orb(x, y), [x, y])
                return

    def _cast(self, order: str, call: Callable[[], None], logged: list) -> None:
        try:
            call()
        except Refused:  # the aim gap, the mana: a reflex shrugs and tries next step
            return
        self.cast.append(order)
        if self.log is not None:
            self.log.append([self.hands.world.time, order, *logged])


def _dist2(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
