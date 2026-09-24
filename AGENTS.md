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
uv run python tools/restyle.py refresh DIR   # repaint the stand-ins (Codex; --provider openrouter), install the cut
uv run python tools/showcase.py OUT          # a clip with its soundtrack through the real renderer (caffeinate -u)
```

## Layout

- `hellward/sim/` — the rules, with no saga2d: `content.py` (every table), `level.py` (the map,
  the path as one coordinate `s`, reach as intervals of `s`), `model.py` (the fixed-step `World`,
  cheap to clone), `planner.py` (the leaders' curse choice), `autoplay.py` (the scripted defender).
- `hellward/audio/` — `cues.py` (every cue by name, from the pieces in `assets/pieces/` and synth),
  `music.py` (the three loops), `bank.py` (`SoundBank`: cache, takes, voice budget, crossfades);
  `docs/audio.md`. Bump `bank.VERSION` after changing any sound.
- `hellward/art/` — `rig.py`, `figures.py`, `structures.py` (the posed low-poly stand-ins: monsters in
  three facings, towers in three ranks, gates, arches), `mapart.py` (the floor), `fx.py` (procedural
  glows, sigils, orbs, the panel), `sprites.py` (registers everything: the painting in
  `assets/painted/` when its cells match, else the stand-in; `HELLWARD_ART=procedural` forces them).
- `hellward/ui/` — `battle.py` (the scene: fixed-step clock, input, event routing), `view.py` (sprites
  kept in step with the rules), `effects.py` (bolts, lightning, novas, curses, the leaders' thoughts),
  `lighting.py` (the darkness overlay), `hud.py` (panel, orbs, chronicle, banners), `thinking.py` (the
  planner's worker process), `title.py`, `style.py`.

## Rules

- `sim/` imports nothing from saga2d. The planner clones the world and steps the clone, so a step
  must stay deterministic, cheap, and must not read anything a clone does not copy.
- After a rules change run `tools/balance.py` and `tools/curse_quality.py`; quote the before and
  after numbers in the commit.
- Anything that builds the game in a script needs an `if __name__ == "__main__":` guard: the planner's
  and the stand-ins' process pools spawn, and a spawned worker re-imports the main module.
- A new frame, facing or monster makes its painted sheet stale (the game warns and draws the stand-in):
  repaint it with `tools/restyle.py`. Look at every visual change in a real frame (`tools/showcase.py`).
