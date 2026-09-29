# Monster animation

## Visual goal

The monster must read as the same creature while moving through a turn, taking a hit, and dying. At the game's normal zoom, the planted foot should stay near the route, the weapon should remain in the same hand, and a death should be recognizable from its silhouette before the blood or dust effect plays. Fallen, Skeleton, and Zombie are the first quality pass; the other monsters retain their existing assets until their clips are authored.

## Motion model

- **Eight travel bearings.** Sample the route on either side of the monster to get the direction it is actually travelling, including diagonals and the short interval around a bend. Select the nearest 45-degree facing. Draw left views independently: mirroring swaps the Fallen's blade and the Skeleton's sword and shield. Keep the last facing during a hit or death.
- **Distance drives footsteps.** Interpolate the monster's route position for every drawn frame, then advance its walk cycle by distance travelled. A slow or frozen monster does not run in place; a faster one does not slide through the same number of poses. Each kind has its own stride and pose rhythm. Frame selection and transient visual states live in the view, outside the deterministic simulation.
- **One-shot actions.** Death overrides hit, which overrides a door blow or chant, which overrides walking. A hit has a short, readable recoil and returns to the current walk phase. Repeated hits do not hold a monster in permanent recoil. A death starts at the creature's last foot point and facing, completes its own sequence, then removes the sprite. Pausing freezes the action clock; changing battle speed scales it with the fight.
- **Ground contact.** Every pose within a clip shares a ground pivot. The shadow remains under the feet while the body falls. Oversized poses need a deliberately sized cell or a separate death cell; remeasuring every frame independently would make the creature jump.

## Character direction

| Monster | Travel | Hit | Death |
| --- | --- | --- | --- |
| Fallen | Quick, low scamper: ears and blade lag the torso, feet alternate clearly. | Sharp recoil with the weapon pulled across the body. | Loses its footing, drops toward one side, and curls into a small heap. |
| Skeleton | Measured march led by the shield, with weight settling onto each straight leg. | Shield and skull jerk on different beats, exposing a loose rib cage. | Knees and spine fail, then skull, shield, and bones separate into a dry pile. |
| Zombie | Uneven drag and recovery, one leg trailing while the head and arms lag behind. | Heavy torso absorbs the blow before the head snaps back. | Buckles at the knees and pitches forward into a slow, weighty collapse. |

The existing impact particles and three distinct death sounds reinforce these motions. The body animation must still communicate the event when sound is off or several monsters die together.

The three-hit recoil lasts 0.21 s for each creature. Their five death poses have different weight: Fallen changes pose every 0.07 s and fades out by 0.65 s, Skeleton every 0.09 s and by 0.80 s, Zombie every 0.12 s and by 1.03 s. Fallen's light-body sound lands about 0.32 s into its death and Zombie's wet-body sound about 0.47 s in, close to the visible fall. The simulation continues to own damage and death; these timings only change the presentation.

## Asset production

1. Keep the posed Sagaforge meshes as deterministic motion guides and as a complete fallback. Render every desired bearing from the same rig and camera. Author the extra travel, hit, and death poses there first, so the sheet manifest can be checked before painting.
2. Repaint in short strips grouped by creature, bearing, and action. Use the existing painted creature as the identity and material reference. One enormous sheet would shrink each cell in the image model's output and invite hand swaps, changing proportions, and magenta background leakage.
3. Cut each strip against its guide, keeping one registration for the strip and the same explicit foot pivot across strips. Check the complete frame manifest, alpha edges, and feet. The cutter checks individual cells; a clean cut does **not** establish that adjacent poses match. The first pass had zero cutter flags even though Skeleton heads alternated horizontally and Zombie hits grew visibly.
4. Run `tools/animation_qc.py` on the **resolved installed frames**. It compares the painted head/torso track with the corresponding posed guide, including the walk8-to-walk1 seam, and compares each hit's central body extent with that bearing's walk. Hard errors reject alternating registration, abrupt extra motion, and substantial apparent growth. The raw painted walk-to-hit comparison catches a guide that happens to share the painter's scale mistake. Death-entry breadth and opaque mass changes are review findings: a collapse or raised arm can legitimately change the silhouette. Keep the skull diameter, costume, props, and ground point consistent; do not scale an isolated pose to quiet one metric. Review foot contact by eye because lifted legs make alpha-bottom measurements unreliable.
5. Inspect the real `tools/animation_preview.py` output at normal battle zoom and at 1:1 sprite resolution. The preview uses ordinary world steps, route interpolation, and each creature's real speed at 60 drawn frames per second. Review all eight ordered frames in every bearing, the walk8-to-walk1 seam, moving walk-to-hit-to-walk, and the complete death. Export the optional all-bearing `tools/animation_qc.py --contact-sheet DIR` grids for a static anatomy/size pass; the motion preview samples three hit bearings, so the grids cover the other five. Keep only the final useful contact sheet or clip in `~/saga/evidence/hellward/monster-animation-consistency/` with its source commit and reproduction command.

The painted source sheets are an art dependency, not an animation state machine. The view asks for stable names such as `mon/fallen/front_right/walk3` and `mon/zombie/back/death4`; the asset registry resolves those names to the approved painting or the authored guide. Changing the manifest for these three must leave every other painted monster valid.

### Installed sheets and reproducible painting

