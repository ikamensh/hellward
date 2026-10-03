"""The run: one pool and one purse across all twelve locations, XP and levels, goals drawn by seed."""

from __future__ import annotations

from dataclasses import replace

import math

import pytest

from hellward.run import (
    BONUS_EARLY,
    CAMP_HEAL,
    DISMANTLE_REFUND,
    FAILED,
    LIFE,
    MET,
    OPEN,
    BonusPack,
    DefenceResult,
    Drawn,
    add_xp,
    bonus_pack,
    bonus_preview,
    camp,
    clear_xp,
    describe,
    dismantle,
    draw_goals,
    finish,
    from_json,
    gold_floor,
    kill_xp,
    kit,
    learn,
    lives_sigils,
    observe_world,
    start,
    to_json,
    unlearn,
    xp_next,
)
from hellward.run.goals import make
from hellward.sim.balance import BALANCE
from hellward.sim.bonus import PROFIT
from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.content import MONSTERS


def test_a_run_starts_full_pooled_and_aimed_at_tristram():
    run = start(7)
    assert (run.index, run.pool, run.gold, run.level) == (0, 30, 0, 1)
    assert run.location.key == "tristram"
    assert [goal.key for goal in run.drawn].__len__() == 3


def test_every_location_draws_three_distinct_goals_it_qualifies_for():
    for index, key in enumerate(ORDER):
        location = LOCATIONS[key]
        drawn = draw_goals(11, index, location)
        assert len({goal.key for goal in drawn}) == 3
        for goal in drawn:
            if goal.key == "gate":
                assert location.arsenal.gates
            if goal.key == "hymn":
                assert "hymn" in location.arsenal.spells
            if goal.key == "leaders":
                assert any(MONSTERS[group.kind].leader is not None
                           for wave in location.waves for group in wave.groups)
                assert goal.arg == ""   # every leader: the draw names no kind


def test_the_draw_is_by_seed_and_differs_between_runs():
    tristram = LOCATIONS["tristram"]
    assert draw_goals(7, 0, tristram) == draw_goals(7, 0, tristram)
    assert {draw_goals(seed, 0, tristram) for seed in range(20)}.__len__() > 1


def test_the_leaders_draw_names_no_kind():
    jungle = LOCATIONS["jungle"]
    args = {goal.arg for seed in range(60) for goal in draw_goals(seed, ORDER.index("jungle"), jungle)
            if goal.key == "leaders"}
    assert args == {""}   # every leader: the fold watches them all


def test_a_kit_tops_carried_gold_up_to_the_floor_and_carries_the_pool():
    run = start(3)
    assert kit(run).gold == gold_floor(LOCATIONS["tristram"]) == round(LOCATIONS["tristram"].start_gold * 0.8)
    assert kit(run).lives == run.pool == 30
    rich = camp(start(3))
    assert kit(replace(rich, gold=999)).gold == 999


def test_no_two_defences_of_a_run_roll_alike():
    run = start(5)
    assert kit(run).seed != kit(replace(run, index=1)).seed


def test_a_camp_returns_the_tunings_share_of_the_missing_life_rounded_up():
    assert camp(replace(start(1), pool=20)).pool == 20 + math.ceil(10 * CAMP_HEAL)
    assert camp(replace(start(1), pool=29)).pool == 29 + math.ceil(1 * CAMP_HEAL)
    assert camp(start(1)).pool == 30
    assert camp(replace(start(1), pool=99)).pool == 99   # past full is left alone, never taxed


def test_the_camp_before_an_acts_end_fills_the_pool():
    hells = ORDER.index("hells_gate")
    assert camp(replace(start(1), index=hells, pool=9)).pool == LIFE
    assert camp(replace(start(1), index=hells, pool=29)).pool == LIFE
    temple = ORDER.index("temple")
    assert camp(replace(start(1), index=temple, pool=9)).pool == LIFE
    caves = ORDER.index("caves")
    assert camp(replace(start(1), index=caves, pool=9)).pool == 9 + math.ceil(21 * CAMP_HEAL)


def test_the_first_level_up_comes_in_tristrams_second_wave():
    first = sum(group.count * kill_xp(MONSTERS[group.kind].hp)
                  for group in LOCATIONS["tristram"].waves[0].groups)
    first += clear_xp(1)
    second_kills = sum(group.count * kill_xp(MONSTERS[group.kind].hp)
                       for group in LOCATIONS["tristram"].waves[1].groups)
    assert first < xp_next(1) <= first + second_kills


