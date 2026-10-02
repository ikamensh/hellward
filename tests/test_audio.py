"""Hellward's audio: the cue set, the rendered files and the scores.

The files are rendered once for the module, as tools/export_audio.py renders them for the client; every test reads
what the game would play. (Which cues the client plays: tests/test_client_assets.py.)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hellward.audio.cues import CUES, files, loudness
from hellward.audio.music import PIECES
from hellward.sim.content import MONSTERS
from sagaforge.foley import mono, read_wav
from sagaforge.synth import SAMPLE_RATE, write_wav

SCENE_CUES = {"click", "refuse", "build", "upgrade", "sell", "door_build", "door_hit", "door_break", "wave", "cleared", "leak",
              "gold", "ponder", "chant", "curse", "fizzle", "arrow_cast", "arrow_hit", "ballista_cast", "ballista_hit",
              "knife_cast", "knife_hit", "hook", "fire_cast", "fire_hit", "fireball", "lightning", "frost", "venom_cast",
              "venom_hit", "victory", "defeat", "smite", "hymn", "meteor_fall", "meteor", "orb", "returned"}
STEMS = list(files())


@pytest.fixture(scope="module")
def cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("hellward-audio")
    (root / "sounds").mkdir()
    (root / "music").mkdir()
    for stem, render in files().items():
        write_wav(root / "sounds" / f"{stem}.wav", render())
    for name, piece in PIECES.items():
        write_wav(root / "music" / f"{name}.wav", piece.render())
    return root


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
    for cue in ("door_hit", "arrow_cast", "arrow_hit", "fire_hit", "fire_cast", "lightning", "frost", "venom_hit", "gold") + tuple(f"death_{kind}" for kind in MONSTERS):
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


def test_an_arrow_has_a_short_dry_release_and_a_restrained_impact():
    """The opening tower sounds physical and leaves room for the fight's magic."""
    release = CUES["arrow_cast"].render(0)
    impact = CUES["arrow_hit"].render(0)
    fire = CUES["fire_hit"].render(0)
    assert 0.07 <= len(release) / SAMPLE_RATE <= 0.3
    assert 0.07 <= len(impact) / SAMPLE_RATE <= 0.3
    assert 0 < loudness(release) < loudness(fire)
    assert 0 < loudness(impact) < loudness(fire)


def test_the_wave_bell_rings_on(cache: Path):
    for stem in takes("wave"):
        assert len(sound(cache, stem)) / SAMPLE_RATE > 3.0


def test_stingers_last_three_to_six_seconds(cache: Path):
    for cue in ("victory", "defeat"):
        assert 3.0 <= len(sound(cache, cue)) / SAMPLE_RATE <= 6.0


# -- Preparing the cache -----------------------------------------------------------------------



def test_every_location_has_its_own_battle_track():
    from hellward.audio.music import BATTLE_FOR, track_for
    from hellward.sim.campaign import LOCATIONS

    assert set(BATTLE_FOR) == set(LOCATIONS)
    assert len(set(BATTLE_FOR.values())) == len(LOCATIONS), "every dungeon sounds different"
    for key in LOCATIONS:
        assert track_for(key) in PIECES
        assert PIECES[track_for(key)].seconds >= 300


@pytest.mark.parametrize("name", PIECES)
def test_music_is_a_clean_stereo_score(cache: Path, name: str):
    clip = read_wav(cache / "music" / f"{name}.wav")
    assert clip.ndim == 2 and clip.shape[1] == 2
    assert abs(len(clip) / SAMPLE_RATE - PIECES[name].seconds) < 1 / SAMPLE_RATE
    assert 0.1 < np.abs(clip).max() < 0.81
    if name != "title":
        assert np.abs(clip[0]).max() < 1e-3
        assert np.abs(clip[-1]).max() < 1e-3
        chapter = clip[30 * SAMPLE_RATE:40 * SAMPLE_RATE]
        later = clip[120 * SAMPLE_RATE:130 * SAMPLE_RATE]
        assert not np.array_equal(chapter, later), "the score must develop rather than repeat a passage"
        window = 20 * SAMPLE_RATE
        levels = [np.sqrt(np.mean(clip[i:i + window] ** 2)) for i in range(0, len(clip) - window, window)]
        assert max(levels) > 1.3 * min(levels), "the score must have a quiet and a strong section"
