# Painted monster rigs

## Measures and acceptance

| Measure | Implementation | Verification |
| --- | --- | --- |
| Painted character identity | Eight authored bind views for Fallen, Skeleton and Zombie; no changing paint inside an action | Review all bearings and the real battle comparison |
| Stable surfaces and proportions | Eleven overlapping parts per view, reused for walk, hit, strike and death | Fixed texture, shared depth interval and hit-size integration properties |
| Individual movement | Fallen's quick bouncing stride, Skeleton's restrained shield gait, Zombie's asymmetric shuffle | Continuous 60 fps renderer preview |
| Directional movement | Eight true views; same motion phase through turns, existing tangent smoothing and direction hysteresis | Route integration test and all-bearing preview |
| Impact and death | Recoil overlays the current gait; quick imp fall, scattered bones, slow heavy corpse collapse | Transition, pause, speed and cleanup integration tests |
| Readability | Painted material detail, ivory Skeleton bones, dark silhouette edges, existing shadows and lighting; attacking arms pass in front | Real battle at game zoom |
| Engine cost | Small trimmed part textures; continuous transforms in Saga2D's retained GPU sprite batch | Preview records update cost for 24 bodies / 264 parts |

The pilot is opt-in while being reviewed:

```sh
HELLWARD_MONSTER_STYLE=puppet uv run hellward
caffeinate -u uv run python tools/puppet_preview.py /tmp/hellward-puppet-review
caffeinate -u uv run python tools/puppet_preview.py /tmp/hellward-puppet-battle --battle
uv run pytest -q tests/test_painted_rigs.py tests/test_monster_animation.py tests/test_rigged_monsters.py
```

`puppet_preview.py` captures the real Pyglet renderer. The authoring view shows all eight bearings;
the battle comparison shows approved frame paintings beside the new rigs with the battle camera,
floor, shadow and darkness overlay. The preview must be watched at normal speed as well as checked
in a still. Quantitative properties catch drift and broken playback; they cannot approve the art.

## Authoring contract

`hellward/assets/puppet/*-bind.png` contains one standing painted body per view. The corresponding
`*-rig.json` declares cell crops, ground point, common height, joints, explicit ownership polygons,
back-to-front layer order, and hidden-part donors. The source scale is fixed per view and independent
of action. Texture extraction assigns remaining pixels to the nearest bone and overlaps joint edges.
Transparent noise below alpha 12 is discarded. Hidden limbs are copied only from explicit donors;
missing painted parts raise an error. This is preparation at load time, not runtime image generation.

`hellward/art/puppet.py` prepares bone-aligned trimmed textures and 64 periodic joint samples per view. Runtime interpolates
those samples and overlays impact/strike/death poses.
`hellward/ui/puppet.py` submits their transforms through the engine's public sprite API. Surface
textures never change during a walk or impact. Hidden Skeleton arms and legs are taken from explicit
painted front-view donors; Zombie arm masks and pivots are registered separately in each view. A death snapshots the last rendered pose; attacking
arms keep their layer order when death begins. The battle owns all clocks, including pause and speed. Every piece shares the middle of the root's
8px sorting interval: this prevents floating point cancellation from splitting a body between draw
groups at an exact boundary. A regression check reproduces that failure on an uncorrected body.

The design has limits: turns still select eight views, limbs are flat painted surfaces, and the gait
uses projected foot motion rather than a full 3D foot constraint. Large rotations can expose joint
seams or occlusion assumptions. True continuous yaw, changing equipment and correct dynamic light
would favor a finished 3D mesh. The current flat blockouts do not meet the painted art target.

## Image provenance

All three bind atlases were created with the built-in ImageGen tool from references assembled from
approved game paintings. The selected output files are saved in `hellward/assets/puppet/`; runtime
has no dependency on the generation service. Full turnaround specifications were:

- **Skeleton:** 4 by 2 sheet of the same Skeleton warrior in eight views; aged ivory bones, red waist
  rag, bronze round shield on anatomical left arm, narrow rusty sword on right, amber eye sockets.
  Full bodies, identical proportions; neutral standing pose, feet level, arms 20 degrees away from
  ribs, sword and shield outside hips. Sculptural skull, rib cage, pelvis and separate long bones.
  Elevated orthographic game camera, warm upper-left light, dark crevices, golden edges, detailed
  painted dark fantasy finish. Transparent background, no shadows, text, grid or action poses.
- **Fallen:** same layout and camera; short stocky imp, oversized horned head, pointed ears, muscular
  crimson skin, amber eyes, fanged grin, cloven hooves, leather skirt, wrist wraps. Crescent dagger
  in right hand and empty clawed left. Permanent modest hunch, arms hanging apart, feet level; no
  changing equipment, limb crossings, floor shadow, text or action poses. Detailed flesh and worn
  leather, dark crevices and restrained amber edge highlights.
- **Zombie:** same layout and camera; hulking hunched corpse, bald head sunk between shoulders,
  milky eyes, dead open mouth, gray-olive mottled skin, torn umber sleeveless tunic, muddy trousers,
  worn boots and long bare forearms with clawed hands. Lower right shoulder, arms hanging slightly
  forward and apart, softly bent knees, feet level. Same anatomy and outfit in every cell. Bruised
  olive skin, coarse cloth, dark crevices, warm upper-left key light, pale cool rim. Transparent,
  no floor shadow, equipment, text, gore or extra limbs.

Skeleton's accepted material edit used this final prompt:

> Use case: precise-object-edit. Edit target: eight-view painted skeleton bind-pose atlas. Change
> ONLY the bone material from dark golden bronze to bright pale aged ivory, warm off-white highlights
> and deep brown crevices. Skull, ribs and long bones must read clearly at small game size. Preserve
> bronze shield and rusty sword, red waist cloth, amber eyes. Keep every figure's exact pose, anatomy,
> proportions, silhouette, pixel placement, equipment and eight-view order, and exact 1448 by 1086
> canvas. Actual transparent background. No extra objects, no ground shadows, no labels.

The edit moved the painted figures despite its placement constraint. Each view's source joints,
regions, height and ground were registered to its edited bounding box before texture extraction;
this alignment is encoded in `skeleton-rig.json`, not inferred while playing.

API second-opinion review was attempted with Gemini 3.1 Pro and Claude Opus 4.8; both failed
because the local CLI could not authenticate. No external review conclusion is claimed.