def test_the_campaigns_xp_reaches_about_fifty_five_levels():
    total = 0.0
    for key in ORDER:
        for number, wave in enumerate(LOCATIONS[key].waves, start=1):
            total += (sum(group.count * kill_xp(MONSTERS[group.kind].hp) for group in wave.groups)
                        + clear_xp(number))
    run, gained = add_xp(start(0), total)
    assert 54 <= run.level <= 58
    assert gained == run.level - 1


def test_levels_pay_points_and_every_fourth_a_reskill():
    run, gained = add_xp(start(0), xp_next(1) + xp_next(2) + xp_next(3))
    assert (run.level, gained) == (4, 3)
    assert (run.skill_points, run.reskill_points) == (3, 1)


def test_lives_sigils_count_the_lives_lost():
    assert [lives_sigils(lost) for lost in (0, 1, 2, 3, 5, 6)] == [3, 2, 2, 1, 1, 0]


def test_learning_needs_its_points_its_above_and_its_place():
    run = replace(start(0), index=2, skill_points=12)
    run = learn(run, "unlock_pyre")
    assert run.skill_points == 9
    with pytest.raises(ValueError, match="needs Fire Ball"):
        learn(run, "blaze")
    with pytest.raises(ValueError, match="already learned"):
        learn(run, "unlock_pyre")
    with pytest.raises(ValueError, match="opens later"):
        learn(learn(learn(run, "adept_fire"), "master_fire"), "fire_ball")
    with pytest.raises(ValueError, match="costs 3 points"):
        learn(replace(start(0), index=2), "unlock_pyre")


def test_unlearning_takes_a_reskill_and_refunds_the_bottom_skill():
    run = replace(start(0), index=2, skill_points=12, reskill_points=1)
    run = learn(learn(learn(run, "unlock_pyre"), "adept_fire"), "master_fire")
    run = unlearn(run, "fire")
    assert run.learned == frozenset({"unlock_pyre", "adept_fire"})
    assert (run.skill_points, run.reskill_points) == (7, 0)
    with pytest.raises(ValueError, match="nothing in warding"):
        unlearn(run, "warding")
    with pytest.raises(ValueError, match="no reskill point"):
        unlearn(run, "fire")


def _result(**over: object) -> DefenceResult:
    base: dict[str, object] = {"won": True, "lives_left": 28, "lives_lost": 2, "gold_left": 40,
                               "tower_costs": 100, "xp_earned": 30.0,
                               "goals": ((Drawn("lean", "8"), MET),), "salvage_earned": 1}
    return DefenceResult(**{**base, **over})  # type: ignore[arg-type]


def test_a_win_settles_pool_gold_xp_sigils_and_draws_on():
    run = finish(start(4), _result())
    assert run.pool == 28
    assert run.gold == 40 + dismantle(100) == 40 + int(100 * DISMANTLE_REFUND)
    assert run.index == 1 and run.location.key == "graveyard"
    assert len(run.drawn) == 3
    assert run.records[0].sigils == lives_sigils(2) + 1 == 3
    assert run.skill_points == 3 + (run.level - 1)
    assert run.salvage == 1


def test_an_open_goal_closes_by_its_kind_and_a_countable_goal_fails():
    run = finish(start(4), _result(goals=((Drawn("lean", "8"), OPEN), (Drawn("bonus", "2"), OPEN))))
    assert [verdict for _, verdict in run.records[0].goals] == [MET, FAILED]
    assert run.records[0].sigils == lives_sigils(2) + 1


def test_a_loss_ends_the_run_at_its_location_and_pays_nothing():
    run = start(4)
    lost = finish(run, _result(won=False, lives_left=0, lives_lost=30,
                               goals=((Drawn("lean", "8"), OPEN), (Drawn("bonus", "2"), MET))))
    assert lost.lost and not lost.won
    assert lost.index == 0 and lost.pool == 0
    assert lost.records[0].sigils == 0
    assert [verdict for _, verdict in lost.records[0].goals] == [FAILED, FAILED]


def test_winning_the_temple_wins_the_run():
    run = replace(start(4), index=11)
    won = finish(run, _result())
    assert won.won and not won.lost
    assert won.drawn == ()


def _fold(key: str, arg: str, *events: tuple):
    fold = make(Drawn(key, arg))
    for event in events:
        fold.observe(event)
    return fold


