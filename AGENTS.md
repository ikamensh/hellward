# Hellward — agent notes

A gothic tower defence on Saga2D in which demon leaders curse the player's towers, choosing their
curses by simulating the fight ahead. Part of the Saga stack (`~/saga/`, see `../AGENTS.md`).
Saga2D is a pinned PyPI release (source in `../saga2d`); `../sagaforge` is an editable path
dependency. `docs/design.md` is the game.

## Commands

```bash
uv sync --extra dev
uv run hellward                              # play
uv run pytest -q                             # the suite
uv run python tools/balance.py               # every leader policy against eight scripted defenders
uv run python tools/curse_quality.py         # how close the leaders' curses are to the best possible
uv run python tools/sampler.py DIR --music   # every sound cue back to back, and the music, to listen to
uv run python tools/pieces.py refresh        # regenerate changed foley pieces (Stable Audio 3, docs/audio.md)
```

## Layout

- `hellward/sim/` — the rules, with no saga2d: `content.py` (every table), `level.py` (the map,
  the path as one coordinate `s`, reach as intervals of `s`), `model.py` (the fixed-step `World`,
  cheap to clone), `planner.py` (the leaders' curse choice), `autoplay.py` (the scripted defender).
- `hellward/audio/` — `cues.py` (every cue by name, from the pieces in `assets/pieces/` and synth),
  `music.py` (the three loops), `bank.py` (`SoundBank`: cache, takes, voice budget, crossfades);
  `docs/audio.md`. Bump `bank.VERSION` after changing any sound.

## Rules

- `sim/` imports nothing from saga2d. The planner clones the world and steps the clone, so a step
  must stay deterministic, cheap, and must not read anything a clone does not copy.
- After a rules change run `tools/balance.py` and `tools/curse_quality.py`; quote the before and
  after numbers in the commit.
