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
| `hellward/audio/music.py`, `instruments.py` | the three loops and their instruments |
| `hellward/audio/bank.py` | `SoundBank`: the cache, takes, pitch, the voice budget, music crossfades |
| `tools/sampler.py` | every cue back to back in one WAV, and the music, to listen to |

## The cues

A cue with several takes is written as `<cue>_<n>.wav`; the bank never plays the same take twice
in a row and varies the pitch of repeated cues by up to ±4 % (deaths ±3 %).

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

A death is Warband's pattern: the cry, faded over its last 0.15 s as the body lands 0.12–0.3 s
before the cry ends; the body take is rotated one step against the cry take so no two cues share
a whole fall. Long rumbles (bones, rubble) are cut to 1.4–1.8 s so a wave of gargoyles does not
drown the next one.

### Levels and the budget

Each cue is levelled by its loudest 50 ms (RMS): interface 0.06, actions 0.1, battle 0.12,
alerts 0.16, with a peak cap per class (battle 0.55, so four landing together stay under full
scale). The bank admits at most four `battle` cues in 0.12 s and eight in 0.5 s, and the same cue
not again within 0.08 s; tower sounds (casts, hits, door blows, gold) stop one voice short of
those limits, so the last voice of a burst is always free for a death. Interface cues, actions,
alerts, leaders, `door_break` and `death_azazel` always play. `x` is accepted by `play` but
saga2d does not pan effects, so it changes nothing yet. In a demo battle of 300 s the bank played
415 of 836 requests; deaths were almost never dropped.

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
uv run python tools/sampler.py /tmp/cues --music    # cues.wav + cues.txt, and title/battle/boss.wav
```

After a refresh, or any change to a cue or the music, bump `VERSION` in `hellward/audio/bank.py`
so every player's cache is rebuilt, and run `uv run pytest -q tests/test_audio.py`.

## The music

Composed in code (`music.py`) on instruments adapted from Warband's and a few of Hellward's own:
a detuned twelve-string (each course two plucks 7 cents apart, the low courses with an octave
string), a bowed drone that crossfades round the loop, far-off `oo` voices, an organ, a cast
church bell (hum, minor-third tierce, clang) and a heartbeat for a drum. Everything wraps round
the loop, the reverb too, so the loops are seamless.

| Track | Length | What plays |
|---|---|---|
| `title` | 45 s, 12 bars at 64 | D aeolian over a D–A drone: a lone twelve-string arpeggio, a slow falling melody on it, distant voices from bar 5, a bell at the top and two-thirds in, a heart under the second half |
| `battle` | 80 s, 24 bars at 72 | D phrygian: the heart on every half bar, the arpeggio quickening to sixteenths in the middle third with a frame drum, rattles and a low bow; monks and far voices; bells every eight bars |
| `boss` | 54.5 s, 20 bars at 88 | D phrygian over a D–E♭ drone: war drums and taiko, a low bow hammering the flat second, a sixteenth-note twelve-string, organ clusters, monks, a falling choir line, timpani and bells |

`SoundBank.prepare` renders the cues synchronously (about 2.5 s of CPU on an M-series Mac) and
composes the music in a background thread, title first (all three took 24 s here while other jobs
held the load average near 100); `bank.music(mood)` starts a track, crossfading 1.5–2.5 s, the moment it is
on disk. The cache is about 16 MB of cues and 30 MB of music under the game's asset path.

## Tests

`tests/test_audio.py` prepares a cache once and checks: the cue set is exactly the scene's list
plus a death per monster; every file is finite, non-silent, under full scale, 0.04–7 s long and
silent at both edges; interface cues sit under the fight; bigger monsters die lower (spectral
centroid) and a fireball carries more sub-100 Hz energy than any fire bolt; frost and lightning
ring brighter than fire; the bell rings on; stingers last 3–6 s; `prepare` is idempotent, restores
a missing file and discards the cache on a new `VERSION`; the budget holds, keeps the last voice
for a death, and a second of budget-admitted battle mixes under full scale; takes rotate and pitch
wanders within ±4 %; music starts, crossfades and waits for its track; each loop is stereo, the
right length, and its seam is no bigger a step than the other samples.
