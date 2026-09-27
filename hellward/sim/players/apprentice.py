"""The apprentice: a thoughtful human on a first play, and the balance tools' yardstick.

It plays exactly like the ordinary defender (its towers, gates, upgrades and Cleanse), and it has
started to learn the tree and two aimed spells: Smite at the leaders' signs, and Meteor on a thick
crowd while keeping mana for Smite. Frozen Orb it never touches: it has not learned to time it.
"""

from __future__ import annotations

from dataclasses import dataclass

from hellward.sim.campaign import Location, idle
from hellward.sim.model import Refused
from hellward.sim.players.hands import Hands
from hellward.sim.players.ordinary import Ordinary
from hellward.sim.skills import SKILLS, can_learn

FIRST = ("adept_fire", "warmth", "adept_cold", "adept_lightning", "holy_shield", "fire_ball",
         "adept_poison", "salvation", "glacial_spike", "chain_lightning", "soul_harvest",
         "contagion", "master_fire", "master_cold", "master_lightning", "master_poison",
         "blaze", "shatter", "static_field", "lower_resist", "thorns", "spell_mastery",
         "adept_bone", "corpse_explosion", "master_bone", "life_tap",
         "adept_nature", "hurricane", "master_nature", "twister")

METEOR_CROWD = 4     # others within METEOR_REACH of the aimed monster that make a Meteor worth it
METEOR_REACH = 1.4   # tiles around the aimed monster
METEOR_SPARE = 95.0  # a Meteor (60) only when a Smite (35) stays in hand


@dataclass
class Apprentice(Ordinary):
    name: str = "apprentice"

    def skills(self, location: Location, sigils: int) -> frozenset[str]:
        order = [*FIRST, *(key for key in SKILLS if key not in FIRST)]
        learned: set[str] = set()
        for key in order:
            if idle(location, SKILLS[key].needs):
                continue
            if can_learn(frozenset(learned), key, sigils):
                learned.add(key)
        return frozenset(learned)

    def act(self, hands: Hands) -> None:
        clock = self.clock
        super().act(hands)
        if self.clock == clock:
            return   # the ordinary defender thought nothing this step, neither does the apprentice
        world = hands.world
        if "smite" in world.location.arsenal.spells and world.mana >= world.spell_cost("smite"):
            if hands.threats():
                try:
                    hands.smite_threat()
                except Refused:
                    pass
                return
        if ("meteor" in world.location.arsenal.spells and world.mana >= METEOR_SPARE
                and world.mana >= world.spell_cost("meteor")):
            at = self._crowd(hands)
            if at is not None:
                try:
                    hands.meteor(*at)
                except Refused:
                    pass

    def _crowd(self, hands: Hands) -> tuple[float, float] | None:
        """The first monster with at least four others within reach, aimed at its own spot."""
        world = hands.world
        spots = [world.level.point(m.s) for m in world.monsters]
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
