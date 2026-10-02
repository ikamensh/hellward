# Hellward audio

The sound of a town under a cathedral: stone rooms, dry bones, a bell, and a slow twelve-string
over a drone. Physical sounds are generated recordings composed in code; tonal and magical ones
and all the music are synthesised. Nothing is downloaded at run time and nothing here has been
heard by Ilya yet: the descriptions below are what each sound is built to be, checked with
spectrograms and levels, not by ear.

## Where it lives

| File | What it holds |
|---|---|
| `hellward/assets/pieces/` | 71 generated pieces (mono, 16-bit, 44.1 kHz, 7.1 MB) and `manifest.json` with each prompt, seed and hash |
| `tools/pieces.py` | the pieces' prompts, seeds and style suffixes; `refresh` remakes what changed |
| `hellward/audio/cues.py` | every cue the scene plays, composed from pieces and `sagaforge.synth` |
| `hellward/audio/music.py`, `instruments.py` | six dungeon scores, the title and boss music, and their instruments |
| `tools/export_audio.py` | renders every cue's takes (WAV) and every track (MP3) into the client, `godot/game/assets/audio/` |
| `godot/game/scripts/sfx.gd` | the client's player: a random take, at most four voices of a cue, positional battle sounds, music buses |
| `tools/sampler.py` | every cue back to back in one WAV, and the music, to listen to |

## The cues

A cue with several takes is written as `<cue>_<n>.wav`; the client picks one at random and plays at most four voices
of a cue at once (`sfx.gd`), battle sounds placed in the world.

| Cue | Takes | Sound |
|---|---|---|
| `click` | 1 | a dry wooden tick with a dull glint |
| `refuse` | 1 | a muted low thunk, twice, the second lower |
| `build` | 2 | a stone block ground into place, then set down |
| `upgrade` | 1 | a rising D-major glass chime with a little sparkle, in a small room |
| `sell` | 2 | the tower unseated, a short grind, coins chinking into the purse |
| `door_build` | 2 | three mallet knocks on timber |
| `door_hit` | 4 | one blow on an iron-banded oak door (club, claws, ram), cut to the first blow |
| `door_break` | 2 | a last blow, the door bursting in splinters over a low thump, the wreck clattering down |
| `wave` | 2 | the cathedral bell tolling, the stone ringing on for four seconds |
| `cleared` | 1 | a short organ and choir chord landing on D major |
| `leak` | 1 | an ominous low gong that blooms, a far-off wail falling an octave under it |
| `gold` | 3 | a handful of gold coins |
| `cleanse` | 1 | holy light: a bright glass cluster in A major over a soft sung "ah", sparkling |
| `ponder` | 1 | a soft low breath through the teeth with a murmur under it |
| `chant` | 1 | 1.15 s: a low D–E♭–A♭ drone rising a major third, with whispered syllables over it |
| `curse` | 1 | a reversed swell sucking in for 0.2 s to a dark impact that rings a low minor second |
| `fizzle` | 1 | the drone sagging from 420 to 95 Hz and guttering out in sparks |
| `smite` | 3 | holy lightning from the vault: the thunder crack, a deep blow under it, a sung A-major chord blooming over it |
| `meteor_fall` | 1 | a roar swelling and dropping in pitch for the second before a meteor lands |
| `meteor` | 2 | the meteor landing: the blast, a ground-shaking boom, rubble falling after |
| `orb` | 3 | a frozen orb bursting: ice exploding outwards, a glassy ring of cold |
| `ward` | 1 | a ward closing round a tower: a held bright E-major chord and a rising shimmer |
| `broken` | 1 | a curse broken before it lands: a glassy crack and the chant collapsing |
| `fire_cast` | 3 | a fiery whoosh |
| `fire_hit` | 3 | a small burst of flame landing |
| `fireball` | 3 | the flame landing, a deep fiery blast on its heels and a sub-boom |
| `lightning` | 3 | a crack of static, a buzzing zap falling two octaves, crackle trailing off, a thump |
| `frost` | 3 | a burst of cold air, a glassy high shimmer spilling out, ice shattering in it |
| `venom_cast` | 3 | a wet spit and bubbles rising off it |
| `venom_hit` | 3 | a slimy splat and a short hiss |
| `victory` | 1 | 6 s: organ and voices climb D minor → B♭ → C → D major, bells and timpani on the arrival |
| `defeat` | 1 | 6 s: a bow falls D–C–B♭–A over low voices while a heartbeat slows and stops; one toll |
| `death_fallen` | 3 | a shrill imp squeal, a light body |
| `death_skeleton` | 3 | bones collapsing and scattering (no voice) |
| `death_zombie` | 3 | a wet gurgling groan, a wet body slap |
| `death_goatman` | 3 | a bestial bleating roar, a heavy body |
| `death_gargoyle` | 3 | a gritty stony screech, rubble crumbling |
| `death_overlord` | 3 | a huge guttural roar, a very heavy fall with a sub-thump |
| `death_azazel` | 2 | a colossal roar, an enormous fall that shakes the floor, a room around it |
| `death_shaman` | 2 | a cracked high shriek, a light body |
| `death_priest` | 2 | a dry bony rattle-hiss, bones collapsing |
| `death_witch` | 2 | a piercing scream, a body falling |

A death starts with a cry and a body impact, with the body take rotated one step against the cry
take so no two cues share a whole fall. Fallen and Zombie land early, while their painted collapse
is visible; their cries finish over the heap. Other voiced deaths land 0.12–0.3 s before the cry
ends. Long rumbles (bones, rubble) are cut to 1.4–1.8 s so a wave of gargoyles does not drown the
next one.

### Levels and the budget

