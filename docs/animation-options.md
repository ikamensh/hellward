# Monster animation production choices

## What this pass exposed

The view already interpolates route position and chooses frames by distance travelled. The visible
vibration comes from image-space inconsistency: independently painted walk strips move the skull and
torso between adjacent poses, and some hit paintings change the apparent body scale. A shared cell
and foot pivot prevent the *sprite origin* from jumping, but cannot hold the anatomy inside the cell
steady. The eight-key cycle also makes every mismatch recur several times per second. A faster
playback clock would make the same mismatch more frequent. Fallen's front and back cycles still
hold four distinct paintings across eight walk slots, so this QA pass cannot make those views as
fluid as a genuinely sampled motion curve.

The existing procedural fallback is made from posed 3D meshes in `hellward/art/figures.py`, then
rasterized to the same eight-frame sprite interface. It proves that one body can serve every bearing,
but the current low-poly material and eight held samples do not match the painterly game art. The
`tools/rig3d_preview.py` experiment interpolates the Skeleton's existing pose controls at 60 fps
and turns its mesh continuously between bearings: the camera, ground origin, travel speed and
proportions are identical on both sides. This demonstrates structural continuity, not a finished
character or an in-game 3D renderer.

An eight-frame ImageGen revision of Fallen's front and back walks removed their duplicated frames
and passed cell registration and center-track checks. The 60 fps game render exposed alternating
head and torso texture and brightness on the new intermediate frames. Their upper-body pixel changes
were sometimes as large as the approved contact-to-contact change, even though only a limb should
have moved partway. We discarded that candidate. More frames only help when identity and surface
detail stay stable through the motion.

## Painted 2.5D pilot

The flat 3D blockout failed the visual target. Adding animation alone could not repair its silhouette,
anatomy, or materials. The new [painted rig pilot](painted-rigs.md) instead authors one detailed painted
body in eight views, splits each into overlapping jointed parts, and reuses those same surfaces in
continuous walks, impacts, strikes and deaths. Fallen, Skeleton and Zombie are implemented and can
be selected with `HELLWARD_MONSTER_STYLE=puppet`. The approved frame paintings remain the default
while the pilot is reviewed. New bind painting provenance, integration checks and reproduction
commands are recorded in the pilot document.

This is a useful near-term method with the pinned engine: it reduces changing anatomy and texture
between frames and permits different timing without repainting a strip. It still uses flat limbs and
view changes. A finished textured 3D character remains the stronger source for arbitrary yaw and
large limb rotations. The 3D quality measures should be explicit: match the painted silhouette first,
sculpt the skull/horns/shoulders/hands, unwrap and paint skin/bone/cloth separately, preserve contact
shadows and edges, then rig and author the character's gait and reactions. An unpainted blockout is
an inadequate preview of that production route.

