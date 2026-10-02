# Hellward — agent notes

A gothic tower defence in which demon leaders curse the player's towers, choosing their curses by simulating the
fight ahead. A **Godot 4.7 client** (`godot/`) over a **Python server** (`hellward/server`) that plays the rules,
the leaders' planner and the campaign. Part of the Saga stack (`~/saga/`, see `../AGENTS.md`); `../sagaforge` is
an editable path dependency (the audio code and the asset tools), nothing else from the stack is.
`docs/design.md` is one defence; `docs/campaign.md` the campaign around it; `docs/story.md` the story's cast and
rules; `docs/godot-client.md` who owns what between server and client, the protocol and its measured costs
([ADR 0002](docs/adr/0002-python-server-godot-client.md)); `godot/AGENTS.md` the client's own notes (rendering
without disturbing the person at the Mac, the asset pipeline, frame time).

## Commands

```bash
uv sync --extra dev
uv run hellward                              # play: the Godot client, which starts the server
uv run pytest -q                             # the suite (simulation, server, campaign through the real server)
godot/tools/test.sh                          # the client's headless tests against the real server
uv run python tools/protocol_bench.py        # the protocol's cost: frame sizes, encode time, round trips
uv run python tools/balance.py --location caves      # every leader policy against eight ordinary defenders
uv run python tools/curse_quality.py --location caves  # how close the leaders' curses are to the best possible
uv run python tools/campaign_balance.py --out DIR   # the campaign's tuning table (heavy: through ~/saga/tools/slot.py)
uv run python tools/margin.py veteran        # the tuning's yardstick: how much harder each location could be (slot.py)
uv run python tools/margin.py --replay ~/.hellward/replays/F.json   # the same for a logged person's defence
uv run python tools/sim_bench.py             # a defence per location, source against compiled: time and digests
uv run python tools/warden_plans.py search   # the warden's build for a location, searched on training seeds
uv run python tools/plan_player.py plan all   # search the planned player's builds (slot.py; after a rules change)
uv run python tools/export_audio.py --music  # render every cue and track into the client (godot/game/assets/audio)
uv run python tools/sampler.py DIR --music   # every sound cue back to back, and the music, to listen to
uv run python tools/pieces.py refresh        # regenerate changed foley pieces (Stable Audio 3, docs/audio.md)
uv run python tools/story.py paint           # paint the story's missing panels (Codex; refs first: story.py refs)
uv run python tools/intro.py STEP OUT        # the story intro as film and as comic (docs/intro.md)
```

## Layout

- `hellward/sim/` — the rules, with no I/O: `content.py` (monsters, towers, curses, spells),
  `campaign.py` (the two acts' locations with their maps, waves and arsenal; `ACTS`, `ACT_ENDS`; sigils),
  `skills.py` (the tree and the `Perks` it bakes into a defence), `level.py` (the map, the path as
  one coordinate `s`, reach as intervals of `s`), `model.py` (the fixed-step `World`, cheap to
  clone), `planner.py` (the leaders' curse choice), `players/` (scripted players, which act
  through `hands.py`: a person's view and reaction time; `veteran` is the tuning's yardstick, `corner` Ilya's
  opening, `ghost` a logged person's defence replayed, `spacing.py` the area-curse penalty they share).
- `hellward/server/` — `python -m hellward.server`, the client's child: `__main__.py` (connects to the client's
  loopback port, hello, activation), `service.py` (requests to answers), `protocol.py` (events, frames and the
  battle's start as JSON), `battle.py` (one defence: the client's clock in whole steps, orders and refusals, the
  replay log, scripted players), `campaign.py` (profiles, map, briefing, skills, forge, story schedule, results),
  `progress.py` and `saves.py` (the campaign's save, the 2D game's envelope), `thinking.py` (the planner's worker
  processes), `client.py` (a Python stand-in for the client: tests and the bench).
- `hellward/story.py` — every story page (its panel's picture, words and what the painter paints), the panel
  bible; panels in `godot/game/assets/story/`, painter references in `hellward/assets/story/refs/`.
- `hellward/fastsim.py`, `compiled.py` — the simulation compiled with mypyc for the server and the tools that play
  many defences (`build/fastsim/`); `sums.py` adds floats as source and compiled both do. `tests/test_fastsim.py`
  holds the compiled simulation to the source, event for event.
- `hellward/audio/` — `cues.py` (every cue by name, from the pieces in `assets/pieces/` and synth), `music.py`
  (the loops: title, one battle per location, boss); rendered into the client by `tools/export_audio.py`;
  `docs/audio.md`.
- `godot/` — the client (see `godot/AGENTS.md`): `game/scripts/` (`net.gd` the link, `game.gd` the screens' ways,
  `screens/` the campaign screens, `main.gd` a battle, `world.gd` the battle as the server plays it, `monster.gd`,
  `tower.gd`, `hud.gd`, `builder.gd` the player's orders), `tools/` (tests, captures, Blender models, painting).

## Rules

- The server is the authority: the client computes no rule (no damage, cost, range, unlock or outcome). It shows
  what the server says and sends orders; a refusal comes back with its reason. A protocol change lands on both
  sides in one commit; `hellward.server.PROTOCOL` and `Net.PROTOCOL` move together.
- `sim/` imports nothing but the standard library. The planner clones the world and steps the clone, so a step
  must stay deterministic, cheap, and must not read anything a clone does not copy.
- A scripted player sees only what a person sees (`players/hands.py`; `tests/test_players.py` checks
  the sources): never a leader's planner, cooldown or chant clock, never a clone of the live world.
- After a rules change run `tools/balance.py` and `tools/curse_quality.py`; quote the before and
  after numbers in the commit.
- The server and the tools run the simulation compiled (`HELLWARD_INTERPRETED=1` runs the source), which keeps it to
  mypyc's terms: `uv run mypy` stays clean, no simulation module calls the built-in `sum`, a `Final`
  constant is never rebound, and nothing reads `vars()` or `__dict__` of a simulation object. A new tool
  that plays many defences activates it before importing the simulation, as `tools/balance.py` does.
- Anything that starts the server or plays defences in a script needs an `if __name__ == "__main__":` guard: the
  planner's process pool spawns, and a spawned worker re-imports the main module.
- Look at every visual change in a rendered frame, rendered only through `godot/tools/godot-capture.sh` (see
  `godot/AGENTS.md`): never run the Godot binary to render.
- Never edit the simulation's sources (`hellward/sim/`) while a tuning or search run is going: its worker
  processes check the compiled build against the sources and stop.
