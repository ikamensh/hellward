"""Hellward's audio: the cue set the scene plays, the rendered files, the bank's rules and the music loops.

The cache is prepared once for the module (effects and all eight tracks), the way the game does
before its first frame; every test reads what the game would play.
"""

from __future__ import annotations

from pathlib import Path
import random

import numpy as np
import pytest

from hellward.audio import bank as bank_module
from hellward.audio.bank import BURST, BURST_WINDOW, CROWD, CROWD_WINDOW, VERSION, SoundBank
from hellward.audio.cues import CUES, files, loudness
from hellward.audio.music import PIECES
from hellward.sim.content import MONSTERS
from saga2d import Game
from sagaforge.foley import mono, read_wav
from sagaforge.synth import SAMPLE_RATE

SCENE_CUES = {"click", "refuse", "build", "upgrade", "sell", "door_build", "door_hit", "door_break", "wave", "cleared", "leak",
              "gold", "cleanse", "ponder", "chant", "curse", "fizzle", "fire_cast", "fire_hit", "fireball", "lightning", "frost",
              "venom_cast", "venom_hit", "victory", "defeat", "smite", "meteor_fall", "meteor", "orb", "ward", "broken"}
STEMS = list(files())


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("hellward-audio")
    SoundBank.prepare(root, wait=True)
    return root


@pytest.fixture
def game(cache: Path):
    g = Game("Hellward test", backend="mock", resolution=(800, 600), asset_path=cache)
    yield g
    g.close()


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def played(game: Game) -> list[tuple[str, float]]:
    """(file stem, pitch) of every effect the mock backend was asked to play."""
    stems = {game.assets.sound(stem): stem for stem in STEMS}
    return [(stems[p["handle"]], p["pitch"]) for p in game.backend.sounds_played]


def sound(cache: Path, stem: str) -> np.ndarray:
    return read_wav(cache / "sounds" / f"{stem}.wav")


def centroid(clip: np.ndarray) -> float:
    x = mono(clip)
    spectrum = np.abs(np.fft.rfft(x))
    return float((spectrum * np.fft.rfftfreq(len(x), 1 / SAMPLE_RATE)).sum() / spectrum.sum())


def takes(cue: str) -> list[str]:
    return CUES[cue].files(cue)


def cue_of(stem: str) -> str:
    return stem if stem in CUES else stem.rsplit("_", 1)[0]


# -- The cue set and the files --------------------------------------------------------------


def test_the_cues_are_exactly_what_the_scene_plays():
    assert set(CUES) == SCENE_CUES | {f"death_{kind}" for kind in MONSTERS}


@pytest.mark.parametrize("stem", STEMS)
def test_every_cue_file_is_a_clean_sound(cache: Path, stem: str):
    """Non-silent, finite, under full scale, a sensible length, and silent at both edges: no click on start or stop."""
    clip = sound(cache, stem)
    x = np.abs(mono(clip))
    peak = float(x.max())
    assert np.isfinite(x).all()
    assert 0.1 < peak < 1.0
    assert 0.04 <= len(x) / SAMPLE_RATE <= 7.0
    assert x[0] < 1e-3 and x[-1] < 1e-3
    assert x[:int(0.0005 * SAMPLE_RATE)].max() < 0.3 * peak, "it swells in, however sharp the blow"
    assert x[-int(0.002 * SAMPLE_RATE):].max() < 0.05 * peak, "it fades out rather than stopping"


def test_several_takes_of_what_plays_often():
    for cue in ("door_hit", "fire_hit", "fire_cast", "lightning", "frost", "venom_hit", "gold") + tuple(f"death_{kind}" for kind in MONSTERS):
        assert CUES[cue].takes >= 2, cue


def test_interface_cues_sit_under_the_fight(cache: Path):
    ui = max(loudness(sound(cache, stem)) for cue in ("click", "refuse") for stem in takes(cue))
    fight = min(loudness(sound(cache, stem)) for cue in ("door_hit", "fire_hit", "death_goatman") for stem in takes(cue))
    assert ui < 0.7 * fight


def test_bigger_monsters_die_lower(cache: Path):
    def mean_centroid(cue: str) -> float:
        return float(np.mean([centroid(sound(cache, stem)) for stem in takes(cue)]))

    assert mean_centroid("death_overlord") < mean_centroid("death_fallen")
    assert mean_centroid("death_azazel") < mean_centroid("death_fallen")
    assert mean_centroid("death_overlord") < mean_centroid("death_shaman")


