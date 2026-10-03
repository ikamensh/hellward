"""The story walk (tools/llm_story.py): the beats follow the player's own order — the prologue,
then per location its before page, its briefing, its fight and its after page, each act's ending in
place of its last location's after page — and every beat's panel exists on disk."""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load_walk():
    spec = importlib.util.spec_from_file_location("llm_story", TOOLS / "llm_story.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_story"] = module
    spec.loader.exec_module(module)
    return module


walk = load_walk()

from hellward.audio.music import BOSS_BLURBS, DUNGEONS  # noqa: E402
from hellward.sim.breaches import BREACHES  # noqa: E402
from hellward.sim.campaign import ACT_ENDS, LOCATIONS, ORDER  # noqa: E402
from hellward.sim.content import MONSTERS  # noqa: E402
from hellward.story import LAST_PAGES, STORIES  # noqa: E402


def test_beats_open_with_the_prologue_in_the_timeline_order():
    timeline = json.loads((walk.PROLOGUE_DIR / "timeline.json").read_text())
    shots = [str(s["key"]) for s in timeline["shots"]]
    keys = [beat.key for beat in walk.beats()]
    assert keys[:len(shots)] == [f"prologue/{shot}" for shot in shots]
    assert keys[0] == "prologue/glass"
    assert "prologue/title" in keys


def test_prologue_beats_carry_every_caption_in_order():
    timeline = json.loads((walk.PROLOGUE_DIR / "timeline.json").read_text())
    told = [line for beat in walk.prologue_beats() for line in beat.body
            if not line.startswith("(") and line != "HELLWARD"
            and not line.startswith("Keep it burning")]
    assert told == [str(w["text"]) for w in timeline["words"]]


def test_each_location_plays_before_then_briefing_then_fight_then_after_or_ending():
    keys = [beat.key for beat in walk.beats()]
    for location in ORDER:
        before = f"{location}-before"
        briefing = f"{location}/briefing"
        battle = f"{location}/battle"
        assert keys.index(before) < keys.index(briefing) < keys.index(battle), location
        if location in ACT_ENDS.values():
            act = LOCATIONS[location].act
            first = STORIES[LAST_PAGES[act]].pages[0].key
            assert keys.index(battle) < keys.index(first), location
            assert f"{location}-after" not in keys, location
        else:
            after = f"{location}-after"
            assert keys.index(battle) < keys.index(after), location
    assert keys[-1] == STORIES[LAST_PAGES[2]].pages[-1].key


def test_every_story_page_appears_exactly_once():
    pages = [page.key for story in STORIES.values() for page in story.pages]
    played = [beat.key for beat in walk.beats() if beat.key in set(pages)]
    assert sorted(played) == sorted(pages)


def test_briefings_carry_the_taunt_the_lesson_and_the_blurb():
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        body = "\n".join(beats[f"{location}/briefing"].body)
        place = LOCATIONS[location]
        assert place.taunt in body and place.lesson in body and place.blurb in body


def test_every_beat_panel_exists_on_disk():
    for beat in walk.beats():
        for panel in beat.panels:
            assert (ROOT / panel).is_file(), panel


def test_fights_count_the_authored_waves_and_bodies():
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        waves = LOCATIONS[location].waves
        bodies = sum(group.count for wave in waves for group in wave.groups)
        body = list(beats[f"{location}/battle"].body)
        assert body[0] == f"{len(waves)} waves, {bodies} bodies", location
        assert len([line for line in body if line.startswith("w")]) == len(waves), location
        for i, name in enumerate(LOCATIONS[location].wave_names):
            assert any(line.startswith(f"w{i + 1} \u2018{name}\u2019:") for line in body), (location, name)