Each enhanced creature registers **152 named images**: eight bearings times eight walk positions, three door poses, three hits, and five death poses. The original `mon-<kind>` painting supplies the front/back/right contact poses and door attacks. The supplemental `mon-<kind>-bearings` sheet adds true diagonal and left-facing paintings. Skeleton and Zombie have eight individually painted steps in all eight bearings: the sheet contains the other five complete cycles plus intermediate poses for the three original directions. Fallen has eight individually painted steps in six bearings; its original front and back contacts are held for one intermediate slot each. This keeps those two cycles painterly while their ground movement still interpolates every drawn frame. `mon-<kind>-enhanced` supplies all 64 hit/death poses; `mon-<kind>-doors` supplies the 15 remaining door attacks, plus Fallen's corrected right-facing attack. Every registered image for the first three resolves to a painting; `HELLWARD_ART=procedural` remains a complete deterministic fallback for development. The common canvas and ground origin are fixed in `figures.ENHANCED_CELLS`.

Use the small-strip tool to revise art without repainting a giant atlas:

```bash
uv run python tools/monster_animation.py guide fallen impact /tmp/fallen-impact --facings front_right
# Edit /tmp/fallen-impact/mon-fallen-impact-input.png with the image model; inspect its result.
uv run python tools/monster_animation.py cut fallen impact /tmp/fallen-impact /path/to/rendered.png
# Inspect the transparent cut and its drift/edge report before installing it.
uv run python tools/monster_animation.py merge fallen impact /tmp/fallen-impact
```

The same commands accept `walk` (four contact poses), `walk-even` (four inbetweens), `walk-full` (all eight poses), and `door` (wind/strike/recover). For a new bearing, use `--facings`; `impact` and `walk-full` require it. Without it the other walk and door strips use the five supplemental bearings. Paint one eight-cell impact or complete walk strip per bearing, a twenty-cell contact sheet for five bearings, or a fifteen-cell door sheet. `merge` replaces only the supplied keys and retains the rest. For a complete eight-step revision, use `cut --register-to APPROVED_GUIDE_STEM` with an eight-cell guide assembled from approved walk paintings; the command validates its frame grid and ground pivot. For an impact revision, put approved walk poses in the first three cells of the edit target and keep the five approved death cells after them. Ask the painter for a brace, recoil, and recovery within the **walk's** body envelope, then restore the original death cells if they were not part of the edit. This makes body size a visible source constraint instead of relying on words alone. The global `tools/restyle.py refresh` intentionally leaves these three approved multipart sheets alone.

When every pose in an old death strip is uniformly oversized, resize the **entire** strip around its shared ground pivot only after comparing it with the approved walk and hit. Keep the five poses together and inspect the fall at 1:1 and battle scale. A single large hit frame needs a new painted pose: shrinking it alone changes the skull, weapon and stride relative to its neighbors.

Use this prompt as the edit template, adding the facing and the creature-specific motion from the table above: “Edit the attached magenta guide sprite sheet into finished dark gothic action-RPG sprites. Use the existing painted `mon-<kind>` sheet as the exact character, materials, lighting, weapon-hand and scale reference. Preserve the guide's grid, cell positions, ground point, poses and facing in every cell. For an impact strip, row one is hit1, hit2, hit3, death1; row two is death2 through death5. Keep the progression from recoil through a fully prone corpse, with no extra limbs or swapped weapon. Leave every pixel outside the figure pure flat #FF00FF; no floor, shadow, text, effects or added objects. Keep each figure entirely inside its cell.” The Fallen is a red imp with two horns and a curved blade in its right hand; Skeleton has a right-hand sword and left-arm round shield; Zombie has an uneven dragging leg and both arms reaching forward. The painting, guide manifest, and cutter registration are the reproducible source for each sheet.

## Verification and rollout

Use a BattleScene integration test to cover all eight bearings, progression tied to travel, hit priority and recovery, death completion, and exact asset registration. Run `tools/animation_qc.py` after each installed strip; resolve hard errors and inspect every review finding. The optional `--contact-sheet DIR` output shows every installed bearing and action at the game's 1× size for the visual anatomy pass. Use the real Pyglet renderer for motion: the mock backend verifies state but does not produce a useful screenshot. Capture the continuous 60 fps clip and ordered walk sheet from `tools/animation_preview.py`, then a normal Tristram/Graveyard battle frame to check the composition among towers, effects, and terrain. This pass changes presentation only, so balance and curse quality should be unchanged.

Expand to the remaining monsters by motion family, not by copying these three timelines: fliers need wing-driven lift and a falling crash, spiders need staggered leg groups, casters need distinct chant transitions, and large bosses need longer anticipation and more screen-space weight.

## Other approaches

| Approach | Benefit | Cost or visual risk |
| --- | --- | --- |
| Textured 3D rigs rendered offline to sprite sheets | Most consistent identity across every bearing; real depth, lighting, and limb overlap. | Requires model, texture, and animation authoring beyond the current low-poly kit. Strong long-term option. |
| Layered 2D cutout rigs drawn by Saga2D | Continuous joint motion with fewer images and cheap variation. | Perspective turns, cloth, and overlapping limbs can look flat; needs a new per-part pivot and draw-order system. |
| Optical-flow inbetweens from the present paintings | Quickly raises apparent frame rate without repainting whole walks. | Warped blades, ghosted limbs, and no new hidden-side information; suitable only as a temporary bridge. |
| Procedural 3D guides with richer geometry and lighting, without repainting | Deterministic, fast to extend across the cast, good for iteration. | Less painterly than the surrounding finished art until the renderer/materials are upgraded. |
| Sprite transforms, flash, and extra particles alone | Minimal asset work and immediate hit feedback. | Cannot supply true directional silhouettes or the character-specific deaths this pass calls for. |

The [production choices and 3D pilot](animation-options.md) compare these routes against the current engine. The offline rig test uses the same Skeleton mesh and camera on both sides to isolate the benefit of continuous joint motion; it is a motion prototype, not finished character art.
