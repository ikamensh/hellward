"""The tree: branches read verbs, engines seed into plans, unfunded engines unswap."""

from collections import Counter

from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.players import tree
from hellward.sim.players.planned import Planned, adjust_plan, check
from hellward.sim.players.warden import Plan as WardenPlan
from hellward.sim.players.warden import Step, adjust_plan as warden_adjust
from hellward.sim.players.warden import draft_build, draft_skills
from hellward.sim.skills import unlock_skills

TEMPLE = LOCATIONS["temple"]
SIGILS = 3 * ORDER.index("temple")


def builds(steps):
    return Counter(s[1] for s in steps if s[0] == "build")


def test_branches_want_their_verbs_engines_and_unknown_keys_are_skipped():
    reading = tree.read(("war_tithe", "volatile", "not_a_relic"))
    assert ("idol", 2) in reading.engines and ("well", 1) in reading.engines
    assert reading.skills[:2] == ("unlock_idol", "unlock_well")   # unlocks before adepts
    assert tree.read(()) == tree.Reading()
    assert tree.read(("canticle", "hoard", "journeyman")).engines == ()


def test_charters_raise_with_no_skill():
    reading = tree.read(("hook_charter",))
    assert ("hook", 1) in reading.engines and ("knife", 1) in reading.engines
    assert ("well", 1) in reading.engines   # it reads charge too
    assert "unlock_hook" not in reading.skills and "unlock_knife" not in reading.skills
    assert tree.chartered(("hook_charter", "grove_charter")) == {"hook", "knife", "grove"}
    assert "effigy" not in tree.chartered(("grove_charter",))   # it would eat the charter's curse gold


def test_a_cast_draw_seeds_idols_into_the_temple_plan_and_keeps_their_tiles():
    plan = check(TEMPLE)
    before = {s[2]: s[1] for s in plan.steps if s[0] == "build"}
    read = adjust_plan(plan, ("war_tithe",), TEMPLE, SIGILS, ORDER.index("temple"))
    kinds = builds(read.steps)
    assert kinds["idol"] == 2
    after = {s[2]: s[1] for s in read.steps if s[0] == "build"}
    assert set(after) == set(before)   # tiles kept, only kinds change
    assert sum(1 for tile in before if after[tile] != before[tile]) == 2
    learned = read.learn(SIGILS, ORDER.index("temple"))
    assert "unlock_idol" in learned
    assert tree.missing_unlocks([(s[1], s[2]) for s in read.steps if s[0] == "build"],
                                learned, ("war_tithe",)) == frozenset()


def test_the_sigils_drop_tail_bonuses_to_pay_for_the_engines_unlocks():
    plan = check(TEMPLE)
    base = plan.learn(SIGILS, ORDER.index("temple"))
    read = adjust_plan(plan, ("war_tithe",), TEMPLE, SIGILS, ORDER.index("temple"))
    learned = read.learn(SIGILS, ORDER.index("temple"))
    assert "unlock_idol" in learned and "unlock_idol" not in base
    assert base - learned   # some bonus paid for it


def test_an_engine_the_sigils_cannot_fund_is_unswapped_again():
    plan = check(TEMPLE)
    read = adjust_plan(plan, ("war_tithe", "volatile", "last_breath"), TEMPLE, SIGILS,
                       ORDER.index("temple"))
    learned = read.learn(SIGILS, ORDER.index("temple"))
    assert tree.missing_unlocks([(s[1], s[2]) for s in read.steps if s[0] == "build"],
                                learned, ("war_tithe", "volatile", "last_breath")) == frozenset()
    kinds = builds(read.steps)
    assert kinds["idol"] == 2   # the first branch fits
    assert "well" not in kinds or "unlock_well" in learned   # the rest fit or revert


def test_curse_readers_trade_an_effigy_for_the_cores_damage():
    builds_in = [("pyre", (1, 1)), ("pyre", (2, 2)), ("effigy", (3, 3))]
    seeded, swaps = tree.swap_kinds(builds_in, (), curse=True)
    assert ("effigy", (3, 3)) not in seeded and ("pyre", (3, 3)) in seeded
    assert swaps == [((3, 3), "effigy", "pyre")]


def test_engines_the_stage_cannot_unlock_are_skipped():
    tristram = LOCATIONS["tristram"]
    skills, seeded, swaps = tree.adjust(["unlock_pyre"], [("pyre", (1, 1)), ("pyre", (2, 2))],
                                        ("war_tithe",), tristram)
    assert seeded == [("pyre", (1, 1)), ("pyre", (2, 2))] and swaps == [] and skills == ["unlock_pyre"]


def test_with_no_relics_every_plan_stands_exactly_as_searched():
    plan = check(TEMPLE)
    assert adjust_plan(plan, (), TEMPLE, SIGILS, ORDER.index("temple")) is plan
    assert Planned().draft(TEMPLE, SIGILS) == Planned().draft(TEMPLE, SIGILS, ())
    learned = draft_skills(TEMPLE, SIGILS)
    assert draft_build(TEMPLE, learned) == draft_build(TEMPLE, learned, relics=())


def test_a_veteran_draft_seeds_engines_and_opens_charters():
    learned = draft_skills(TEMPLE, SIGILS, relics=("war_tithe", "hook_charter"))
    assert "unlock_idol" in learned
    steps = draft_build(TEMPLE, learned, relics=("war_tithe", "hook_charter"))
    kinds = Counter(s.kind for s in steps if s.what == "build")
    assert kinds["idol"] >= 2 and kinds["hook"] >= 1 and kinds["knife"] >= 1   # floors; shares may add
    tight = draft_build(TEMPLE, learned, relics=("spite",))
    plain = draft_build(TEMPLE, learned)
    assert [s.tile for s in tight if s.what == "build"] != [s.tile for s in plain if s.what == "build"]


def test_a_warden_stored_plan_reads_its_relics():
    plan = WardenPlan(frozenset({"unlock_pyre"}),
                      tuple([Step("build", "pyre", (1, 1)), Step("build", "pyre", (2, 2)),
                             Step("build", "pyre", (3, 3)), Step("build", "arrow", (4, 4)),
                             Step("build", "arrow", (5, 5))]))
    read = warden_adjust(plan, ("war_tithe",), TEMPLE, SIGILS, ORDER.index("temple"))
    kinds = Counter(s.kind for s in read.steps if s.what == "build")
    assert kinds["idol"] == 2 and kinds["arrow"] == 1
    assert "unlock_idol" in read.skills
    first = [s.kind for s in read.steps if s.what == "build"][:2]
    assert first == ["pyre", "pyre"]   # the opening holds while the engines come online behind it