def test_fights_name_each_kind_where_it_first_walks_and_mark_stand_ins():
    beats = {beat.key: beat for beat in walk.beats()}
    seen: dict[str, str] = {}
    for location in ORDER:
        body = "\n".join(beats[f"{location}/battle"].body)
        kinds = {group.kind for wave in LOCATIONS[location].waves for group in wave.groups}
        new = sorted(kinds - seen.keys())
        for kind in kinds:
            seen.setdefault(kind, location)
        if new:
            (line,) = [line for line in body.splitlines() if line.startswith("new here:")]
            marked = [item.strip() for item in line.removeprefix("new here:").split(",")]
            names = [m.removesuffix(" (stand-in)") for m in marked]
            assert sorted(names) == sorted(MONSTERS[k].name for k in new), location
            by_name = {MONSTERS[k].name: k for k in new}
            for item, name in zip(marked, names):
                assert item.endswith(" (stand-in)") == (not walk.modelled(by_name[name])), (location, name)
        else:
            assert "new here:" not in body, location
    breached = {g.kind for spec in BREACHES.values() for g in spec.groups}
    assert sorted(set(seen) | breached) == sorted(walk.walked_kinds()), "the sheet shows every kind that walks"


def test_fights_carry_the_breach_where_one_is_offered():
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        body = "\n".join(beats[f"{location}/battle"].body)
        if location in BREACHES:
            spec = BREACHES[location]
            assert f"breach after w{spec.after_wave + 1}: {spec.name}" in body, location
            assert spec.blurb in body, location
        else:
            assert "breach after" not in body, location


def test_fights_state_the_client_objective():
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        body = "\n".join(beats[f"{location}/battle"].body)
        assert "objective: Hold the sanctuary — where your lantern burns — until the last wave breaks." in body, location


def test_fights_carry_the_music_and_the_boss_break_in():
    assert all(BOSS_BLURBS.values())
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        assert DUNGEONS[location].blurb, location
        body = "\n".join(beats[f"{location}/battle"].body)
        assert f"music: battle_{location} — {DUNGEONS[location].blurb}" in body, location
        bosses = {g.kind for g in LOCATIONS[location].waves[-1].groups
                  if MONSTERS[g.kind].boss}
        if bosses:
            assert "breaks in with boss" in body, location
            for kind in bosses:
                assert MONSTERS[kind].name in body and BOSS_BLURBS[kind] in body, (location, kind)
        else:
            assert "breaks in with boss" not in body, location


def test_fights_name_what_the_leaders_raise():
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        body = "\n".join(beats[f"{location}/battle"].body)
        raisers = {g.kind for wave in LOCATIONS[location].waves for g in wave.groups
                   if MONSTERS[g.kind].leader is not None and MONSTERS[g.kind].leader.raises}
        for kind in raisers:
            raised = MONSTERS[MONSTERS[kind].leader.raises].name
            assert f"{MONSTERS[kind].name}" in body and f"raises {raised}" in body, (location, kind)


def test_fights_gauge_the_hardship():
    assert sorted(walk.DIFFICULTY) == sorted(ORDER)
    beats = {beat.key: beat for beat in walk.beats()}
    for location in ORDER:
        veteran, best = walk.DIFFICULTY[location]
        (line,) = [line for line in beats[f"{location}/battle"].body if line.startswith("hardship")]
        assert f"\u00d7{best:g} best bot" in line and walk.DIFFICULTY_SOURCE in line, location
        if veteran is None:
            assert "veteran" not in line, location
        else:
            assert f"\u00d7{veteran:g} veteran" in line, location


def test_first_fight_opens_the_monster_sheet():
    beats = [beat for beat in walk.beats() if beat.key.endswith("/battle")]
    assert beats[0].panels[0] == walk._rel(walk.STILLS_DIR / "monsters.jpg")
    assert all("monsters.jpg" not in panel for beat in beats[1:] for panel in beat.panels)


def test_commands_list_show_and_all(capsys):
    assert walk.main(["list"]) == 0
    listed = capsys.readouterr().out
    assert "prologue/glass" in listed and "act2-end-4" in listed
    assert walk.main(["show", "1"]) == 0
    assert "PROLOGUE" in capsys.readouterr().out
    assert walk.main(["show", "temple-before", "--notes"]) == 0
    assert "paint:" in capsys.readouterr().out
    assert walk.main(["show", "no-such-beat"]) == 1
    assert walk.main(["all"]) == 0
    assert "Keep it burning" in capsys.readouterr().out
