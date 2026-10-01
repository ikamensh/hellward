"""Paint the demo's images with Codex's image tool (the ChatGPT plan, no API credit).

    python3 tools/paint.py                 # paint every image not yet painted, three at a time
    python3 tools/paint.py cobbles thatch  # repaint these
    python3 tools/paint.py --list

Raw paintings land in art/painted/<name>.png; tools/pbr.py turns the tileable ones into the game's
material maps. Codex picks the pixel size; the PBR step resizes.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "painted"
MODEL = "gpt-5.5"   # the configured default is refused on the ChatGPT account

TILE = ("A seamless tileable texture for a 3D game: viewed straight down, orthographic, filling the whole square "
        "frame edge to edge, with flat even diffuse light, no cast shadows, no highlights, no vignette, no border, "
        "no text. Fully opaque: the pattern runs off every edge of the frame, with no rounded corners and no transparent "
        "margin. The left edge must continue into the right edge and the top into the bottom. Realistic, "
        "high detail, dark-fantasy palette. Subject: ")

TEXTURES = {
    "cobbles": "a worn medieval cobblestone street: rounded dark grey granite setts of varied sizes laid in loose "
               "rows, packed dark earth and grit in the joints, a little moss, flecks of ash.",
    "earth": "trampled dark earth of a village lane at night: packed brown mud, small pebbles, scattered straw, "
             "a few dead grass tufts, ash.",
    "grass": "a dry, withered meadow: dense dark olive and brown grass blades, patches of dark soil, fallen leaves.",
    "plaster": "an old lime-plaster house wall: dirty off-white plaster stained by soot and damp, fine cracks, "
               "a few chips showing wattle beneath.",
    "timber": "dark weathered oak beam wood grain running vertically: deep cracks, almost black brown, worn.",
    "planks": "weathered wooden planks running vertically, grey-brown boards with gaps, knots, iron nails.",
    "thatch": "an old straw thatch roof: dense bundles of dark golden-grey straw running vertically, rotting and "
              "mossy in patches.",
    "stone": "a gothic masonry wall of rough grey limestone ashlar blocks in courses of varied lengths, thin mortar "
             "joints, weathered edges, moss and soot stains.",
    "slate": "dark blue-grey slate roof tiles in overlapping horizontal rows, rough edges, a little lichen.",
    "iron": "blackened wrought iron plate, hammered, with rust bloom, scratches and rivets.",
    "demon_skin": "leathery crimson demon hide: wrinkled deep red skin with darker veins, small bumps and scars.",
    "corpse_skin": "rotting corpse skin: grey-green and livid purple, bruised, with veins, sores and dried blood.",
    "bone": "old yellowed bone: smooth ivory surface with fine cracks, brown stains and pits.",
    "cloth": "tattered dark brown burlap cloth: coarse weave, frayed holes, dirt and blood stains.",
    "basalt": "polished black basalt carved with faint angular runes, a few fine cracks.",
    "flagstones": "large worn grey flagstones of a church square, irregular rectangles with dark joints and moss.",
}

SINGLE = {
    "stained_glass": ("A single gothic pointed-arch stained-glass window seen straight on, filling a tall frame: "
                      "deep red, gold and blue glass, black lead lines, a radiant sun at the top, a robed saint "
                      "below; lit from behind so the glass glows. Plain black outside the arch. No text.", "portrait"),
    "sky": ("An equirectangular 360-degree panorama of a night sky for a 3D game skybox, 2:1: a low smoky horizon "
            "glowing dull orange from burning villages far away, heavy dark clouds above with a pale moon "
            "breaking through, faint stars. The bottom quarter is dark hazy ground fog. Seamless left to right. "
            "No buildings, no text.", "landscape"),
    "banner": ("A long hanging cloth banner seen straight on, filling a tall frame: deep crimson velvet with a "
               "golden radiant sun sigil and a gold border, frayed lower edge. Plain black around it. No text.",
               "portrait"),
    # effect sprites: painted on pure black, which the game turns into transparency
    "fire_sheet": ("A 4 by 4 grid sprite sheet of sixteen separate realistic fire flames for a game particle "
                   "system, each flame alone in its own equal square cell, centred, upright, not touching the cell "
                   "edges: licking tongues of bright yellow-white core, orange body and deep red ragged tips, all "
                   "different shapes. Pure black background everywhere, no glow spilling between cells, no text, "
                   "no grid lines.", "square"),
    "smoke_sheet": ("A 4 by 4 grid sprite sheet of sixteen separate soft billowing smoke puffs for a game particle "
                    "system, each alone in its own equal square cell, centred, round-ish, not touching the cell "
                    "edges, light grey wispy smoke with soft edges and internal billows. Pure black background, "
                    "no text, no grid lines.", "square"),
    "rune_circle": ("A single glowing magic summoning circle seen straight from above, centred, filling the "
                    "square: thin concentric rings, angular demonic runes and a pentagram-like star, drawn in "
                    "bright violet-magenta glowing lines. Pure black background, nothing else, no text.", "square"),
    "portal_swirl": ("A single swirling vortex seen straight on, centred, filling the square: spiralling arms of "
                     "fire and molten red-orange energy twisting into a black-red centre, wisps and sparks. Pure "
                     "black outside the circle, no text.", "square"),
    "blood_decal": ("A single dark red blood splatter seen straight from above, centred: a main pool with "
                    "spatters and droplets around it. Pure black background, no text.", "square"),
    "scorch_decal": ("A single scorch mark seen straight from above, centred: soft round burnt blackened ground "
                     "with ash flecks and a few glowing orange embers, fading to the edges. Pure white background, "
                     "no text.", "square"),
}


def task(name: str) -> str:
    if name in TEXTURES:
        prompt, shape = TILE + TEXTURES[name], "square"
    else:
        prompt, shape = SINGLE[name]
    out = OUT / f"{name}.png"
    return (f"{prompt}\n\nUse the built-in image_gen tool in generate mode, {shape}, with the specification above, "
            f"then copy the generated PNG to {out} (it is saved under $CODEX_HOME/generated_images). Do not modify "
            f"anything else; finish by printing the path you copied from.")


def paint(name: str) -> str:
    out = OUT / f"{name}.png"
    out.unlink(missing_ok=True)
    result = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "-m", MODEL,
                             "-c", "model_reasoning_effort=low", "-C", str(OUT), "-"],
                            input=task(name), capture_output=True, text=True, timeout=900)
    if not out.exists():
        return f"FAILED {name}: {(result.stdout + result.stderr)[-600:]}"
    return f"painted {name}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()
    every = [*TEXTURES, *SINGLE]
    if args.list:
        print("\n".join(every))
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    unknown = set(args.names) - set(every)
    if unknown:
        parser.error(f"unknown: {sorted(unknown)}")
    names = args.names or [n for n in every if not (OUT / f"{n}.png").exists()]
    failed = 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(paint, names):
            print(line, flush=True)
            failed += line.startswith("FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