Each cue is levelled by its loudest 50 ms (RMS): interface 0.06, actions 0.1, battle 0.12,
alerts 0.16, with a peak cap per class (battle 0.55, so four landing together stay under full
scale). (The 2D game's sound bank also held a battle budget; the Godot client keeps four voices per cue.)

## The pieces

Generated with Stable Audio 3 Medium through `sagaforge.foley` on this machine (MLX runtime at
`~/stable-audio-3/optimized/mlx`). Licence: Stability AI Community License — outputs are owned by
the licensee and free to commercialise; recorded in the manifest.

- **Voices** (`<monster>_cry_<n>`, shape `voice`, 2 s requested, 3 s for Azazel): one sentence
  per take, describing the voice rather than the creature ("a small impish creature with a high
  raspy voice squeals…", "a dry hissing exhale with a bony rattle…"), suffix "dark gothic
  dungeon, close, dry, no music, no reverb".
- **Stages** (`impact`, 1.6 s): bodies by weight (`body_light`, `body_wet`, `body_medium`,
  `body_heavy`), `door_hit`, `door_hammer`, `fire_whoosh`, `fire_hit`, `ice_shatter`,
  `poison_splat`, `coins`, `stone_thud`; suffix "one short sound then silence, dark gothic
  dungeon, close, dry, no music, no reverb, no voice".
- **Rumbles** (`collapse`, 3 s): `bones`, `stone_crumble`, `body_colossal`, `door_splinter`,
  `door_debris`, `fire_blast`, `stone_grind`, and the `bell` ("old stone cathedral, close, no
  voice").

First-round lessons: a "fist pounds on a door" gave three knocks, claws "raking" put the loud blow
0.7 s in, and a "rustle and thud" put the thud last; each was re-worded to "once", "a single
time", "one soft dull thud". One coin take was rejected as a click and re-seeded, then re-worded.

```bash
uv run python tools/pieces.py refresh               # generates what is missing or whose prompt/seed changed
uv run python tools/pieces.py sampler /tmp/pieces   # pieces.wav + pieces.txt, every piece back to back
uv run python tools/sampler.py /tmp/cues --music    # cues.wav + cues.txt, and one WAV per track
```

After a refresh, or any change to a cue or the music, render them into the client
(`uv run python tools/export_audio.py --music`) and run `uv run pytest -q tests/test_audio.py tests/test_client_assets.py`.

## The music

Composed in code (`music.py`) on instruments adapted from Warband's and a few of Hellward's own:
a detuned twelve-string (each course two plucks 7 cents apart, the low courses with an octave
string), a bowed drone, far-off `oo` voices, an organ, a cast church bell (hum, minor-third tierce,
clang) and a heartbeat for a drum. Each dungeon has a through-composed score of eight-bar
chapters with alternate harmonic routes and an arc from stillness to danger and back. Environmental
sounds sit inside the music: fire and wind in Tristram, wind and drops at the graves, drips in the
cathedral and catacombs, lava breaths in the caves, and low infernal air at the gate. Chapters
crossfade in the room; the complete score fades out and plays once. The title remains a loop.

| Track | Length | What plays |
|---|---|---|
| `title` | 45 s, 12 bars at 64 | D aeolian over a D–A drone: a lone twelve-string arpeggio, a slow falling melody on it, distant voices from bar 5, a bell at the top and two-thirds in, a heart under the second half |
| `battle_tristram` | 5:17 | D aeolian: a solitary twelve-string, the heart and a village lament as the fire grows |
| `battle_graveyard` | 5:02 | E dorian: wind, grave drops, a distant choral lament, organ and funeral bells |
| `battle_cathedral` | 5:23 | D phrygian: a torchlit procession, monks, frame drum and bells gathering strength in the nave |
| `battle_catacombs` | 5:00 | C phrygian: close dripping stone, a bowed flat second, organ and toms in the bone halls |
| `battle_caves` | 5:04 | F phrygian-dominant: lava breaths, racing guitar, a rising ember melody and war drums |
| `battle_hells_gate` | 5:15 | D phrygian: infernal air, a falling choir and the village melody returning in a darker form |
| `battle_docks` | ≈5 | G aeolian: a harbour swell, chimes over a hollow choir, a slow heart and frame drum |
| `battle_spider_forest` | ≈5 | A dorian: skittering twelve-string over rattles and toms, insects in the dark |
| `battle_jungle` | ≈5 | E phrygian: hunting drums (taiko, toms, a running frame drum), a cello and monks |
| `battle_drowned_city` | ≈5 | C# aeolian: sunk and slow, a hollow choir over organ, a lone heart, water dripping |
| `battle_travincal` | ≈5 | D# phrygian: the council's procession, monks and organ over war drums |
| `battle_temple` | ≈5 | B phrygian-dominant: the mother lamp's hall, choir and organ, the heart rising to the last fight |
| `boss` | about 4 min | Azazel's last wave: the gate's music driven harder, then emptied out at the end |

A location's intro already plays its battle track (`game.gd` `_open_intro`), so the briefing carries the
dungeon's feel before the first wave; a defence keeps it, and a boss's last wave breaks in with `boss`.
The client ships every track rendered (MP3) and crossfades between them (`Sfx.music`).

## Tests

`tests/test_audio.py` renders the cues and scores once and checks: the cue set is exactly the list
plus a death per monster; every file is finite, non-silent, under full scale, 0.04–7 s long and
silent at both edges; interface cues sit under the fight; bigger monsters die lower (spectral
centroid) and a fireball carries more sub-100 Hz energy than any fire bolt; frost and lightning
ring brighter than fire; the bell rings on; stingers last 3–6 s; each score is stereo, the right
length, ends cleanly, and has quiet and strong passages. `tests/test_client_assets.py` holds the client to
the set: it plays every cue, plays nothing that is not rendered, and every file is in its assets.