def test_a_lean_defence_fails_past_its_towers_and_warns_at_the_cap():
    fold = _fold("lean", "2", ("built", 1), ("built", 2), ("sold", 1, (0, 0), 5), ("built", 3))
    assert fold.verdict() == OPEN
    fold.observe(("built", 4))
    assert fold.verdict() == FAILED
    capped = _fold("lean", "1", ("built", 1))
    assert "at most 1 tower" in (capped.warn("build", {"kind": "arrow"}) or "")
    assert capped.warn("sell", {"tower": 1}) is None
    assert make(Drawn("lean", "2")).warn("build", {"kind": "arrow"}) is None


def test_the_gate_must_stand_by_wave_two_and_never_fall():
    assert _fold("gate", "", ("wave", 0), ("door_built", 0)).verdict() == OPEN
    assert _fold("gate", "", ("wave", 0), ("wave", 1), ("wave", 2)).verdict() == FAILED
    assert _fold("gate", "", ("door_built", 0), ("door_broken", 0)).verdict() == FAILED


def test_one_family_judges_every_tower_built():
    assert _fold("family", "fire", ("built", 1, "pyre"), ("built", 2, "pyre")).verdict() == OPEN
    assert _fold("family", "fire", ("built", 1, "pyre"), ("built", 2, "arrow")).verdict() == FAILED
    assert _fold("family", "!physical", ("built", 1, "pyre")).verdict() == OPEN
    assert _fold("family", "!physical", ("built", 1, "ballista")).verdict() == FAILED
    fold = make(Drawn("family", "fire"))
    assert fold.warn("build", {"kind": "storm"}) is not None
    assert fold.warn("build", {"kind": "pyre"}) is None


def test_the_leaders_die_first_or_curse_first():
    assert _fold("leaders", "", ("spawn", 1, "bone_priest"), ("spawn", 2, "shaman"),
                 ("death", 1, "bone_priest", "fire", (0, 0), 5),
                 ("death", 2, "shaman", "fire", (0, 0), 5)).verdict() == MET
    assert _fold("leaders", "", ("spawn", 1, "bone_priest"), ("spawn", 2, "shaman"),
                 ("death", 1, "bone_priest", "fire", (0, 0), 5),
                 ("cursed", 2, (0, 0), "rot", (2,))).verdict() == FAILED
    assert _fold("leaders", "", ("spawn", 1, "azazel"),
                 ("cursed", 1, (0, 0), "rot", (2,))).verdict() == OPEN
    failed = _fold("leaders", "", ("spawn", 1, "shaman"), ("cursed", 1, (0, 0), "rot", (2,)),
                   ("death", 1, "shaman", "fire", (0, 0), 5))
    assert failed.verdict() == FAILED   # a curse cannot be un-cursed by the kill


def test_a_fragile_hymn_counts_only_the_hymns_no_curse_touches():
    fold = _fold("hymn", "2", ("step", 0.0), ("hymn", 1), ("step", 1.0),
                 ("cursed", 9, (0, 0), "rot", (1,)), ("step", 7.0), ("hymn", 2), ("step", 14.0),
                 ("hymn", 3), ("end",))
    assert fold.verdict() == MET
    short = _fold("hymn", "2", ("hymn", 1), ("end",))
    assert short.verdict() == OPEN and short.close_default == FAILED


def test_the_bonus_needs_a_clearing_at_its_stake_or_more():
    assert _fold("bonus", "2", ("bonus", 1, "cleared")).verdict() == OPEN
    assert _fold("bonus", "2", ("bonus", 1, "cleared"), ("bonus", 3, "cleared")).verdict() == MET
    assert _fold("bonus", "2", ("bonus", 2, "failed")).verdict() == OPEN


def test_every_goal_has_its_camp_line():
    assert "at most 8 towers" in describe(Drawn("lean", "8"))
    assert "by wave 2" in describe(Drawn("gate", ""))
    assert "every tower built is fire" in describe(Drawn("family", "fire"))
    assert "no tower built is physical" in describe(Drawn("family", "!physical"))
    assert "every leader dies before its first curse lands" in describe(Drawn("leaders", ""))
    assert "3 times" in describe(Drawn("hymn", "3"))
    assert "stake 2 or more" in describe(Drawn("bonus", "2"))
    with pytest.raises(KeyError):
        describe(Drawn("nope", ""))


