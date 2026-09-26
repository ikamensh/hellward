# Hellward — agent notes

A gothic tower defence on Saga2D in which demon leaders curse the player's towers, choosing their
curses by simulating the fight ahead. Part of the Saga stack (`~/saga/`, see `../AGENTS.md`).
Saga2D is a pinned PyPI release (source in `../saga2d`); `../sagaforge` is an editable path
dependency. `docs/design.md` is one defence; `docs/campaign.md` is the campaign around it (six
locations, the skill tree, the spells, the world map, and how difficulty is tuned).

## Commands

```bash
uv sync --extra dev
uv run hellward                              # play
uv run pytest -q                             # the suite
uv run python tools/balance.py --location caves      # every leader policy against eight ordinary defenders
uv run python tools/curse_quality.py --location caves  # how close the leaders' curses are to the best possible
uv run python tools/campaign_balance.py --out DIR   # the campaign's tuning table (heavy: through ~/saga/tools/slot.py)
uv run python tools/sim_bench.py             # a defence per location, source against compiled: time and digests
uv run python tools/warden_plans.py search   # the warden's build for a location, searched on training seeds
uv run python tools/plan_player.py plan all   # search the planned player's builds (slot.py; after a rules change)
uv run python tools/sampler.py DIR --music   # every sound cue back to back, and the music, to listen to
uv run python tools/pieces.py refresh        # regenerate changed foley pieces (Stable Audio 3, docs/audio.md)
uv run python tools/restyle.py refresh DIR   # repaint the stand-ins (Codex; --provider openrouter), install the cut
uv run python tools/restyle.py ground DIR    # paint the floors not yet painted over their stand-ins; worldmap: the map
uv run python tools/showcase.py OUT          # a clip with its soundtrack through the real renderer (caffeinate -u)
uv run python tools/screens.py OUT           # PNG frames of every screen through the real renderer (caffeinate -u)
uv run python tools/intro.py STEP OUT        # the story intro as film and as comic (docs/intro.md)
```

## Layout

- `hellward/sim/` — the rules, with no saga2d: `content.py` (monsters, towers, curses, spells),
  `campaign.py` (the six locations with their maps, waves and arsenal; the difficulties; sigils),
  `skills.py` (the tree and the `Perks` it bakes into a defence), `level.py` (the map, the path as
  one coordinate `s`, reach as intervals of `s`), `model.py` (the fixed-step `World`, cheap to
  clone), `planner.py` (the leaders' curse choice), `players/` (scripted players, which act
  through `hands.py`: a person's view and reaction time).
- `hellward/sim/fastsim.py` — the simulation compiled with mypyc for the tools that play many defences
  (`build/fastsim/`); `sums.py` adds floats as source and compiled both do. `tests/test_fastsim.py` holds the
  compiled simulation to the source, event for event.
- `hellward/audio/` — `cues.py` (every cue by name, from the pieces in `assets/pieces/` and synth),
  `music.py` (the three loops), `bank.py` (`SoundBank`: cache, takes, voice budget, crossfades);
  `docs/audio.md`. Bump `bank.VERSION` after changing any sound.
- `hellward/art/` — `rig.py`, `figures.py`, `structures.py` (the posed low-poly stand-ins: monsters in
  three facings, towers in three ranks, gates, arches), `mapart.py` (each location's floor by its
  theme), `worldmap.py` (the world map and the places on it), `fx.py` (procedural glows, sigils,
  orbs, spell icons, the panel), `sprites.py` (registers everything: the painting in
  `assets/painted/` when its cells match, else the stand-in; `HELLWARD_ART=procedural` forces them).
- `hellward/ui/` — `flow.py` (the ways between the screens), `progress.py` (the saved campaign),
  `mapscreen.py`, `briefing.py` (a location's intro), `skilltree.py`, `battle.py` (the defence:
  fixed-step clock, input, spells, event routing), `view.py` (sprites kept in step with the rules),
  `effects.py` (bolts, lightning, novas, curses, spells, the leaders' thoughts), `lighting.py` (the
  darkness overlay), `hud.py` (panel, orbs, spell bar, chronicle, banners), `thinking.py` (the
  planner's worker process), `title.py` (title and reckoning), `menus.py`, `widgets.py`, `style.py`.

## Rules

- `sim/` imports nothing from saga2d. The planner clones the world and steps the clone, so a step
  must stay deterministic, cheap, and must not read anything a clone does not copy.
- A scripted player sees only what a person sees (`players/hands.py`; `tests/test_players.py` checks
  the sources): never a leader's planner, cooldown or chant clock, never a clone of the live world.
- After a rules change run `tools/balance.py` and `tools/curse_quality.py`; quote the before and
  after numbers in the commit.
- The tools run the simulation compiled (`HELLWARD_INTERPRETED=1` runs the source), which keeps it to
  mypyc's terms: `uv run mypy` stays clean, no simulation module calls the built-in `sum`, a `Final`
  constant is never rebound, and nothing reads `vars()` or `__dict__` of a simulation object. A new tool
  that plays many defences activates it before importing the simulation, as `tools/balance.py` does.
- Anything that builds the game in a script needs an `if __name__ == "__main__":` guard: the planner's
  and the stand-ins' process pools spawn, and a spawned worker re-imports the main module.
- A new frame, facing or monster makes its painted sheet stale (the game warns and draws the stand-in):
  repaint it with `tools/restyle.py`. Look at every visual change in a real frame (`tools/showcase.py`).
