# Why Godot 4

Hellward 3D had to answer two questions: how good can Hellward look in 3D, and which engine we would keep
building it in. Agents write all of this code and art, so "can an agent drive it end to end, and see its own
results" weighed as much as visual ceiling.

| | Godot 4.7 (chosen) | Unity 6 | Unreal 5 | Bevy | three.js | Panda3D / Ursina |
|---|---|---|---|---|---|---|
| Night-village look out of the box | volumetric fog, glow, SSAO/SSIL/SSR, GPU particles, decals | yes (HDRP/URP) | the best | partial | needs post stack | dated |
| Scenes and logic as text an agent edits | `.tscn` + GDScript, all text | YAML + C#, editor-centric | binary assets, Blueprints | Rust code only | JS code only | Python |
| Renders a frame from the command line | yes (offscreen SubViewport, `tools/shot.sh`) | batchmode, awkward | heavy | yes | via a browser | yes |
| Ships to Mac / Windows / Linux / web | one export each (web on the simpler renderer), MIT licence | licence terms, heavy | very heavy | yes | web only | Python packaging |
| Iteration time | seconds | minutes | minutes | compile times | seconds | seconds |

Godot 4 is the only option that is all of: a real game engine (animation, audio, UI, particles, input,
export), text all the way down, scriptable rendering for agent-side visual checks, and pretty enough. Unreal
looks better and is impossible for an agent to drive. Bevy and three.js need us to build the rest of the engine.
Panda3D would keep Python, but its renderer would cap the look below what this demo already reaches.

## The pipeline this demo proves

- **Models are Python.** Each model is a Blender script (`tools/blender/*.py`, Blender 5.2 in the background)
  exported to glTF: houses with real timber framing, rigged and animated monsters, towers with turning
  turrets. Changing a model is editing code and re-running it; the scripts are reviewable like any code.
- **Textures and effect sprites are Codex paintings** (`tools/paint.py`, the ChatGPT plan's image tool, no
  API credit), made seamless and turned into albedo/normal/roughness/height maps by `tools/pbr.py`.
- **Materials are named in Blender and dressed in Godot** (`game/scripts/mats.gd`), so one texture change
  restyles every model that uses it.
- **Sound and music come from the 2D game's own audio code** (`tools/export_audio.py`).
- **Every visual change is checked in a rendered frame.** Captures run offscreen (`scenes/capture.tscn`) through
  a shim that keeps Godot from ever taking the desktop (`tools/godot-capture.sh`), at full speed even with the
  screen locked: about 5 s for a 1080p shot, real time for a recording.

## Costs and open questions

- **The simulation.** The 2D game's rules and the leaders' planner (rollouts of a cloned world) live in Python
  and are compiled with mypyc. This demo runs a light GDScript port of the rules without the planner. A full
  3D Hellward has two honest options: port the simulation to GDScript/C# (the planner's rollouts would want
  C# or a GDExtension for speed), or keep the Python simulation as the authority and run Godot as its client
  over a local socket, the way saga2d's online play already separates rules from presentation. The second keeps
  every balance tool and test that exists today.
- **Art throughput.** A monster is a ~500-line Blender script; four took one agent about an hour, including
  rig and five animations. That scales to Hellward's cast, but bosses and fliers will want more care.
- **Saga2D.** Hellward 3D does not use the stack's engine. If the 3D direction is adopted, Hellward leaves
  saga2d; the other games are unaffected.
