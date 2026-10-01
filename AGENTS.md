# Hellward 3D — agent notes

A 3D take on [Hellward](../hellward/) (the 2D gothic tower defence) in **Godot 4.7**: one level (Tristram),
its first monsters and towers, built to see how far 3D can carry the game. Part of the Saga stack (`../AGENTS.md`).
Local only; no GitHub remote.

## Commands

```bash
godot --path game                         # play (godot = /Applications/Godot.app/Contents/MacOS/Godot)
godot --headless --path game --import     # import new or changed assets (after building models/textures)
tools/model.sh NAME...                    # build models: runs tools/blender/NAME.py in Blender -> game/assets/models/NAME.glb
tools/preview.sh NAME OUT.png [anim=walk] # contact sheet of a model under game lighting (turntable, or an animation)
uv run python tools/paint.py [NAME...]    # paint images with Codex (art/painted/)
uv run python tools/pbr.py [NAME...]      # painted tiles -> seamless albedo/normal/rough/height maps (game/assets/textures/)
HELLWARD_INTERPRETED=1 uv run --project ../hellward python tools/export_level.py tristram   # the 2D game's map -> game/data/
```

## Conventions

- Metres; one map tile is 2 m. Models: Blender Z up, facing +Y (Godot -Z after export), origin on the ground
  at the footprint centre. Helpers and the full contract: `tools/blender/lib.py`.
- Materials are named, never textured, in Blender; `game/scripts/mats.gd` maps each name to its textured or
  glowing material when a model is loaded (`Mats.apply`).
- Look at every visual change in a rendered frame (`tools/preview.sh`, or the game in Movie Maker mode:
  `godot --path game --write-movie OUT/f.png --fixed-fps 30 --quit-after N`). pyglet's rule applies here too:
  the display must be awake (`caffeinate -u`).
