"""The LLM seat: budgets, advisors, autos, the turn loop and the kept campaign."""

from __future__ import annotations

import json
import time
from pathlib import Path

from hellward.llm import advisor
from hellward.llm.driver import Session, policy_for
from hellward.llm.view import briefing, field, status
from hellward.server import protocol
from hellward.server.campaign import Campaign
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import MONSTERS
from hellward.sim.model import World
from hellward.sim.players.adaptive import Adaptive
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import defend


def campaign_at(data: Path, profile: str = "llm") -> Campaign:
    return Campaign(data, planner=policy_for("smart", 0), demo_player=Adaptive, seed=0, profile=profile)


def tiles(session: Session, kind: str, n: int) -> list[tuple[int, int]]:
    """Legal build tiles from the advisor, so the tests survive a remapped Tristram."""
    return [s.tile for s in advisor.placement(session.world, kind, top=n)]


def test_budgets() -> None:
    session = Session("tristram", seed=0)
    assert len(briefing(session.world, seed=0, skills=frozenset())) < 6000
    assert len(status(session.world)) < 1600
    session.do("build arrow 14 10")
    session.do("build arrow 16 7")
    session.do("call")
    digest = session.do("wait 4")
    assert len(digest) < 1200
    assert len(session.do("advise arrow")) < 800
    assert len(field(session.world)) < 800


def test_budgets_late_campaign() -> None:
    session = Session("temple", seed=0)
    assert len(briefing(session.world, seed=0, skills=frozenset())) < 6000
    assert len(status(session.world)) < 1600


def test_build_refusals_change_nothing() -> None:
    session = Session("tristram", seed=0)
    assert "refused" in session.do("build arrow 0 0")   # the wall, not the floor
    assert "refused" in session.do("build pyre 14 10")   # not offered in Tristram
    assert session.world.gold == 36
    assert "refused" in session.do("smite 999")
    assert "bad" in session.do("build arrow 1")


def test_rank_and_sell() -> None:
    session = Session("tristram", seed=0)
    (x, y), = tiles(session, "arrow", 1)
    session.do(f"build arrow {x} {y}")
    price = session.world.gold
    assert "refused" in session.do(f"up {x} {y}")   # no rank skill, no gold spent
    assert session.world.gold == price
    assert "sold" in session.do(f"sell {x} {y}")
    assert session.world.gold > price


def test_advise_is_deterministic_and_quick() -> None:
    first = Session("tristram", seed=3).do("advise arrow")
    second = Session("tristram", seed=3).do("advise arrow")
    assert first == second
    assert first.startswith("arrow tiles: (")
    session = Session("tristram", seed=3)
    start = time.perf_counter()
    advisor.placement(session.world, "arrow")
    assert time.perf_counter() - start < 1.0


def test_advise_wave_and_upgrade() -> None:
    session = Session("tristram", seed=0)
    waves = len(session.world.waves)
    assert "w1" in session.do("advise wave") and "arrow" in session.do("advise wave")
    assert f"w{waves}" in session.do(f"advise wave {waves}")
    assert "bad advise" in session.do(f"advise wave {waves + 1}")
    (x, y), = tiles(session, "arrow", 1)
    session.do(f"build arrow {x} {y}")
    assert "rank arrow" in session.do(f"advise up {x} {y}")
    assert "no tower" in session.do("advise up 0 0")


def test_autos_toggle() -> None:
    session = Session("tristram", seed=0)
    assert "smite_leader=on" in session.do("auto")
    assert "hymn=off" in session.do("auto")
    assert "hymn=on" in session.do("auto hymn on")
    assert "hymn=off" in session.do("auto hymn off")
    assert "bad" in session.do("auto frobnicate on")


def test_wave_one_fight_reports_kills_and_autos() -> None:
    session = Session("tristram", seed=0)
    for x, y in tiles(session, "arrow", 3):
        session.do(f"build arrow {x} {y}")
    session.do("call")
    log = session.do("watch")
    assert "started w1" in log
    assert "cleared w1" in log
    expected = sum(g.count * MONSTERS[g.kind].lives for g in session.world.waves[0].groups)
    assert session.world.kills + (20 - session.world.lives) == expected


def test_shaman_wave_reports_curses() -> None:
    session = Session("tristram", seed=1)
    for x, y in tiles(session, "arrow", 3):
        session.do(f"build arrow {x} {y}")
    session.do("call")
    log = ""
    for _ in range(12):   # through w1, w2 and into the shaman's w3
        log += session.do("wait 30")
        if "curses:" in log or session.world.outcome is not None:
            break
    assert "curses:" in log


def test_threats_and_smite() -> None:
    session = Session("tristram", seed=0)
    session.do("build arrow 14 10")
    session.do("call")
    session.do("wait 6")
    assert "smite hits for" in session.do("threats")
    row = session.do("threats")
    if "#" in row:   # a target worth it: smite the first id named
        ident = row.split("#")[1].split()[0]
        assert "smitten" in session.do(f"smite {ident}")


def test_quit_and_unknown() -> None:
    session = Session("tristram", seed=0)
    assert "unknown command" in session.do("frobnicate")
    session.do("quit")
    assert session.closed


def test_lab_has_no_meta_progression() -> None:
    session = Session("tristram", seed=0)
    assert "No profile" in session.do("campaign")
    assert "No profile" in session.do("learn adept_arrow")
    assert "No profile" in session.do("forge")
    assert "Tristram" in session.do("defend tristram")   # the lab defends freely


