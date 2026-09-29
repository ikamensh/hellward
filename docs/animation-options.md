# Monster animation production choices

## What this pass exposed

The view already interpolates route position and chooses frames by distance travelled. The visible
vibration comes from image-space inconsistency: independently painted walk strips move the skull and
torso between adjacent poses, and some hit paintings change the apparent body scale. A shared cell
and foot pivot prevent the *sprite origin* from jumping, but cannot hold the anatomy inside the cell
steady. The eight-key cycle also makes every mismatch recur several times per second. A faster
playback clock would make the same mismatch more frequent.

The existing procedural fallback is made from posed 3D meshes in `hellward/art/figures.py`, then
rasterized to the same eight-frame sprite interface. It proves that one body can serve every bearing,
but the current low-poly material and eight held samples do not match the painterly game art. The
`tools/rig3d_preview.py` experiment interpolates the Skeleton's existing pose controls at 60 fps
and turns its mesh continuously between bearings: the camera, ground origin, travel speed and
proportions are identical on both sides. This
demonstrates structural continuity, not a finished character or an in-game 3D renderer.

## Choices

| Method | What it solves | New cost | Fit here |
| --- | --- | --- | --- |
| **Rigged 3D, rendered offline to sprites** | One model fixes identity, proportions, handedness, and bearing consistency. Curves can supply many walk, hit, and death samples. Saga2D keeps its current sprite renderer. | Model, UV/material, rig, animation, fixed-camera export tooling; many rendered cells and atlas memory. | **Best next production experiment.** |
| **Runtime 3D characters over the 2D floor** | Smooth joint and yaw motion without baking every view; dynamic light and equipment variation. | A new skinned-mesh renderer, depth ordering, camera matching, shadows, lighting and performance work across backends. | Most flexible, highest engine risk. |
| **Layered 2D bone rig** | Continuous motion from fewer painted parts; small atlas and easy recolors. | Every part needs pivot and overlap rules. Diagonal views, occlusion, and a corpse breaking apart need separate art. | Good for mostly planar creatures, weaker for these eight-bearing humanoids. |
| **Painted sprites with registration and sequence checks** | Keeps the current visual style and renderer; catches the present defects before merge. | Every bearing and action still needs hand correction; geometry remains independent from frame to frame. | Necessary immediately, but ongoing authoring remains expensive. |

Optical-flow interpolation is a small stopgap only. It invents pixels between incompatible shapes and
can smear the Skeleton's sword or the Fallen's blade. It cannot reveal a creature's hidden side.

The engine currently pins `saga2d==0.3.15` and uses Pyglet 2.1 for the game view. Pyglet's own 2.1
documentation calls its 3D model module an undocumented work in progress, so a runtime skinned-rig
plan should include a renderer spike before promising glTF animation playback. Blender's official
documentation supports armature animation and transparent render film, which makes an offline export
pipeline a more bounded first step.

## Recommended 3D pilot

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
the walk. The procedural guide is a motion reference, not an anatomical truth: review findings need a
human pass, especially a deliberate lean or head recoil. A hard failure must be fixed or documented
with a specific visual reason before the atlas is merged. Also review a normal-speed rendered loop;
an isolated contact sheet cannot show vibration or a bad transition into and out of hit.

The fix workflow is to use one approved body and ground point as reference for a whole bearing/action
strip, preserve the original paint and hand props, correct the inconsistent cells, rerun the audit,
then capture the real renderer. Scaling an entire hit sprite to satisfy one numeric threshold can
shrink the head, hands, and weapon incorrectly. The final visual approval is a short loop at game
zoom, followed by one inspected 1:1 strip.

## Sources

- [Blender manual: transparent render film](https://docs.blender.org/manual/en/4.5/render/eevee/render_settings/film.html)
- [Blender manual: actions](https://docs.blender.org/manual/en/4.5/animation/actions.html)
- [Pyglet 2.1 migration guide: model module status](https://docs.pyglet.org/en/latest/programming_guide/migration.html)