def test_a_fireball_booms_more_than_a_fire_bolt(cache: Path):
    """The burst carries more energy under 100 Hz than any single bolt landing, level for level."""
    def bass(stem: str) -> float:
        x = mono(sound(cache, stem))
        power = np.abs(np.fft.rfft(x)) ** 2 / len(x)
        return float(power[np.fft.rfftfreq(len(x), 1 / SAMPLE_RATE) < 100].sum())

    assert min(bass(s) for s in takes("fireball")) > max(bass(s) for s in takes("fire_hit"))


def test_frost_and_lightning_ring_brighter_than_fire(cache: Path):
    fire = max(centroid(sound(cache, stem)) for stem in takes("fire_hit") + takes("fireball"))
    assert min(centroid(sound(cache, stem)) for stem in takes("frost") + takes("lightning")) > 2 * fire


def test_the_wave_bell_rings_on(cache: Path):
    for stem in takes("wave"):
        assert len(sound(cache, stem)) / SAMPLE_RATE > 3.0


def test_stingers_last_three_to_six_seconds(cache: Path):
    for cue in ("victory", "defeat"):
        assert 3.0 <= len(sound(cache, cue)) / SAMPLE_RATE <= 6.0


# -- Preparing the cache -----------------------------------------------------------------------


def test_prepare_writes_every_file_and_is_idempotent(cache: Path):
    assert (cache / "sounds" / "VERSION").read_text() == VERSION
    for stem in STEMS:
        assert (cache / "sounds" / f"{stem}.wav").exists()
    for name in PIECES:
        assert (cache / "music" / f"{name}.wav").exists()
    before = {p: p.stat().st_mtime_ns for p in cache.rglob("*.wav")}
    SoundBank.prepare(cache, wait=True)
    assert {p: p.stat().st_mtime_ns for p in cache.rglob("*.wav")} == before


def test_prepare_restores_a_missing_cue(cache: Path):
    victim = cache / "sounds" / "door_hit_2.wav"
    kept = cache / "sounds" / "click.wav"
    stamp = kept.stat().st_mtime_ns
    victim.unlink()
    SoundBank.prepare(cache, wait=True)
    assert victim.exists() and kept.stat().st_mtime_ns == stamp


def test_a_new_version_discards_the_whole_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(bank_module, "COMPOSE_ORDER", ())  # composing is covered by the module cache
    (tmp_path / "sounds").mkdir()
    (tmp_path / "music").mkdir()
    (tmp_path / "sounds" / "VERSION").write_text("old")
    (tmp_path / "sounds" / "retired_cue.wav").write_bytes(b"")
    (tmp_path / "music" / "title.wav").write_bytes(b"")
    SoundBank.prepare(tmp_path)
    assert (tmp_path / "sounds" / "VERSION").read_text() == VERSION
    assert not (tmp_path / "sounds" / "retired_cue.wav").exists() and not (tmp_path / "music" / "title.wav").exists()
    assert all((tmp_path / "sounds" / f"{stem}.wav").exists() for stem in STEMS)


def test_a_bank_needs_a_prepared_cache(tmp_path: Path):
    g = Game("Hellward test", backend="mock", resolution=(800, 600), asset_path=tmp_path)
    try:
        with pytest.raises(RuntimeError, match="prepare"):
            SoundBank(g)
    finally:
        g.close()


# -- The bank --------------------------------------------------------------------------------------


def test_every_cue_plays_through_the_game(game: Game):
    clock = Clock()
    bank = SoundBank(game, clock=clock, seed=1)
    for cue in CUES:
        clock.now += 1.0
        assert bank.play(cue, x=12.5)
    assert len(game.backend.sounds_played) == len(CUES)
    with pytest.raises(KeyError):
        bank.play("trumpet")


def test_the_voice_budget_holds_battle_cues_back(game: Game):
    clock = Clock()
    bank = SoundBank(game, clock=clock, seed=2)
    deaths = [cue for cue, spec in CUES.items() if spec.kind == "battle" and cue.startswith("death_")]
    assert sum(bank.play(cue) for cue in deaths) == BURST
    assert bank.play("click") and bank.play("wave"), "interface cues and alerts are never held back"
    for _ in range(3):  # later bursts fill the crowd window, then it is full
        clock.now += BURST_WINDOW + 0.001
        for cue in deaths:
            bank.play(cue)
    assert sum(CUES[cue_of(stem)].kind == "battle" for stem, _ in played(game)) == CROWD
    clock.now += CROWD_WINDOW
    assert bank.play(deaths[0])


def test_the_last_voice_of_a_burst_is_kept_for_a_death(game: Game):
    clock = Clock()
    bank = SoundBank(game, clock=clock, seed=8)
    assert bank.play("fire_cast") and bank.play("fire_hit") and bank.play("death_zombie")
    assert not bank.play("lightning") and not bank.play("venom_cast"), "three voices taken: tower sounds wait"
    assert bank.play("death_goatman")


