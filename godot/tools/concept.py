"""Paint the monsters' concept renders with Codex's image tool: the inputs image-to-3D turns into meshes.

    uv run python tools/concept.py                 # paint every concept not yet painted, three at a time
    uv run python tools/concept.py fallen skeleton # repaint these
    uv run python tools/concept.py --list

A concept is one full-body figure in an A-pose (arms clear of the body, legs apart, no weapon) on flat grey, lit
evenly: what a mesh generator reads best and a rig binds cleanly. Props (weapons, staff, shield) are painted
alone. Fallen and Shaman follow the 2D game's paintings (art/concept/ref/); Skeleton and Zombie are new designs.
Raw paintings land in art/concept/<name>.png.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "art" / "concept"
REF = OUT / "ref"
MODEL = "gpt-5.5"

LOOK = ("Rendered as a finished high-end 3D game character from a AAA action RPG (the quality of Diablo IV's "
        "monsters): sculpted anatomy with fine surface detail, physically based materials, realistic proportions "
        "for its kind. Soft, even, neutral studio light from the front, no coloured light, no rim light, no fog, "
        "no glow except where stated, no cast shadow, no ground. The whole figure in frame with a margin all round, "
        "centred, on a flat plain mid-grey background (#808080) everywhere: no dark backdrop, no halo, no vignette, no "
        "gradient. No text, no border, no other figures.")

FIGURE = ("A single full-body character, seen from the front and slightly to its left (a three-quarter front view, "
          "about 20 degrees), standing in a relaxed A-pose: arms held away from the body at about 35 degrees with "
          "elbows slightly bent and hands open, legs apart with a clear gap between them, empty hands, no weapon. ")

PROP = ("A single game prop alone, seen in a three-quarter view, filling most of the frame, nobody holding it. ")

CONCEPTS: dict[str, tuple[str, str | None]] = {
    "fallen": (FIGURE + "A Fallen, a small demon imp about 1.1 m tall, exactly the creature in the attached reference "
               "(front, side and back views from a 2D game): crimson-red wrinkled leathery hide with darker veins, a "
               "slight hunch, a big head with huge long pointed ears sticking out sideways, two short curved ivory "
               "horns, glowing yellow eyes, a wide snarling mouth full of small fangs, wiry muscular arms and legs, "
               "digitigrade legs ending in dark cloven hooves, clawed fingers. A ragged brown leather loincloth with "
               "a belt and iron buckle, crossed leather straps on the chest, worn leather wraps on the forearms. "
               "Only the eyes glow.", "fallen_ref.png"),
    "shaman": (FIGURE + "A Fallen Shaman, the imps' witch-doctor, about 1.3 m tall, exactly the creature in the "
               "attached reference (front, side and back views from a 2D game): the same crimson-red demon imp body "
               "with huge pointed ears, small horns, glowing yellow eyes and dark cloven hooves, wearing a tall fan "
               "headdress of long red and golden-yellow feathers rising high above its head, a necklace of small "
               "bones and teeth, white ritual paint stripes on its face and chest, a belt hung with little human "
               "skulls over a dark fur and hide skirt, leather arm wraps. Only the eyes glow. No staff.",
               "shaman_ref.png"),
    "skeleton": (FIGURE + "A Skeleton warrior risen from a crypt, about 1.85 m tall and gaunt: a complete human "
                 "skeleton of old yellowed cracked bone stained with grave dirt, ribcage open and empty, every bone "
                 "clearly shaped (skull, jaw, clavicles, ribs, pelvis, finger and toe bones). It wears the remnants "
                 "of a soldier's kit: a dented rusty iron spangenhelm with a nose guard, one rusted iron pauldron "
                 "on its left shoulder held by a rotten leather strap across the chest, a torn shirt of rusty "
                 "chainmail hanging only from the hips like a short skirt, and a tattered faded crimson tabard "
                 "strip hanging in front. Small orange embers glow deep inside the eye sockets; nothing else "
                 "glows. Empty hands.", None),
    "zombie": (FIGURE + "A Zombie, a hulking risen plague corpse about 1.9 m tall, heavy and stooped with a sagging "
               "belly: mottled grey-green rotting skin with livid purple bruises, dark veins and open sores, a torn "
               "flank showing a few ribs, a slack jaw hanging open with broken teeth, milky blind eyes, thin "
               "matted hair. It wears a filthy torn burial shroud of grey-brown linen draped over one shoulder and "
               "wrapped round its hips, a rusty iron manacle with a short broken chain on its right wrist, bare "
               "blackened feet. Two broken arrows stick out of its back and shoulder. Long heavy arms with "
               "blackened claw-like nails. Nothing glows.", None),
    "kukri": (PROP + "The Fallen's knife: a heavy curved kukri-like blade of dark pitted iron with a notched edge and "
              "a bright worn cutting edge, a short iron guard, a grip wrapped in old brown leather, an iron pommel. "
              "Laid out straight, blade pointing up and slightly to the right.", None),
    "skull_staff": (PROP + "The Fallen Shaman's staff: a gnarled dark wooden staff, as tall as a man, topped with a "
                    "small human skull lashed on with leather cords, red cloth ribbons and a few feathers hanging "
                    "below the skull, a bone fetish tied halfway down. Standing upright, the whole staff in frame.",
                    None),
    "skull": (PROP + "The skull on the Fallen Shaman's staff, alone: a human skull of old bleached bone, ivory "
              "white with grey-brown grime in its cracks and sutures, deep dark eye sockets, a broken nose "
              "cavity, a full row of worn upper teeth and the lower jaw still attached, slightly open. Seen from the "
              "front and a little to its left, so the sockets, cheekbones and the jaw's depth all show.", None),
    "zombie_head": (PROP + "The head of the Zombie, alone, cut off low on its thick neck (the neck stump included): "
                    "a risen plague corpse's face, puffy mottled grey-green rotting skin with livid purple bruises and "
                    "dark veins, sunken cheeks, milky white blind eyes, a slack jaw hanging open with broken yellow "
                    "teeth and black gums, thin dark matted hair hanging in strands over a balding scalp, one torn "
                    "ear. Seen from the front and a little to its left, so the face and the hanging jaw both show. "
                    "Nothing glows.", None),
    "sword": (PROP + "The Skeleton's sword: an old rusted arming sword, notched and pitted blade, a simple iron "
              "crossguard, grip of rotten leather, round iron pommel. Standing upright, point down, the whole sword "
              "in frame.", None),
    "shield": (PROP + "The Skeleton's shield: a round wooden shield about 70 cm across, dark oak planks split and "
               "gouged, a rusted iron rim and a domed iron boss, the faded remains of a painted crimson sun sigil. "
               "Seen from the front and slightly to the side, so its thickness shows.", None),
}


def task(name: str) -> tuple[str, Path | None]:
    prompt, ref = CONCEPTS[name]
    out = OUT / f"{name}.png"
    mode = "edit mode on the attached reference image, using it only as the design reference (make a new image)" \
        if ref else "generate mode"
    return (f"{prompt}\n\n{LOOK}\n\nUse the built-in image_gen tool in {mode}, portrait, with the specification "
            f"above, then copy the generated PNG to {out} (it is saved under $CODEX_HOME/generated_images). Do not "
            f"modify anything else; finish by printing the path you copied from.", REF / ref if ref else None)


def paint(name: str) -> str:
    out = OUT / f"{name}.png"
    out.unlink(missing_ok=True)
    prompt, ref = task(name)
    cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "-m", MODEL,
           "-c", "model_reasoning_effort=low", "-C", str(OUT)]
    if ref:
        cmd += ["-i", str(ref)]
    result = subprocess.run([*cmd, "-"], input=prompt, capture_output=True, text=True, timeout=900)
    if not out.exists():
        return f"FAILED {name}: {(result.stdout + result.stderr)[-600:]}"
    return f"painted {name}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("names", nargs="*")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()
    if args.list:
        print("\n".join(CONCEPTS))
        return 0
    unknown = set(args.names) - set(CONCEPTS)
    if unknown:
        parser.error(f"unknown: {sorted(unknown)}")
    OUT.mkdir(parents=True, exist_ok=True)
    names = args.names or [n for n in CONCEPTS if not (OUT / f"{n}.png").exists()]
    failed = 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(paint, names):
            print(line, flush=True)
            failed += line.startswith("FAILED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
