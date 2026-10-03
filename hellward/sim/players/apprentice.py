"""The apprentice: a thoughtful human on a first play, and the balance tools' yardstick.

It plays like the ordinary defender (its towers, gates, upgrades and Battle Hymn, though it keeps a
Smite in hand while a leader walks), and it has started to learn the tree and two aimed spells: Smite on
a leader one Smite kills, else on a monster close to the sanctuary one Smite kills, and Meteor on a thick
crowd while keeping mana for Smite. Frozen Orb it never touches: it has not learned to time it.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim.campaign import ORDER, Location, idle
from hellward.sim.content import SPELLS, felt_hit
from hellward.sim.model import Monster, Refused, World
from hellward.sim.players.hands import Hands, ready
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.skills import SKILLS, can_learn

FIRST = ("unlock_pyre", "adept_fire", "warmth", "unlock_frost", "adept_cold", "unlock_storm",
         "adept_lightning", "holy_shield", "fire_ball", "unlock_plague", "adept_poison", "adept_arrow",
         "unlock_hymn", "glacial_spike", "chain_lightning", "contagion", "master_fire", "master_cold",
         "master_lightning", "master_poison", "master_arrow", "blaze", "shatter", "static_field",
         "lower_resist", "thorns", "spell_mastery", "unlock_altar", "adept_bone", "corpse_explosion",
         "master_bone", "life_tap", "unlock_grove", "adept_nature", "hurricane", "master_nature", "twister",
         "unlock_ballista", "adept_ballista", "master_ballista", "unlock_hook", "adept_hook", "master_hook",
         "unlock_knife", "adept_knife", "master_knife", "unlock_orb", "unlock_meteor")

METEOR_CROWD = 4     # others within METEOR_REACH of the aimed monster that make a Meteor worth it
METEOR_REACH = 1.4   # tiles around the aimed monster
METEOR_SPARE = 95.0  # a Meteor (60) only when a Smite (35) stays in hand
CLOSE = 3.0          # tiles from the sanctuary at which a monster one Smite kills is smitten


@dataclass
class Apprentice(Ordinary):
    name: str = "apprentice"

    def draft(self, location: Location, sigils: int) -> frozenset[str]:
        stage = ORDER.index(location.key)
        order = [*FIRST, *(key for key in SKILLS if key not in FIRST)]
        learned: set[str] = set()
        for key in order:
            if idle(location, SKILLS[key].needs):
                continue
            if can_learn(frozenset(learned), key, sigils, stage):
                learned.add(key)
        return frozenset(learned)

    def act(self, hands: Hands) -> None:
        clock = self.clock
        super().act(hands)
        if self.clock == clock:
            return   # the ordinary defender thought nothing this step, neither does the apprentice
        world = hands.world
        if ready(world, "smite"):
            target = self._smitten(world)
            if target is not None:
                try:
                    hands.smite(target.id)
                except Refused:
                    pass
                return
        if ("meteor" in world.arsenal.spells and world.mana >= METEOR_SPARE
                and world.mana >= world.spell_cost("meteor")):
            at = self._crowd(hands)
            if at is not None:
                try:
                    hands.meteor(*at)
                except Refused:
                    pass

    def _hymn(self, hands: Hands) -> None:
        world = hands.world
        keep = world.spell_cost("smite") if "smite" in world.arsenal.spells and world.leaders() else 0.0
        if world.mana - keep >= world.spell_cost("hymn"):
            super()._hymn(hands)

    def _smitten(self, world: World) -> Monster | None:
        """A leader one Smite kills (its curse dies with it), else a monster close to the sanctuary one Smite kills."""
        blow = SPELLS["smite"].damage * world.power()
        for m in world.leaders():
            if m.hp <= felt_hit(blow, None, m.kind):
                return m
        for m in world.monsters:   # nearest the sanctuary first
            if world.remaining(m) > CLOSE:
                break
            if m.hp <= felt_hit(blow, None, m.kind):
                return m
        return None

    def _crowd(self, hands: Hands) -> tuple[float, float] | None:
        """The first monster with at least four others within reach, aimed at its own spot."""
        world = hands.world
        spots = [world.position(m) for m in world.monsters]
        for i in range(len(spots)):
            near = 0
            for j in range(len(spots)):
                if i == j:
                    continue
                dx = spots[j][0] - spots[i][0]
                dy = spots[j][1] - spots[i][1]
                if dx * dx + dy * dy <= METEOR_REACH * METEOR_REACH:
                    near += 1
                    if near >= METEOR_CROWD:
                        break
            if near >= METEOR_CROWD:
                return spots[i]
        return None
