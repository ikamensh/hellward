"""The Godot client has what the rules can show: a sound for every cue and track, and a body for every kind.

The client's scripts are read as text: every cue the audio code renders is played somewhere, every cue the client
plays is rendered, every file is in the client's assets (tools/export_audio.py), and every monster and tower kind
the rules have wears a model or a stand-in.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from hellward.audio.cues import CUES, files
from hellward.audio.music import PIECES
from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import MONSTERS, TOWERS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import assets  # noqa: E402

GAME = Path(__file__).resolve().parent.parent / "godot" / "game"
SCRIPTS = "\n".join(p.read_text() for p in sorted((GAME / "scripts").rglob("*.gd")))


def test_every_cue_is_rendered_into_the_client():
    for stem in files():
        assert (GAME / "assets" / "audio" / f"{stem}.wav").is_file(), f"{stem}: run tools/export_audio.py"


def test_every_track_is_rendered_into_the_client_and_every_location_has_its_battle_music():
    for name in PIECES:
        assert (GAME / "assets" / "audio" / f"music_{name}.mp3").is_file(), f"{name}: tools/export_audio.py --music"
    for key in LOCATIONS:
        assert f"battle_{key}" in PIECES
    assert '"battle_" + String(brief["key"])' in SCRIPTS and '"battle_" + String(battle["location"]["key"])' in SCRIPTS


def test_the_client_plays_every_cue_and_only_cues_that_exist():
    played = set(re.findall(r'Sfx\.play\("([a-z_]+)"[,)]', SCRIPTS))
    named = set(re.findall(r'"([a-z_]+)"', SCRIPTS))
    for cue in CUES:
        if cue.startswith("death_"):
            continue
        assert cue in named, f"the client never plays {cue}"
    assert '"death_" + kind' in SCRIPTS, "each kind dies with its own cry"
    assert played <= set(CUES), f"the client plays cues nobody renders: {sorted(played - set(CUES))}"


def test_every_monster_and_tower_kind_wears_a_model_or_a_stand_in():
    monster = (GAME / "scripts" / "monster.gd").read_text()
    tower = (GAME / "scripts" / "tower.gd").read_text()
    models = {p.stem for p in (GAME / "assets" / "models").glob("*.glb")}
    for kind in MONSTERS:
        own = f"mon_{kind}" in models
        assert own or re.search(rf'"{kind}": \["(fallen|shaman|zombie|skeleton)"', monster), kind
    for kind in TOWERS:
        own = f"tower_{kind}" in models or f"tower_{kind}_1" in models
        assert own or re.search(rf'"{kind}": \["(arrow|pyre|frost|storm)"', tower), kind


def test_every_tower_kind_has_its_portrait_hue():
    """The HUD's slots and the briefing's arsenal frame a tower's portrait in its kind's hue (Hud.TOWER_HUES): a kind
    without one broke every Act II briefing once plague, altar and grove wore their own models."""
    table = re.search(r"const TOWER_HUES := \{(.*?)\}", (GAME / "scripts" / "hud.gd").read_text(), re.S)
    for kind in TOWERS:
        assert f'"{kind}":' in table.group(1), f"{kind}: give it a hue in Hud.TOWER_HUES"


def test_every_model_has_the_clips_anchors_and_maps_the_client_uses():
    """tools/assets.py's checks: a monster model has every clip monster.gd plays (and a leader its cast), the
    effect anchors, its maps, and no stand-in left over; a tower kind a model or a stand-in, not both."""
    for kind in MONSTERS:
        assert not assets.monster(kind)["problems"], (kind, assets.monster(kind)["problems"])
    for kind in TOWERS:
        assert not assets.tower(kind)["problems"], (kind, assets.tower(kind)["problems"])


def test_every_client_asset_has_its_import_record_and_no_record_is_orphaned():
    """Godot's .import records are committed with their assets: a model or texture without one imports with a new
    uid on every machine, and a record left behind by a deleted asset is noise."""
    tracked = set(__import__("subprocess").run(["git", "ls-files", "godot/game/assets"], capture_output=True, text=True,
                                               cwd=GAME.parent.parent, check=True).stdout.split())
    for path in tracked:
        if path.endswith(".import"):
            assert path[: -len(".import")] in tracked, f"{path}: its asset is gone"
        elif path.endswith((".glb", ".png", ".jpg", ".webp", ".wav", ".mp3", ".ogg")):
            assert path + ".import" in tracked, f"{path}: commit its .import record"
