# Baked 3D monster comparison

Skeletons and Zombies can use either their painted sprites or a second set of
sprites rendered offline from the articulated 3D body in `hellward/art/figures.py`.
Both sets have eight authored bearings and the same fixed cell and ground pivot.
The 3D set samples an interpolated sixteen-frame walk from the existing eight
joint poses. It also includes each monster's hit, door strike, and distinct death
poses. No mesh is rendered while the battle runs.

The game defaults to **painted**. The 3D meshes are blockout geometry: they
validate articulation and directional playback, but their anatomy and materials
are visibly below the approved painted art. The **mixed** comparison is opt-in:
each Skeleton and Zombie spawn independently chooses a style from its kind and
monster ID. The choice is stable across replay, pause, hits, turning, and death,
and it never consumes the simulation's random stream. Other monster kinds keep
their existing art. Use these modes to compare:

```bash
uv run hellward                                   # painted (default)
HELLWARD_MONSTER_STYLE=mixed uv run hellward      # painted and baked 3D comparison
HELLWARD_MONSTER_STYLE=rigged uv run hellward     # baked 3D for Skeleton/Zombie
```

`HELLWARD_ART=procedural` still forces the old procedural fallback for all art.
It takes precedence over the comparison mode.

The source assets are `hellward/assets/rigged/mon-{skeleton,zombie}.png` and
their `.json` layouts. Rebuild them after changing these monsters' geometry,
poses, or the renderer:

```bash
python3 ~/saga/tools/slot.py -- uv run python tools/bake_rigged_monsters.py
python3 ~/saga/tools/slot.py -- caffeinate -u uv run python tools/rigged_mix_preview.py /tmp/hellward-rigged-mix
uv run pytest -q tests/test_rigged_monsters.py tests/test_monster_animation.py
```

The loader rejects missing or misregistered frames. The 3D bakes are a motion
and structure comparison. Their flat shaded materials and simple geometry are
visibly less finished than the painted art. A trial of painted material swatches
on these same mesh faces increased surface detail but did not repair the crude
silhouettes, so that trial was not installed.

For a production 3D replacement, build a real creature model for each monster:
sculpt the head, hands, torso and silhouette against the painted reference;
unwrap it; paint diffuse, roughness and emissive maps; rig the joints; animate
walk, hit, strike and death with planted foot contacts; then render every pose
through a fixed orthographic camera with consistent lights and a shared ground
pivot. Bake into the existing sprite-sheet contract so Saga2D needs no runtime
3D renderer. Review all eight bearings and transitions at battle scale before
switching the default. A textured blockout or independently repainted frames
are insufficient quality gates.
