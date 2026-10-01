# Hellward 3D — agent notes

A 3D take on [Hellward](../hellward/) (the 2D gothic tower defence) in **Godot 4.7**: one level (Tristram),
its first monsters and towers, built to see how far 3D can carry the game. Part of the Saga stack
(`../AGENTS.md`). Local only; no GitHub remote. Why Godot, and the open questions: [docs/engine.md](docs/engine.md).

## Commands

```bash
godot --path game                          # play (godot = /Applications/Godot.app/Contents/MacOS/Godot)
godot --path game -- demo film             # the scripted defence, filmed
tools/test.sh                              # headless integration tests (game/tests/run.gd), ~20 s
tools/shot.sh VIEW OUT.png [FRAMES] [args] # one 1080p frame of a named view (game/scripts/shots.gd)
tools/gallery.sh OUT.png V1,V2,.. FRAMES demo   # several views from one run, as a contact sheet
tools/record.sh OUT.mp4 FRAMES 1 demo film      # a video with its mixed soundtrack; OUT a dir: every Nth JPEG
tools/showcase.sh [OUT]                    # tests, beauty stills and the filmed demo into the evidence folder
tools/preview.sh MODEL OUT.png [anim=walk]      # contact sheet of one model under game lighting
tools/model.sh NAME...                     # build models: tools/blender/NAME.py in Blender -> game/assets/models/NAME.glb
uv run python tools/paint.py [NAME...]     # paint images with Codex (art/painted/)
uv run python tools/pbr.py [NAME...]       # painted tiles -> seamless albedo/normal/rough/height maps
uv run python tools/fxsprites.py           # painted effect/UI sprites -> game/assets/fx, game/assets/ui
HELLWARD_INTERPRETED=1 uv run --project ../hellward python tools/export_level.py tristram   # the 2D map -> game/data/
HELLWARD_INTERPRETED=1 uv run --project ../hellward python tools/export_audio.py           # cues and music -> game/assets/audio/
```

## Rendering without disturbing the person at the Mac

Never run the Godot binary to render. `tools/godot-capture.sh` runs it with a shim
(`tools/capture/noactivate.m`) that keeps the app from activating or showing a window, and the capture tools
run scenes inside `scenes/capture.tscn`, which renders into an offscreen SubViewport with the window's own
drawing disabled: macOS throttles a hidden or locked-screen window's drawables to one a second, an offscreen
viewport never asks for one. The wrapper re-imports when assets or scripts changed (a new `class_name` is unknown
until then and the scene fails to parse); captures quit on a watchdog if a scene hangs. `--headless` cannot
render on macOS (the dummy renderer only), but runs the tests.

## Layout

- `game/scripts/` — `main.gd` (wiring, mist, vignette; user args), `atmosphere.gd` (the night: sky, moon,
  fog, glow, grade; shared with the model previews), `level.gd` (the 2D grid in metres,
  routes, the floor mask and terrain), `dressing.gd` (the village, portal, cathedral, fires), `scatter.gd`
  (grass, stones, forest, dead wood), `world.gd` (the rules: waves, gold, lives, mana), `monster.gd`,
  `tower.gd`, `bolt.gd` (missiles), `vfx.gd` (battle effects), `fx.gd` (particles, firelight), `hud.gd`,
  `builder.gd` (input), `camera_rig.gd`, `intro.gd`, `demo.gd` (scripted defender and film director),
  `sfx.gd` (cues, music, the recording's sound log), `mats.gd` (the material library), `models.gd`.
- `game/shaders/` — ground, grass, overlay (hit/chill/curse/kind rim/x-ray), bar, orb, ring, vortex, beam
  (Cleanse), curse_beam, vignette, hud_panel/hud_bar/hud_banner.
- `tools/blender/` — one script per model; `lib.py` holds the contract, `monsters.py`, `towers.py`,
  `village.py`, `drystone.py` the shared kits.
- `game/assets/` — `models/` (built), `textures/` (PBR sets), `fx/` and `ui/` (keyed sprites), `audio/`.

## Conventions

- Metres; one map tile is 2 m. Models: Blender Z up, facing +Y (Godot -Z after export), origin on the ground
  at the footprint centre. Helpers and the full contract: `tools/blender/lib.py`.
- Materials are named, never textured, in Blender; `game/scripts/mats.gd` maps each name to its textured or
  glowing material when a model is loaded (`Mats.apply`).
- Look at every visual change in a rendered frame (`tools/shot.sh`, `tools/gallery.sh`).
- Untyped values (`args`, array elements) break GDScript's `:=` inference: give such variables a type.
- Tests drive the real scene: `push_input` events take window coordinates (`get_final_transform()`), and a
  test that ran no checks fails (a script error aborts a coroutine silently).