def test_bonus_stakes_fight_coming_hosts_with_an_elite_or_a_leader():
    temple = LOCATIONS["temple"]
    one, two, three = (bonus_pack(temple, stake, 9, 11) for stake in (1, 2, 3))
    assert one.life_factor == two.life_factor == three.life_factor == 1.0
    assert one.extra is None
    assert two.extra is not None and three.extra is not None
    assert MONSTERS[two.extra].leader is None and not MONSTERS[two.extra].boss
    assert MONSTERS[three.extra].leader is not None
    assert one.groups == temple.waves[1].groups
    assert two.groups == temple.waves[2].groups
    assert three.groups == two.groups != one.groups
    capped = bonus_pack(temple, 3, 9, 11, wave=4)
    assert capped.groups == temple.waves[4].groups
    assert one.wager == BALANCE.income_unit()
    assert one.profit == round(PROFIT[0] * BALANCE.income_unit())
    assert three.profit == round(PROFIT[2] * BALANCE.income_unit())
    assert one.lives > 0 and one.xp > 0


def test_bonus_repeats_pay_less_and_bad_stakes_are_refused():
    temple = LOCATIONS["temple"]
    first = bonus_pack(temple, 3, 9, 11)
    again = bonus_pack(temple, 3, 9, 11, repeats=1)
    assert again.profit == round(first.profit * 0.6)
    assert again.xp == pytest.approx(first.xp * 0.6)
    with pytest.raises(ValueError, match="stake"):
        bonus_pack(temple, 4, 9, 11)


def test_bonus_packs_are_drawn_by_seed_at_every_location():
    assert bonus_pack(LOCATIONS["caves"], 2, 9, 4) == bonus_pack(LOCATIONS["caves"], 2, 9, 4)
    for index, key in enumerate(ORDER):
        pack = bonus_pack(LOCATIONS[key], 2, 9, index)
        assert pack.groups and pack.lives > 0
        assert pack.extra is None or pack.extra in MONSTERS


def test_the_bonus_preview_names_the_pack_the_lives_and_the_reward():
    pack = bonus_pack(LOCATIONS["temple"], 2, 9, 11)
    preview = bonus_preview(pack)
    assert f"Stake 2 for {pack.wager} gold" in preview
    assert f"{pack.lives} lives at stake" in preview
    assert f"{pack.profit} gold" in preview
    assert MONSTERS[pack.groups[0].kind].name in preview
    assert BONUS_EARLY == 2


def test_observing_a_world_reads_its_leftovers_and_runs_the_folds():
    run = start(6)
    world = kit(run).world()
    world.events.append(("built", 1))
    result = observe_world(kit(run), world, (Drawn("lean", "8"),))
    assert result.won is False and result.lives_left == 30 and result.lives_lost == 0
    assert result.gold_left == world.gold and result.tower_costs == 0
    assert result.goals == ((Drawn("lean", "8"), OPEN),)
    world.xp_total = 96.0
    assert observe_world(kit(replace(run, xp=10.0)), world, ()).xp_earned == 96.0


def test_observing_counts_the_lost_life_from_overridden_starting_lives():
    run = start(6)
    played = kit(run)
    world = played.world()
    world.lives = 10 ** 9 - 7
    result = observe_world(played, world, (), lives=10 ** 9)
    assert (result.lives_left, result.lives_lost) == (10 ** 9 - 7, 7)


def test_bonus_packs_are_typed():
    pack = bonus_pack(LOCATIONS["tristram"], 1, 0, 0)
    assert isinstance(pack, BonusPack)


def test_a_run_round_trips_through_json_with_its_records_and_goals():
    import json

    run = start(11)
    settled = finish(run, DefenceResult(True, 24, 6, 500, 300, 12.0,
                                        ((Drawn("lean", "8"), MET), (Drawn("gate", ""), FAILED)), 3))
    back = from_json(json.loads(json.dumps(to_json(settled))))
    assert back == settled
    assert back.records[0].sigils == settled.records[0].sigils
    won = from_json(to_json(replace(settled, index=len(ORDER), drawn=())))
    assert won.won and won.drawn == ()


def test_a_run_outside_the_campaign_is_refused():
    from hellward.run import Record

    run = start(11)
    with pytest.raises(ValueError):
        from_json({**to_json(run), "index": 99})
    stray = replace(run, records=(Record("mordor", 0, 0),))
    with pytest.raises(ValueError):
        from_json(to_json(stray))
