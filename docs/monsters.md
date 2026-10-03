# Monsters: the four hand-built kinds

The last four monster kinds have no generated sculpt (no GPU box): they are
hand-modelled from primitives in their `godot/tools/blender/mon_<kind>.py`
builders and walk on the imps' keyed cycle. The shared kit is
`godot/tools/blender/biped.py`: `Spec.hand` builds the mesh, paints it and
gives its joints (`h_ball`/`h_limb`/`h_cone`/`h_box`, `h_paint`, `h_join`),
`Spec.keyed` walks it (`monsters.imp_walk`/`imp_idle`) instead of a capture,
and its maps bake from the mesh itself (`hand_material`, `hand_detail`).
`Spec.families`/`looks` part the flat paints into materials. Concepts (painted
with `godot/tools/concept.py`'s Codex invocation) are in
`godot/art/concept/`; the pipeline they skip is `godot/docs/monsters.md`.

| kind | design | height | walk (m/s) |
|---|---|---|---|
| carver | ember-orange Fallen-tier imp, ivory horns, cleaver in its right fist (rigid to the hand) | 1.15 | 0.86 |
| devilkin | lean ash-violet tier, long swept black horns, bone-bead necklace, knife | 1.18 | 0.86 |
| dark_one | broad near-black tier, great curling horns, spiked collar, iron bracers, dark blade | 1.18 | 0.86 |
| abomination | hulking stitched brute, mismatched arms (left overgrown), shoulder spikes, glowing green wounds, bare slam fists | 2.1 | 0.92 |

The three tiers share one builder (`build_imp` in `mon_carver.py`); the
abomination has its own. Client tables (`HEIGHTS`, `RIM`, `WALK` in
`godot/game/scripts/monster.gd`) carry all four and `STAND_INS` is empty.

Build and check one:

```bash
cd godot && UV_NO_SYNC=1 sh tools/model.sh mon_carver
HW_NO_IMPORT=1 UV_NO_SYNC=1 sh tools/review.sh mon_carver /tmp/rev.png "anims=idle walk attack die die2"
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/blender/audit.py -- \
  game/assets/models/mon_carver.glb
python3 ../tools/assets.py   # 23 of 23, no problems
```
