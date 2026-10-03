"""The corpus deals the standard Kit: conventions, takes and the deal itself."""

from hellward.sim.campaign import LOCATIONS, ORDER
from hellward.sim.items import EMPTY_LOADOUT
from hellward.sim.players import PLAYERS
from hellward.sim.players.hands import reference_kit
from hellward.sim.relics import DOWNSIDES
from tools.corpus import EVAL_SEEDS, FEEDERS, deal, sigils_for, takes


def test_the_conventions():
    assert EVAL_SEEDS == tuple(range(1000, 1008))
    assert sigils_for("temple") == 33 and sigils_for(LOCATIONS["caves"]) == 3 * ORDER.index("caves")
    assert {"apprentice", "veteran", "warden", "planned"} <= set(PLAYERS)
    assert set(FEEDERS) == {"adaptive_skills", "adapt", "campaign_balance", "margin", "plan_player",
                            "sim_bench"}


def test_takes_are_seeded_synergistic_and_pact_free():
    held = takes(1000, 8)
    assert held == takes(1000, 8) and len(held) == 8 and not set(held) & set(DOWNSIDES)
    assert takes(1001, 8) != held


def test_the_deal_matches_a_hand_rolled_kit():
    place = LOCATIONS["jungle"]
    player = PLAYERS["planned"](7)
    learned = player.draft(place, sigils_for(place), ("war_tithe",))
    want = reference_kit(place, learned, 7, relics=("war_tithe",))
    kit = deal("jungle", "planned", 7, relics=("war_tithe",))
    assert (kit.location, kit.learned, kit.loadout, kit.gold, kit.lives, kit.seed, kit.relics) == \
        (want.location, want.learned, want.loadout, want.gold, want.lives, want.seed, want.relics)


def test_the_deal_honors_its_knobs():
    kit = deal("caves", PLAYERS["veteran"](3), 3, sigils=0, loadout=EMPTY_LOADOUT, gold=5, lives=9)
    assert (kit.gold, kit.lives, kit.seed, kit.relics) == (5, 9, 3, ())
    assert kit.learned == PLAYERS["veteran"](3).draft(LOCATIONS["caves"], 0)
    kit = deal("caves", "veteran", 3, relics=(), kit_relics=("spite",))
    assert kit.relics == ("spite",)
    assert kit.learned == PLAYERS["veteran"](3).draft(LOCATIONS["caves"], sigils_for("caves"))
