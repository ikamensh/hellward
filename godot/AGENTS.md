# Hellward's Godot client — agent notes

The client of [Hellward](../AGENTS.md): every screen, the 3D battle, sound and input, in **Godot 4.7**. The rules,
the leaders' minds, the campaign and the saves are the Python server's (`../hellward/server`), which `Net`
(`game/scripts/net.gd`) starts as a child process and talks to over loopback (`../docs/godot-client.md`).
Why Godot: [docs/engine.md](docs/engine.md).

## Commands

```bash
uv run hellward                            # (from the repo root) play: Godot runs game/, which starts the server
tools/test.sh [NAME]                       # headless tests against the real server (game/tests/run.gd), ~20 s
tools/shot.sh VIEW OUT.png [FRAMES] [args] # one 1080p battle frame of a named view (game/scripts/shots.gd)
tools/gallery.sh OUT.png V1,V2,.. FRAMES demo   # several views from one run, as a contact sheet
tools/record.sh OUT.mp4 FRAMES 1 demo film      # a video with its mixed soundtrack; OUT a dir: every Nth JPEG
tools/showcase.sh [OUT]                    # tests, beauty stills and the filmed demo into the evidence folder
tools/preview.sh MODEL OUT.png [anim=walk]      # contact sheet of one model under game lighting
tools/model.sh NAME...                     # build models: tools/blender/NAME.py in Blender -> game/assets/models/NAME.glb
uv run python tools/paint.py [NAME...]     # paint images with Codex (art/painted/)
uv run python tools/pbr.py [NAME...]       # painted tiles -> seamless albedo/normal/rough/height maps
uv run python tools/fxsprites.py           # painted effect/UI sprites -> game/assets/fx, game/assets/ui
```

Battle arguments (after `--`): `demo` watches a scripted player (`player=NAME`, `location=KEY`), `film` directs the
camera, `nointro` skips the opening. Screens: `screen=title|profiles|map|briefing|skills|forge|chronicle|story|
prologue|pause|reckoning|settings` (`location=KEY`, `act=N`) with `scene=res://scenes/game.tscn` in captures.
The server saves into `HELLWARD_DATA` (captures and tests make a scratch folder); `HELLWARD_SERVER` overrides the
server's command line.

## Rendering without disturbing the person at the Mac

Never run the Godot binary to render. `tools/godot-capture.sh` runs it with a shim
(`tools/capture/noactivate.m`) that keeps the app from activating or showing a window, and the capture tools
run scenes inside `scenes/capture.tscn`, which renders into an offscreen SubViewport with the window's own
drawing disabled: macOS throttles a hidden or locked-screen window's drawables to one a second, an offscreen
viewport never asks for one. The wrapper re-imports when assets or scripts changed (a new `class_name` is unknown
until then and the scene fails to parse); captures quit on a watchdog if a scene hangs. `--headless` cannot
render on macOS (the dummy renderer only), but runs the tests. Captures that run at the same time must set
`HW_NO_IMPORT=1`: two imports into the same cache at once break it.

## Frame time

Profile with `tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/main.tscn
shot=overview snap=/tmp/x.png frames=460 demo perf [off=omnishadow,grass,...]` (`scripts/capture.gd`): it prints
frame and render times; `off=` switches features off to bisect. On this M4 the battle runs ~19 ms at 1080p. What
cost the most: shadowed omni lights (each re-renders the scene six times; only the portal, the door's spot, the
forecourt braziers and burning props in the field cast shadows), and clutter casting into the moon's cascades.
3D renders at most a 1080p frame's pixels and FSR upscales it (`main.gd _fit_resolution`).

## Layout

- `game/scripts/` — `net.gd` (autoload `Net`: the server's process and the link), `game.gd` (`scenes/game.tscn`,
  the main scene: the ways between the screens), `screens/` (title, profiles, settings, map, briefing, skills,
  forge, story, prologue, pause, reckoning; `screen.gd` their base, `ui.gd` their kit), `prefs.gd` (this machine's
  settings), `main.gd` (`scenes/main.tscn`: one battle, mist, vignette; user args), `world.gd` (the battle as the
  server plays it: the clock in whole steps, events into the scene, orders), `monster.gd`, `tower.gd` (pictures of
  the server's monsters and towers; stand-ins for kinds without a model yet), `atmosphere.gd` (the night),
  `level.gd` (the server's grid in metres, routes, where a monster stands, the floor), `dressing.gd` (each
  location's scenery, gates), `scatter.gd`, `bolt.gd` (missiles), `chain.gd` (the Hook's chain), `vfx.gd`, `fx.gd`,
  `hud.gd` (the bar, the tower card, the monster plate), `builder.gd`
  (input into orders), `camera_rig.gd`, `intro.gd`, `demo.gd` (the film director for a watched defence),
  `sfx.gd` (cues, music, the recording's sound log), `mats.gd` (the material library), `models.gd`.
- `game/shaders/` — ground, grass, overlay (hit/chill/curse/hymn/kind rim/x-ray), bar, orb, ring, vortex, beam
  (holy light: Smite, the shrine), curse_beam, vignette, hud_panel/hud_bar/hud_banner.
- `tools/blender/` — one script per model; `lib.py` holds the contract, `monsters.py`, `towers.py`,
  `village.py`, `drystone.py` the shared kits.
- `game/assets/` — `models/` (built), `textures/` (PBR sets), `fx/` and `ui/` (keyed sprites), `audio/`.

## Conventions

- Metres; one map tile is 2 m. Models: Blender Z up, facing +Y (Godot -Z after export), origin on the ground
  at the footprint centre. Helpers and the full contract: `tools/blender/lib.py`.
- Materials are named, never textured, in Blender; `game/scripts/mats.gd` maps each name to its textured or
  glowing material when a model is loaded (`Mats.apply`).
- Look at every visual change in a rendered frame (`tools/shot.sh`, `tools/gallery.sh`, a screen with
  `scene=res://scenes/game.tscn screen=NAME snap=OUT.png`).
- The client computes no rule: what is built, what it costs, what a curse does and who wins come from the server.
  A guess for the eye (a ghost tower's colour, a build tile's mark) is fine; a guess that decides is not.
- Untyped values (`args`, array elements) break GDScript's `:=` inference: give such variables a type.
- Tests drive the real scene: `push_input` events take window coordinates (`get_final_transform()`), and a
  test that ran no checks fails (a script error aborts a coroutine silently).