def test_campaign_gates_and_maps(tmp_path: Path) -> None:
    session = Session("tristram", seed=0, campaign=campaign_at(tmp_path / "data"))
    seen = session.do("campaign")
    assert "0 free of 0 sigils" in seen
    assert "tristram:open" in seen and "graveyard:-" in seen
    assert "refused" in session.do("defend graveyard")
    assert "refused" in session.do("learn adept_arrow")
    assert "0 sigils free of 0 won" in session.do("skills")
    assert "salvage" in session.do("forge")
    assert "*llm" in session.do("profiles")


def test_meta_budgets(tmp_path: Path) -> None:
    session = Session("tristram", seed=0, campaign=campaign_at(tmp_path / "data"))
    assert len(session.do("campaign")) < 800
    assert len(session.do("skills")) < 2500
    assert len(session.do("forge")) < 1500


def test_learned_skills_reach_the_next_defend(tmp_path: Path) -> None:
    campaign = campaign_at(tmp_path / "data")
    campaign.progress.record_result("tristram", "victory", 20)
    session = Session("tristram", seed=0, campaign=campaign)
    assert session.world.perks.top("arrow") == 0
    assert "learned adept_arrow (1 free of 3)" in session.do("learn adept_arrow")
    assert "*adept_arrow" in session.do("skills")
    session.do("defend tristram")
    assert session.world.perks.top("arrow") == 1
    assert "unlearned all (3 free of 3)" in session.do("unlearn")


def test_profile_persists_between_sessions(tmp_path: Path) -> None:
    data = tmp_path / "data"
    campaign = campaign_at(data)
    campaign.progress.record_result("tristram", "victory", 20)
    Session("tristram", seed=0, campaign=campaign).do("learn adept_arrow")
    reopened = campaign_at(data)
    assert "adept_arrow" in reopened.progress.learned
    assert reopened.progress.best("tristram") == 3
    assert "1 free of 3 sigils" in Session("tristram", seed=0, campaign=reopened).do("campaign")


def test_a_decided_defence_keeps_its_reckoning(tmp_path: Path) -> None:
    data = tmp_path / "data"
    session = Session("tristram", seed=0, campaign=campaign_at(data))
    session.do("build arrow 14 10")
    session.do("call")
    log = ""
    for _ in range(15):
        log += session.do("wait 30")
        if session.world.outcome is not None:
            break
    assert session.world.outcome == "defeat"
    assert "The Sanctuary Has Fallen" in log and "No sigils" in log
    assert "refused: The defence is decided." in session.do("build arrow 1 1")
    assert len(list((data / "replays").glob("*-tristram.json"))) == 1
    assert any((data / "saves").iterdir())


def test_a_logged_defence_replays_identically() -> None:
    """Builds and auto casts through the session, then the log's ghost: the same events."""
    sent: list = []
    session = Session("tristram", seed=0, leaders="none", on_events=sent.extend)
    for x, y in tiles(session, "arrow", 3):
        session.do(f"build arrow {x} {y}")
    session.do("call")
    while session.world.outcome is None:
        session.do("wait 30")
    assert session.battle is not None
    log = session.battle.replay()
    assert any(command[1] == "smite" for command in log["commands"])   # the autos logged too

    replayed: list = []

    def watch(world: World) -> None:
        replayed.extend(protocol.event(world, e) for e in world.events)

    world, _ = defend(LOCATIONS["tristram"], Ghost(log), seed=log["seed"], sigils=0, planner=None,
                      watch=watch)
    assert (world.outcome, world.lives, world.time) == (log["outcome"], log["lives"], log["time"])
    assert json.loads(json.dumps(replayed)) == sent


def test_watch_plays_to_the_next_break() -> None:
    session = Session("tristram", seed=0)
    for x, y in tiles(session, "arrow", 3):
        session.do(f"build arrow {x} {y}")
    session.do("call")
    digest = session.do("watch")
    assert "cleared w1" in digest
    assert session.world.break_left is not None
    assert "afford" in digest or "hold" in digest   # the action line decides the break
    assert len(digest) < 1600


def test_watch_stops_on_leaks() -> None:
    session = Session("tristram", seed=0)
    session.do("call")   # no towers: the wave walks through
    digest = session.do("watch leaks 2")
    assert session.world.lives <= 18
    assert "LEAKED" in digest
    assert session.world.break_left is None   # stopped mid-wave, not at the break
    assert "bad watch" in session.do("watch leaks 0")


def test_advise_count() -> None:
    session = Session("tristram", seed=0)
    assert session.do("advise arrow 8").count("(") == 8
    assert "bad advise" in session.do("advise arrow 99")


def test_smite_picks_its_target() -> None:
    session = Session("tristram", seed=0, autos=set())
    (x, y), = tiles(session, "arrow", 1)
    session.do(f"build arrow {x} {y}")
    session.do("call")
    smitten = ""
    for _ in range(20):   # a wounded foe always walks before the wave is decided
        smitten = session.do("smite")
        if "smitten" in smitten:
            break
        session.do("wait 2")
    assert "smitten" in smitten


def test_status_compresses_towers() -> None:
    session = Session("tristram", seed=0)
    (ax, ay), (bx, by) = tiles(session, "arrow", 2)
    session.do(f"build arrow {ax} {ay}")
    session.do(f"build arrow {bx} {by}")
    assert "arrow×2" in session.do("status")
    assert f"({ax},{ay})" in session.do("status towers")
