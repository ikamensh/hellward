# Monsters: quality levels

Goal (Ilya, 2026-10-01): the Fallen, Fallen Shaman, Skeleton and Zombie become AAA-quality 3D monsters, the best
we have, reached one level at a time. Fallen and Shaman keep the design of their 2D paintings, which Ilya likes;
Skeleton and Zombie get new designs (he found the old ones weak).

Each level is reached by all four monsters before work on the next starts. A level's checks are listed with it;
"looked at" means a rendered frame opened and judged, never assumed.

## L0 — stand-ins (where they started)

Bodies lofted from tubes and blobs along the bones in Blender scripts, the shared tiled skin textures, keyed
animations from pose functions. Readable from the battle camera, toy-like up close: visible primitive seams, no
anatomy, no unique texture.

## L1 — sculpted

A real model per monster, made from approved concept art.

- **Design:** a concept render per monster (`tools/concept.py`, `art/concept/`): Fallen and Shaman true to the 2D
  paintings, Skeleton and Zombie to their briefs. Looked at and approved before any mesh is made.
- **Mesh:** one generated sculpt per monster (image-to-3D): a single surface (no doubled shells), faces outward,
  no floating specks, limbs clear of the body. Budgets about 30k triangles for the imps and 40k for the Skeleton
  and Zombie (the generator's export target); weapons, staff and shield are separate rigid meshes.
- **Textures:** a unique UV atlas per monster with base colour, normal and ORM maps at 2048²; no lighting painted
  into the base colour; the normal map carries the sculpt's detail.
- **Rig:** the bones the animations already use (names kept: the client finds clips and `fx_` nodes by name), fitted
  to the new body; every clip (idle, walk, attack, hit, die, and cast for the Shaman) plays with no tearing, no
  collapsed joints, nothing more than 2 cm under the ground.
- **In game:** heights as before (`HEIGHTS` in the client), the overlay effects (hit flash, chill, kind rim, x-ray)
  still work, and a full wave keeps the battle's frame time (19 ms at 1080p on the M4) within 1 ms.

**Reached 2026-10-02** (hellward branch `monsters-aaa`). Fallen 29.3k triangles, Shaman 30.4k, Skeleton 40.7k,
Zombie 39.4k, each with 2048² albedo, normal, ORM (and emission for eyes); kukri, skull staff, sword and shield
generated the same way. Clips' lowest skinned point: −0.8 cm at worst (walks), −1.8 cm (deaths). Battle at 1080p
with a wave on screen: 18.2–18.6 ms with the old models, 18.6–18.8 ms with these. Client tests pass. The Zombie
and the Skeleton walk on captured motion (100STYLE Zombie and March), the imps on the old keyed walks.
Not yet seen by Ilya; concepts approved by the agent, not by him.

## L2 — production

- **Materials:** skin with subsurface scattering and varied roughness (the imps' oily hide, the Zombie's wet rot),
  bone with cavity darkening, rusted iron with a metal mask, eyes and embers emissive enough to bloom.
- **Secondary motion:** ears, loincloths, feathers, tabard, shroud and chain on their own bones, swinging after
  the body (follow-through), never rigid flaps.
- **Animation craft:** anticipation, overshoot and settle in attacks and hits; feet slide ≤ 1 cm a step while
  planted in the walk at its nominal speed; a weapon never passes through its owner; a corpse lies on the ground with no limb
  beneath it; loops are seamless.
- **Variation:** a pack never looks cloned: per-instance size (±6 %) and tint, phase-shifted cycles, at least two
  idles.
- **Readability:** from the battle camera at 1080p each kind is recognisable by silhouette alone, and none is lost
  against the night ground (checked on grey silhouettes and on real frames).
- **Cost:** imported with LODs; 60 monsters on screen keep the frame time budget.

**Status 2026-10-02:**
- Materials: met. Roughness by surface (oily imp hide 0.38-0.68 by occlusion, wet wounds 0.22, matte cloth 0.9,
  dry bone), occlusion darkens the base colour too, metal only where it is iron (masks per monster), emissive eyes
  and embers. Screen-space subsurface scattering was dropped for its cost (2 ms a full street); a backlight stands
  in for it.
- Secondary motion: met. Spring bones with gravity (ears, the Shaman's feather crest, loincloths, the Zombie's
  linen, the Skeleton's tabard and mail) lag, swing and settle by the end of a clip that returns to its start;
  they never go through the ground. Cloth bones move only their cloth (skin masks by colour and thickness).
- Animation craft: partly met. Planted feet slide (tools/blender/slide.py) a step: Fallen 0.8/1.0 cm, Shaman
  0.6/2.2, Zombie 1.6/1.9, Skeleton 0.9/2.3 — the swarm meets 1 cm, the rest are within 2.5 cm, invisible from the
  battle camera. Attacks wind up, strike and follow through; a hit is a spring layered over whatever clip plays
  (`game/scripts/flinch.gd`), so the walk goes on under it.
- Variation: met for what the client plays: each monster ±6% in size and one of three tints by its id, cycles out
  of step. (Only a pondering Shaman idles in battle, so a second idle would not be seen; dropped.)
- Readability: met. tools/lineup.sh at 48 m and as silhouettes: four distinct outlines.
- Cost: met. 7-10k triangles (props 1.5k), LODs on import. 60 on a street 15.6 ms against 13.0 with the 3.5-6k
  triangle stand-ins; the battle with a wave 18.5-18.8 ms against 18.2-18.6.

## L3 — AAA

- **Blind review:** close-up turntables and in-game frames judged by a panel of critics against named references
  (Diablo IV, Path of Exile 2 monsters), one lens each: anatomy and silhouette, surface and materials, animation,
  readability in play, style coherence with Tristram. Every lens scores 8/10 or better and none finds a blocking
  defect.
- **Deaths and impacts by kind:** the Skeleton collapses into a heap of bones, the Zombie falls with gore, the imps
  die with a spray of dark blood; hits read from the side they came from; fire, frost and lightning mark the body's
  material while they last.
- **Life in motion:** more than one variant of the frequent clips (walk, attack), looks toward what they are after
  (the Shaman at the tower it curses), hits layered over the walk without stopping it.
- **Close-up finish:** wet eyes, teeth and gums, nails and claws modelled; cloth with thickness; no texture stretch
  or seams visible on a turntable.

**Status 2026-10-02 (in progress):** rounds of the five-lens panel (`tools/review_set.sh DIR` renders the
pictures; each critic sees only them), scores per lens across the four kinds:

| round | anatomy | materials | animation | readability | style | what changed before it |
|---|---|---|---|---|---|---|
| 3 | 4-6 | 3-4 | 4-6 | 4-5 | 5-7 | material families, glowing eyes, the staff skull's violet |
| 4 | 4-6 | 4-5 | 4-6 | 5-7 | 4-7 | modelled crest, generated staff skull, squat Fallen, deaths open on the blow |
| 5 | 4-6 | 4-6 | 4-5 | 5-6 | 5-7 | Shaman a head taller, upright crown, overhead cast, pale Zombie |
| 6 | 5-6 | 4-6 | 3-5 | 4-7 | 5-7 | generated Zombie head, crimson that holds under the moon |

What the panel keeps asking for, beyond what is done: a wet/dry/metal surface language richer than one sheen
per body; walks with more character than captured or keyed cycles give at six samples; each kind told apart by
colour at the default camera, where monsters are 25-30 px tall. Blocking defects named in every round so far
were fixed in the next; the 8/10 bar is not met.

## Pipeline (as built)

1. `tools/concept.py`: concept renders (Codex image tool; the 2D paintings as references for Fallen and Shaman).
2. `tools/gen3d/trellis_gen.py` on a Scaleway L40S (Docker image with TRELLIS.2; ungated DINOv3 and BiRefNet
   mirrors; transformers 4.57): three seeds per concept, `sculpt.glb` (1M triangles) and `game.glb` (30-40k,
   2048² maps), exported without TRELLIS's remesh (it doubles every surface). The chosen seed is taken in by
   `tools/blender/intake.py` into `art/gen/<kind>/`.
3. `tools/blender/mon_<kind>.py` with `sculpted.py`: stand the body in the model contract, drop specks, turn
   inside-out parts outward, smooth the vertex normals, bake normals and occlusion from the sculpt, write the
   maps; joints read off `tools/blender/views.py` sheets and snapped to the limbs; voxel geodesic skin weights
   (`tools/skinweights.py`); the old pose library through `Rig.repose`; captured walks through `mocap.py`;
   props held by `sculpted.hold`; follow-through springs and a ground pass on deaths in `Rig.action`.
   Parts the generator gets wrong are modelled instead (`tools/blender/feathers.py`: the Shaman's crest, the
   Zombie's arrows) or generated alone and fitted (the Shaman's staff skull, `art/gen/skull`); a part to replace is
   cut off with `sculpted.trim`.
4. Godot: `Mats.monster` builds the ORM material for any `mon_*` name. Review with `tools/review.sh` (clips),
   `tools/lineup.sh` (side by side at battle distance, or as silhouettes), `tools/preview.sh`, and
   `tools/review_set.sh DIR` for the whole L3 picture set the critics read.
5. The GPU box and a TRELLIS run: `tools/gen3d/README.md`.