A further 2.5D alternative is **weighted painted meshes**: joint weights bend a single painted
surface across an elbow or shoulder instead of rotating independent rigid pieces. This can hide
joint seams and add cloth or flesh follow-through, at the cost of mesh/weight authoring and a runtime
mesh renderer or offline baking. [Spine's weights documentation](https://en.esotericsoftware.com/spine-weights)
explains that model. A separate **3D-to-painted hybrid** would use a sculpted rig for positions,
handedness and occlusion, then paint stable UV textures or fixed projected views. It requires both
finished geometry and a disciplined texture pipeline; independently repainting every rendered frame
would recreate the original flicker.

## Choices

| Method | What it solves | New cost | Fit here |
| --- | --- | --- | --- |
| **Rigged 3D, rendered offline to sprites** | One model fixes identity, proportions, handedness, and bearing consistency. Curves can supply many walk, hit, and death samples. Saga2D keeps its current sprite renderer. | Model, UV/material, rig, animation, fixed-camera export tooling; many rendered cells and atlas memory. | Strongest route to fully spatial characters; finish art before judging animation. |
| **Runtime 3D characters over the 2D floor** | Smooth joint and yaw motion without baking every view; dynamic light and equipment variation. | A new skinned-mesh renderer, depth ordering, camera matching, shadows, lighting and performance work across backends. | Most flexible, highest engine risk. |
| **Layered 2D bone rig** | Continuous motion from fewer painted parts; small atlas and easy recolors. | Every part needs pivot and overlap rules. Diagonal views, occlusion, and a corpse breaking apart need separate art. | Current painted pilot; eight authored views make it viable, with planar deformation limits. |
| **Painted sprites with registration and sequence checks** | Keeps the current visual style and renderer; catches the present defects before merge. | Every bearing and action still needs hand correction; geometry remains independent from frame to frame. | Necessary immediately, but ongoing authoring remains expensive. |

Optical-flow interpolation is a small stopgap only. It invents pixels between incompatible shapes and
can smear the Skeleton's sword or the Fallen's blade. It cannot reveal a creature's hidden side.

The engine currently pins `saga2d==0.3.16` and uses Pyglet 2.1 for the game view. Pyglet's own 2.1
documentation calls its 3D model module an undocumented work in progress, so a runtime skinned-rig
plan should include a renderer spike before promising glTF animation playback. Blender's official
documentation supports armature animation and transparent render film, which makes an offline export
pipeline a more bounded first step.

## Recommended 3D pilot

The first comparison is now playable: Skeleton and Zombie have baked 3D sprite
sets alongside their paintings, with a stable mixed assignment per spawn. See
[the comparison and reproduction commands](rigged-monsters.md). Their current
meshes are structural motion studies; the textured, painterly treatment in the
pilot below remains the visual target.

1. **One finished Skeleton.** Make one textured mesh and an articulated rig with a fixed ground root.
   Keep shield and sword attached to their correct hands. Match the current painted Skeleton's
   silhouette, size and lighting at game zoom before animating. The present mesh is a motion blockout,
   not the art target.
2. **Author four actions once.** Looping walk with two true foot plants; hit recoil that returns to
   any walk phase; door strike; bone collapse with a distinct final corpse. Use joint curves and a
   simple foot constraint or animation contact markers to prevent skating.
3. **Render, then pack.** Lock an orthographic camera, light rig, color transform, model scale,
   transparent background, and the ground point. Render eight bearings from the same model and
   timeline at enough samples that a normal-speed loop reads smoothly (start with 24 walk samples,
   then judge 16/24/32 in game). Export a manifest with action, bearing, frame time, cell, and pivot.
   Keep all actions on one model; do not resize each render to its own silhouette.
   Budget the atlases before committing to the count: the Skeleton's 248×284 source-pixel cell
   consumes about 0.27 MiB of uncompressed RGBA; its current 152 cells are about 41 MiB before
   padding and mipmaps. More samples improve timing but quickly multiply texture memory.
4. **Adapt the image registry.** Let the existing `mon/<kind>/<bearing>/<action><frame>` lookup select
   the new atlas. The battle view still owns route direction, distance phase, and action priority.
   This avoids rewriting combat rules while testing the art direction. Profile atlas upload and memory
   before expanding to the full cast.
5. **Accept at battle scale.** Compare the same route, speed, hit and death in a real battle clip.
   Check foot contact, adjacent-frame body registration, hand identity, pivot, and atlas edges. A
   3D source removes random proportion drift; it does not automatically provide good timing, planted
   feet, a readable collapse, or painterly materials.

If that pilot matches the environment and removes the present defects at an acceptable authoring cost,
use it for the other humanoids. Fliers, spiders, and bosses should still have their own rigs and motion
language. Runtime 3D only becomes attractive if equipment changes, dynamic light interaction, or very
fine turning require flexibility that baked views cannot supply.

## Sprite method while evaluating the pilot

Run `uv run python tools/animation_qc.py` before accepting a painted strip. The audit compares the
head/torso track and body height against each matching procedural pose, then flags alternating walk
centers, jarring adjacent steps (including the 8-to-1 seam), and hits whose body scale differs from
the walk. A second raw painted-walk comparison catches guides that share a size mistake, and exact
duplicate neighboring walk frames receive a review finding. Generate the all-bearing 1× contact
sheets with `uv run python tools/animation_qc.py --contact-sheet /tmp/hellward-monster-qc`. The
procedural guide is a motion reference, not an anatomical truth: review findings need a human pass,
especially a deliberate lean or head recoil. A hard failure must be fixed or documented with a
specific visual reason before the atlas is merged. Also review a normal-speed rendered loop; an
isolated contact sheet cannot show vibration or a bad transition into and out of hit.

The fix workflow is to use one approved body and ground point as reference for a whole bearing/action
strip, preserve the original paint and hand props, correct the inconsistent cells, rerun the audit,
then capture the real renderer. Scaling an entire hit sprite to satisfy one numeric threshold can
shrink the head, hands, and weapon incorrectly. The final visual approval is a short loop at game
zoom, followed by one inspected 1:1 strip. For future intermediates, use a common rig or constrained
part deformation to preserve the approved head and torso texture while moving limbs around a planted
foot. Use ImageGen for newly exposed surfaces, then run the same 1× and moving-loop review.

## Sources

- [Blender manual: transparent render film](https://docs.blender.org/manual/en/4.5/render/eevee/render_settings/film.html)
- [Blender manual: actions](https://docs.blender.org/manual/en/4.5/animation/actions.html)
- [Pyglet 2.1 migration guide: model module status](https://docs.pyglet.org/en/latest/programming_guide/migration.html)
