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

WINGED = ("A single full-body flying creature seen from the front and slightly above, hovering with its wings spread "
          "wide and flat to both sides, legs hanging below, nothing in its hands or claws. ")

SHEET = ("exactly the creature in the attached reference, a sheet of small frames from a 2D game showing it from "
         "several directions and in several poses (use it only for its design: shapes, colours, costume)")

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
    "goatman": (FIGURE + "A Goatman, a demon warrior with the head of a ram and a muscular man's body, about 1.9 m "
                "tall, " + SHEET + ": shaggy brown fur on the legs, which are a goat's with dark cloven hooves, bare "
                "brown-skinned torso and arms, long curling ram's horns, a goat's snout and beard, small burning orange "
                "eyes, worn leather straps and a hide loincloth, iron bracers. Only the eyes glow.", "goatman_ref.png"),
    "overlord": (FIGURE + "An Overlord, a huge fat demon brute about 2.2 m tall, " + SHEET + ": rust-red wrinkled "
                 "hide, a massive gut, short thick legs, enormous shoulders and arms studded with bone spikes, a small "
                 "horned head sunk into its shoulders with tusks, iron bands on its wrists, a spiked iron collar, a "
                 "ragged loincloth. Small yellow eyes glow; nothing else glows.", "overlord_ref.png"),
    "azazel": (FIGURE.replace("arms held away from the body at about 35 degrees", "great bat-like wings spread wide "
               "behind it, arms held away from the body at about 35 degrees") + "Azazel the Flayer, a demon lord "
               "about 2.6 m tall, " + SHEET + ": dark crimson muscular body armoured in black chitin and bone plates, "
               "huge leathery red bat wings, a horned crown of curving black horns, a fanged skull-like face with "
               "burning orange eyes, clawed hands and clawed digitigrade feet, glowing lava-orange cracks in its "
               "armour. Only the eyes and the cracks glow.", "azazel_ref.png"),
    "priest": (FIGURE + "A Bone Acolyte, a gaunt undead priest about 1.85 m tall, " + SHEET + ": a hooded floor-length "
               "robe of dark brown wool with a dull red sash and tabard, a grey dead face with sunken cheeks under the "
               "hood, bony grey hands, a string of small bones and skulls round its neck. Small green eyes glow in the "
               "hood; nothing else glows.", "priest_ref.png"),
    "witch": (FIGURE + "A Blood Witch, a pale sorceress about 1.8 m tall, " + SHEET + ": a long tattered crimson gown "
              "with a black corset and a high collar, long straight black hair, ghost-pale skin, dark lips, long red "
              "nails, a necklace of blood-red stones. Her eyes glow faint red; nothing else glows.", "witch_ref.png"),
    "flayer": (FIGURE + "A Flayer, a tiny jungle demon-imp about 0.9 m tall, " + SHEET + ": lean wiry body with dark "
               "red-brown skin daubed with white and ochre paint, a big carved wooden tribal mask with a toothy grin "
               "over its face, a crest of red feathers sprouting from the mask, bone bracelets and anklets, a grass "
               "and hide loincloth, long thin arms and clawed feet. Small yellow eyes glow through the mask; nothing "
               "else glows.", "flayer_ref.png"),
    "zealot": (FIGURE + "A Zealot of Zakarum, a fanatical human cultist about 1.85 m tall, " + SHEET + ": a cream "
               "and dirty white robe belted with rope, a tall pointed cream hood-hat of the Zakarum order with a gold "
               "trim, a red cross-shaped sigil on the chest, bare scarred forearms, sandals, a crazed grey face. His "
               "eyes glow faint yellow; nothing else glows.", "zealot_ref.png"),
    "spider": ("A single giant spider about 1.6 m across its legs, seen from the front and slightly above, standing "
               "with all eight long legs spread wide and clearly apart from each other and from the body, " + SHEET +
               ": a glossy black-brown armoured body with a bulbous abdomen marked by a blood-red hourglass and red "
               "stripes, bristly jointed legs, a cluster of small red eyes, curved fangs. Only the eyes glow faintly. ",
               "spider_ref.png"),
    "bat": (WINGED + "A Blood Bat, a giant demonic bat with a wingspan of about 1.4 m, " + SHEET + ": dark crimson "
            "membrane wings with black finger bones, a furry blood-red body, a pig-snouted fanged face with big ears, "
            "small hooked feet. Its small eyes glow red; nothing else glows.", "bat_ref.png"),
    "gargoyle": (WINGED + "A Gargoyle, a stone demon about 1.7 m tall with a wingspan of about 2.4 m, " + SHEET + ": "
                 "weathered grey-green stone skin cracked and mossy, leathery stone bat wings, curling horns, a "
                 "snarling ape-like face, long arms with stone claws, crouched digitigrade legs. Its eyes glow pale "
                 "green; nothing else glows.", "gargoyle_ref.png"),
    "hulk": (FIGURE + "A Thorned Hulk, a hulking jungle brute about 2.2 m tall, " + SHEET + ": a massive hunched body "
             "of dark olive-brown bark-like hide, long thorns and spikes growing out of its back, shoulders and "
             "forearms, very long heavy arms, short thick legs, a small brutish head with a jutting jaw and small "
             "orange eyes. Only the eyes glow.", "hulk_ref.png"),
    "drowned": (FIGURE + "The Drowned, a bloated corpse risen from the harbour, about 1.9 m tall, " + SHEET + ": "
                "swollen blue-grey and sickly green waterlogged skin, barnacles and seaweed hanging from its arms and "
                "shoulders, the rotten remains of a sailor's coat and trousers, a slack jaw, pale bulging milky eyes, "
                "long webbed clawed hands. Nothing glows.", "drowned_ref.png"),
    "fetish": (FIGURE + "A Fetish Shaman, a tiny jungle demon about 1.0 m tall, " + SHEET + ": crimson-red skin, a huge "
               "carved bone-and-wood mask covering its head with a spray of red feathers fanning out above it, a "
               "necklace of shrunken heads and teeth, bone bracelets, a ragged grass skirt, thin arms and clawed feet. "
               "Small yellow eyes glow through the mask; nothing else glows.", "fetish_ref.png"),
    "inquisitor": (FIGURE + "A Zakarum Inquisitor, a tall stern priest about 2.0 m tall, " + SHEET + ": long white and "
                   "ivory vestments trimmed with gold embroidery, a crimson stole hanging down the front, a tall "
                   "pointed gold-trimmed mitre, a gold sun-and-cross pectoral, a gaunt cruel face, white gloves. His "
                   "eyes glow faint gold; nothing else glows.", "inquisitor_ref.png"),
    "bone_priest": (FIGURE + "The Bone Priest, an undead high priest about 2.5 m tall, " + SHEET + ": a towering dark "
                    "brown and black robe with heavy gold trim and a crimson underrobe, a tall spiked mitre of bone "
                    "and gold, a skull face with green fire in its sockets, skeletal hands, a mantle of small skulls "
                    "over its shoulders, chains and bone charms hanging from its belt. Only its eye sockets glow "
                    "green.", "bone_priest_ref.png"),
    "goat_axe": (PROP + "The Goatman's weapon: a crude long-hafted battle axe, a crescent iron blade nicked and "
                 "rusted on a dark wooden haft wrapped with leather, about as long as a man is tall. Standing "
                 "upright, blade at the top, the whole axe in frame.", None),
    "club": (PROP + "The Overlord's weapon: a huge spiked club of a gnarled tree root studded with iron spikes and "
             "bound with iron bands. Standing upright, the heavy end at the top, the whole club in frame.", None),
    "flame_sword": (PROP + "Azazel's weapon: a huge curved demonic greatsword of black iron with jagged teeth along its "
                    "edge and molten orange-glowing cracks running down the blade, a horned black crossguard, a grip "
                    "wrapped in red leather. Standing upright, point up, the whole sword in frame.", None),
    "green_staff": (PROP + "The Bone Acolyte's staff: a tall twisted dark wooden staff topped with a cage of bone "
                    "claws holding a glowing green orb, small bones and feathers tied below it. Standing upright, the "
                    "whole staff in frame.", None),
    "blood_staff": (PROP + "The Blood Witch's staff: a slender black wooden staff topped with a twisted iron crescent "
                    "holding a glowing blood-red crystal, red ribbons hanging below. Standing upright, the whole staff "
                    "in frame.", None),
    "spear": (PROP + "The Flayer's spear: a short crude spear, a leaf-shaped bone head lashed to a bamboo shaft with "
              "red cord, two red feathers hanging from it. Standing upright, point up, the whole spear in frame.", None),
    "mace": (PROP + "The Zealot's weapon: a heavy flanged iron mace with a worn leather-wrapped wooden handle and a "
             "small gold Zakarum cross set into its head. Standing upright, the head at the top, the whole mace in "
             "frame.", None),
    "crozier": (PROP + "The Inquisitor's crozier: a tall gold-plated staff topped with a sun-and-cross emblem of the "
                "Zakarum faith, a red banner tassel hanging from it. Standing upright, the whole crozier in frame.", None),
    "bone_staff": (PROP + "The Bone Priest's great staff: a very tall staff of fused human bones and spine vertebrae, "
                   "topped with a horned skull whose sockets burn with green fire, gold rings bound round it. Standing "
                   "upright, the whole staff in frame.", None),
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
