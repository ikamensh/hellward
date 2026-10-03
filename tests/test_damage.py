"""The damage pipeline (``content.felt_hit``): every hit is a whole number, at least 1, its factors capped, rounded
toward the factors, less armor; damage over time and holy damage are the exceptions. And the monsters' tags and armor
as the stage-1 spec fixes them."""

import math
import random
from dataclasses import replace

import pytest

from hellward.sim.campaign import CATACOMBS
from hellward.sim.content import FACTOR_CAP, MONSTERS, Element, Group, MonsterKind, Wave, felt_hit, felt_over_time
from hellward.sim.model import SIM_DT, World

ELEMENTS = tuple(Element)
PLAIN = MonsterKind("plain", "Plain", 10.0, 1.0, 1)


def kinds(rng: random.Random) -> MonsterKind:
    """Every real kind, and plain ones with an element tag or armor drawn at random."""
    if rng.random() < 0.5:
        return rng.choice(list(MONSTERS.values()))
    tag = (rng.choice(ELEMENTS[1:]),)
    side = rng.randrange(3)
    return replace(PLAIN, protected=tag if side == 1 else (), vulnerable=tag if side == 2 else (),
                   armor=rng.randrange(4))


def draws(count: int = 4000):
    rng = random.Random(7)
    for _ in range(count):
        kind = kinds(rng)
        yield (rng.uniform(0.2, 30.0), rng.choice(ELEMENTS), kind, rng.choice((1.0, rng.uniform(0.2, 3.5))))


def test_every_hit_is_a_whole_number_and_at_least_one():
    for hit, element, kind, factor in draws():
        felt = felt_hit(hit, element, kind, factor)
        assert isinstance(felt, int) and felt >= 1


def test_factors_beyond_the_cap_add_nothing():
    for hit, element, kind, _ in draws(1000):
        ceiling = FACTOR_CAP / kind.taken(element)
        assert felt_hit(hit, element, kind, ceiling) == felt_hit(hit, element, kind, ceiling * 3)
    assert felt_hit(10, Element.FIRE, PLAIN, 5.0) == 20


def test_a_hit_rounds_toward_its_factors_before_armor():
    """Up when the capped product is above 1, down when below, half up at exactly 1."""
    for hit, element, kind, factor in draws():
        bare = replace(kind, armor=0)
        product = min(FACTOR_CAP, factor * kind.taken(element))
        value = hit * product
        felt = felt_hit(hit, element, bare, factor)
        if product > 1.0:
            assert felt == max(1, math.ceil(value - 1e-9))
        elif product < 1.0:
            assert felt == max(1, math.floor(value + 1e-9))
        else:
            assert felt == max(1, math.floor(value + 0.5 + 1e-9))
        assert felt_hit(hit, element, kind, factor) == max(1, felt - kind.armor)


def test_a_tag_always_moves_a_whole_hit_by_at_least_one():
    protected = replace(PLAIN, protected=(Element.FIRE,))
    vulnerable = replace(PLAIN, vulnerable=(Element.FIRE,))
    assert (felt_hit(2, Element.FIRE, protected), felt_hit(2, Element.FIRE, PLAIN),
            felt_hit(2, Element.FIRE, vulnerable)) == (1, 2, 3)
    for hit in range(2, 31):
        assert felt_hit(hit, Element.FIRE, protected) <= hit - 1
        assert felt_hit(hit, Element.FIRE, vulnerable) >= hit + 1


def test_more_hit_or_more_factor_is_never_felt_less():
    for hit, element, kind, factor in draws(2000):
        felt = felt_hit(hit, element, kind, factor)
        assert felt_hit(hit + 1.0, element, kind, factor) >= felt
        assert felt_hit(hit, element, kind, factor * 1.3) >= felt


def test_physical_fears_armor_only():
    """No kind is tagged for physical: an Arrow and a Ballista lose only the armor."""
    for kind in MONSTERS.values():
        assert felt_hit(2, Element.PHYSICAL, kind) == max(1, 2 - kind.armor)
        assert felt_hit(7, Element.PHYSICAL, kind) == 7 - kind.armor
    assert felt_hit(2, Element.PHYSICAL, MONSTERS["overlord"]) == 1   # half an arrow
    assert felt_hit(7, Element.PHYSICAL, MONSTERS["overlord"]) == 5   # most of a bolt


def test_holy_damage_takes_no_factor_and_no_armor():
    for hit, _, kind, _ in draws(1000):
        assert felt_hit(hit, None, kind) == felt_hit(hit, None, PLAIN) == max(1, math.floor(hit + 0.5 + 1e-9))


def test_damage_over_time_takes_the_factors_but_no_armor_and_no_rounding():
    for hit, element, kind, factor in draws(1000):
        expected = hit * min(FACTOR_CAP, factor * kind.taken(element))
        assert felt_over_time(hit, element, kind, factor) == pytest.approx(expected)
        assert felt_over_time(hit, element, kind, factor) == felt_over_time(hit, element, replace(kind, armor=0), factor)


def test_venom_goes_through_armor_in_the_world():
    world = World(replace(CATACOMBS, waves=(Wave((Group("overlord", 1, 1.0),), 10),), wave_names=("test",)))
    world.call_wave()
    world.step()
    overlord = world.monsters[0]
    overlord.frozen = 10.0   # it stays put
    overlord.poison.append([0.5, 4.0])
    hp = overlord.hp
    world.step(SIM_DT)
    assert hp - overlord.hp == pytest.approx(0.5 * SIM_DT * overlord.kind.taken(Element.POISON))


def test_the_monsters_tags_and_armor_follow_the_spec():
    """At most two element tags (a boss may have more), physical never; armor on the heavy kinds and the bosses,
    and an armored kind keeps a vulnerability so an elemental tower has a way in. Nothing is immune."""
    armor = {key: kind.armor for key, kind in MONSTERS.items() if kind.armor}
    assert armor == {"overlord": 2, "zealot": 2, "hulk": 3, "abomination": 2, "azazel": 2,
                     "bone_priest": 3}
    assert {key for key, kind in MONSTERS.items() if kind.boss} == {"azazel", "bone_priest"}
    assert (MONSTERS["overlord"].vulnerable, MONSTERS["zealot"].vulnerable, MONSTERS["hulk"].vulnerable) == (
        (Element.LIGHTNING,), (Element.FIRE,), (Element.FIRE,))
    for kind in MONSTERS.values():
        tags = (*kind.protected, *kind.vulnerable)
        assert kind.boss or len(tags) <= 2, kind.key
        assert Element.PHYSICAL not in tags
        assert all(kind.taken(element) > 0 for element in ELEMENTS)
    with pytest.raises(ValueError):
        replace(PLAIN, protected=(Element.FIRE, Element.COLD, Element.POISON))
    with pytest.raises(ValueError):
        replace(PLAIN, protected=(Element.PHYSICAL,))