def test_a_busy_fight_does_not_clip(game: Game, cache: Path):
    """A second of towers firing and monsters dying, as many as the budget admits, mixed at full volume."""
    clock = Clock()
    bank = SoundBank(game, clock=clock, seed=3)
    rng = random.Random(4)
    battle = [cue for cue, spec in CUES.items() if spec.kind == "battle"]
    start = clock.now
    times = []
    for at in sorted(rng.uniform(0, 1.0) for _ in range(200)):
        clock.now = start + at
        if bank.play(rng.choice(battle)):
            times.append(at)
    stems = [stem for stem, _ in played(game)]
    assert len(stems) >= 12
    mix = np.zeros(int(8 * SAMPLE_RATE))
    for at, stem in zip(times, stems):
        x = mono(sound(cache, stem))
        i = int(at * SAMPLE_RATE)
        mix[i:i + len(x)] += x
    assert np.abs(mix).max() < 1.0


def test_takes_rotate_and_the_pitch_wanders(game: Game):
    clock = Clock()
    bank = SoundBank(game, clock=clock, seed=5)
    for _ in range(40):
        clock.now += 1.0
        bank.play("door_hit")
    stems, pitches = zip(*played(game))
    assert all(a != b for a, b in zip(stems, stems[1:])), "never the same take twice in a row"
    assert set(stems) == set(takes("door_hit"))
    assert all(0.96 <= p <= 1.04 for p in pitches) and len(set(pitches)) > 30


def test_music_starts_and_crossfades(game: Game):
    bank = SoundBank(game, seed=6)
    assert all(bank.ready(name) for name in PIECES)
    bank.music("title")
    assert game.audio.music_name == "title"
    bank.music("battle_cathedral")
    assert game.audio.music_name == "battle_cathedral"
    assert len(game.backend.music_players) == 2, "the title fades out under the battle"
    bank.music("battle_cathedral")
    assert len(game.backend.music_players) == 2, "asking again changes nothing"
    bank.stop_music(0.5)
    assert game.audio.music_name is None


def test_music_waits_for_its_track(game: Game, cache: Path, monkeypatch: pytest.MonkeyPatch):
    bank = SoundBank(game, seed=7)
    track = cache / "music" / "boss.wav"
    hidden = track.with_name("boss.hidden")
    track.rename(hidden)
    try:
        monkeypatch.setitem(SoundBank._composers, bank.cache_dir, _Alive())
        bank.music("boss")
        assert game.audio.music_name is None
        hidden.rename(track)
        bank.poll()
        assert game.audio.music_name == "boss"
    finally:
        if hidden.exists():
            hidden.rename(track)


class _Alive:
    """A composer still at work."""

    def is_alive(self) -> bool:
        return True


# -- The music -----------------------------------------------------------------------------------------


def test_every_location_has_its_own_battle_track():
    from hellward.audio.music import BATTLE_FOR, PIECES, track_for

    assert len(set(BATTLE_FOR.values())) == len(BATTLE_FOR), "every dungeon sounds different"
    for key, track in BATTLE_FOR.items():
        assert track in PIECES, f"{key} -> {track} not in PIECES"
        # round-trip
        assert track_for(key) == track


@pytest.mark.parametrize("name, low, high", [
    ("title", 40, 50),
    ("battle_tristram", 50, 62),
    ("battle_graveyard", 43, 53),
    ("battle_cathedral", 48, 58),
    ("battle_catacombs", 38, 48),
    ("battle_caves", 36, 46),
    ("battle_hells_gate", 40, 50),
    ("battle_docks", 43, 53),
    ("battle_spider_forest", 33, 43),
    ("battle_jungle", 35, 45),
    ("battle_drowned_city", 52, 62),
    ("battle_travincal", 48, 58),
    ("battle_temple", 53, 63),
    ("boss", 45, 60),
])
def test_music_is_a_seamless_stereo_loop(cache: Path, name: str, low: float, high: float):
    clip = read_wav(cache / "music" / f"{name}.wav")
    assert clip.ndim == 2 and clip.shape[1] == 2
    assert low <= len(clip) / SAMPLE_RATE <= high
    assert 0.3 < np.abs(clip).max() < 0.81
    step = np.abs(np.diff(clip, axis=0))
    seam = np.abs(clip[0] - clip[-1])
    assert (seam <= np.percentile(step, 99.5, axis=0)).all(), "the loop point jumps like no other sample does"
