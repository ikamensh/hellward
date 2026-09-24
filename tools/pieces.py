"""Generate Hellward's sound pieces with Stable Audio 3, and a file to listen to them.

    uv run python tools/pieces.py refresh              # generate what is missing or changed; manifest updated
    uv run python tools/pieces.py sampler DIR          # pieces.wav: every piece back to back, with a label list

Needs the Stable Audio 3 MLX runtime (``../sagaforge/docs/foley.md``): ``--runtime`` or
``$STABLE_AUDIO_MLX``, default ``~/stable-audio-3/optimized/mlx``.  The prompts below are the source
of truth; ``hellward/assets/pieces/manifest.json`` records what was generated.  A rejected piece
(silent, or a click) is named at the end: give it a new seed in ``RESEEDED`` and refresh again.
After a refresh bump ``VERSION`` in hellward/audio/bank.py so cached cues are mixed again, and run
the tests.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sagaforge.foley import BuildError, Piece, StableAudioMLX, build, sampler  # noqa: E402
from hellward.audio.pieces import ROOT  # noqa: E402

LICENSE = "Stability AI Community License: outputs are owned by the licensee and free to commercialise; training data licensed by Stability AI"
#: The room every piece is in; voices keep their breath, stages are one event each.
VOICE_STYLE = "dark gothic dungeon, close, dry, no music, no reverb"
STAGE_STYLE = "one short sound then silence, dark gothic dungeon, close, dry, no music, no reverb, no voice"
RUMBLE_STYLE = "dark gothic dungeon, close, dry, no music, no reverb, no voice"
BELL_STYLE = "old stone cathedral, close, no voice"

# Each entry: kind -> (shape, seconds requested, peak, one sentence per take).  The same prompt with
# several seeds gives near-identical takes, so every take has its own wording.

#: Dying voices, described as voices (the creature's name makes the model reach for a movie monster).
CRIES: dict[str, tuple[float, list[str]]] = {
    "fallen_cry": (2.0, ["a small impish creature with a high raspy voice squeals in pain and dies, a short shrill shriek cut off",
                         "a tiny wiry voice gives one sharp high-pitched squeal, then goes silent",
                         "a small creature's shrill chittering screech of pain, short"]),
    "zombie_cry": (2.0, ["a man with a rotten throat gives a long wet gurgling groan and falls silent",
                         "a slow deep wet moan with gurgling, a last breath through a ruined throat",
                         "a low hoarse wet groan, slow, fading out"]),
    "goatman_cry": (2.0, ["a large goat's angry bleating bellow, deep and distorted, then a gasp",
                          "a big man's roar breaking into a harsh bleating goat cry, short",
                          "a deep bestial bleat and snort of pain, cut off"]),
    "gargoyle_cry": (2.0, ["a harsh raspy bird-like screech, gravelly and grating, short",
                           "a hoarse screeching cry like stone scraping on stone, short",
                           "a shrill hawk-like shriek with a gritty rasp, cut off"]),
    "overlord_cry": (2.0, ["a huge creature with a very deep guttural voice roars in agony, a bellow that dies away",
                           "a giant brute with a deep growling voice bellows once and chokes",
                           "a massive deep roar of pain trailing into a low death rattle"]),
    "azazel_cry": (3.0, ["an enormous deep demonic roar, a colossal bellow of rage and pain slowly dying away",
                         "a gigantic creature's thunderous low roar breaking into a long dying growl"]),
    "shaman_cry": (2.0, ["a small old creature's cracked high voice shrieks and chokes, short",
                         "a shrill raspy cackle that breaks into a pained scream, short"]),
    "priest_cry": (2.0, ["a dry hissing exhale with a bony rattle, a hollow whispering death hiss",
                         "a raspy hollow hiss like wind through dry bones, fading"]),
    "witch_cry": (2.0, ["a woman's piercing anguished scream, short, cut off",
                        "a woman's shrill cackling scream breaking into a dying wail"]),
}

#: One event per piece: the body landing, the bones scattering, a door struck, a bolt landing.
STAGES: dict[str, tuple[str, float, float, str, list[str]]] = {
    # kind: (shape, seconds, peak, style, takes)
    "body_light": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a small light body drops onto a stone floor, one soft thud",
        "a small light body falls onto stone, one soft dull thud"]),
    "body_wet": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a heavy rotten body slaps wetly onto a stone floor, one wet thud",
        "a limp wet body collapses onto stone, a squelching thud"]),
    "body_medium": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a man-sized body falls onto a stone floor, one heavy thud",
        "a body in leather collapses onto flagstones, one dull thud"]),
    "body_heavy": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a very large heavy body crashes down onto a stone floor, one deep booming thud",
        "a huge brute slams onto flagstones, one deep heavy impact"]),
    "body_colossal": ("collapse", 3.0, 0.85, RUMBLE_STYLE, [
        "a gigantic body crashes onto a stone floor, a deep booming impact that shakes the ground and rumbles",
        "an enormous body falls onto a stone floor, one very deep heavy boom and a low rumble"]),
    "bones": ("collapse", 3.0, 0.8, RUMBLE_STYLE, [
        "a skeleton collapses into a pile of dry bones clattering onto a stone floor",
        "dry bones fall and clatter onto flagstones, rattling and settling",
        "a heap of brittle bones and a skull tumble down and scatter on stone"]),
    "stone_crumble": ("collapse", 3.0, 0.8, RUMBLE_STYLE, [
        "a stone statue crumbles, rocks and gravel falling onto a stone floor",
        "a stone figure breaks apart, chunks of rock clattering down and settling"]),
    "door_hit": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a heavy wooden club slams into a thick oak door with iron bands, one deep wooden thud with a rattle of iron",
        "heavy claws strike a thick wooden door once, one hard wooden bang",
        "a wooden ram hits a thick oak door a single time, one deep hollow boom",
        "a single heavy blow on an iron-banded wooden gate, one thud with an iron clank"]),
    "door_splinter": ("collapse", 3.0, 0.85, RUMBLE_STYLE, [
        "a heavy wooden door bursts apart, splintering planks and snapping iron bands crash down",
        "a thick oak door smashes into pieces, a loud splintering crash and falling wood"]),
    "door_hammer": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a hammer drives a nail into a thick wooden plank, one knock",
        "a mallet knocks a wooden beam into place, one solid wooden knock"]),
    "fire_whoosh": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a burst of fire whooshes past, a short fiery swoosh",
        "a flaming torch swung fast through the air, one whoosh of fire",
        "a ball of flame shoots out with a quick roaring whoosh"]),
    "fire_hit": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a small burst of flame hits and crackles, one short fiery impact",
        "a fire bolt strikes with a sizzling pop of flames",
        "a quick blast of fire flares up and fizzles, a short crackling hit"]),
    "fire_blast": ("collapse", 3.0, 0.85, RUMBLE_STYLE, [
        "a fireball explodes, a deep fiery boom with crackling flames",
        "a burst of fire erupts with a heavy whoomp and roaring flames dying down"]),
    "ice_shatter": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a sheet of ice shatters into sharp crystalline shards, one crash",
        "an icicle breaks and tinkles onto stone, a brittle crack",
        "glassy ice cracks and splinters, a sharp crackling shatter"]),
    "poison_splat": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a glob of thick slime splats wetly and hisses, one splat",
        "a glob of acid slaps onto stone with one wet splat and a brief sizzle",
        "a wet slimy splat on stone, one short squelch and a hiss"]),
    "coins": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a handful of gold coins drops onto a pile of coins, one jingling clatter",
        "a small pile of gold coins drops onto stone, one bright jingling clatter",
        "a few heavy gold coins land on a wooden table, one quick clinking jingle"]),
    "stone_grind": ("collapse", 3.0, 0.8, RUMBLE_STYLE, [
        "a heavy stone block grinds and scrapes across a stone floor",
        "a massive stone slab slides into place, a long low grinding scrape"]),
    "stone_thud": ("impact", 1.6, 0.8, STAGE_STYLE, [
        "a heavy stone block settles into place, one deep solid thud",
        "a stone pillar sets down on flagstones, a heavy dull knock"]),
    "bell": ("collapse", 3.0, 0.85, BELL_STYLE, [
        "a huge deep bronze bell tolls once, a low booming bong with a long ringing hum",
        "a large old church bell strikes once, a low deep toll"]),
    "door_debris": ("collapse", 3.0, 0.8, RUMBLE_STYLE, [
        "broken wooden planks and iron bands clatter down onto a stone floor and settle",
        "splintered boards and a bent iron hinge fall onto flagstones, a wooden clatter settling"]),
}

#: Seeds that produced a rejected piece, and the seed that replaced them.
RESEEDED: dict[str, int] = {}


def wanted() -> list[Piece]:
    out = []
    for k, (kind, (seconds, prompts)) in enumerate(CRIES.items()):
        for i, prompt in enumerate(prompts):
            name = f"{kind}_{i}"
            out.append(Piece(name, f"{prompt}, {VOICE_STYLE}", seconds=seconds, seed=RESEEDED.get(name, 1000 + 10 * k + i), shape="voice", peak=0.72))
    for k, (kind, (shape, seconds, peak, style, prompts)) in enumerate(STAGES.items()):
        for i, prompt in enumerate(prompts):
            name = f"{kind}_{i}"
            out.append(Piece(name, f"{prompt}, {style}", seconds=seconds, seed=RESEEDED.get(name, 4000 + 10 * k + i), shape=shape, peak=peak))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    refresh = commands.add_parser("refresh", help="generate missing or changed pieces")
    refresh.add_argument("--model", default="medium", choices=sorted(StableAudioMLX.MODELS))
    refresh.add_argument("--runtime", type=Path, default=Path(os.environ.get("STABLE_AUDIO_MLX", "~/stable-audio-3/optimized/mlx")))
    listen = commands.add_parser("sampler", help="write every piece back to back")
    listen.add_argument("out", type=Path, help="directory for pieces.wav and pieces.txt")
    args = parser.parse_args()
    if args.command == "refresh":
        try:
            manifest = build(wanted(), ROOT, StableAudioMLX(args.model, runtime=args.runtime), license=LICENSE)
        except BuildError as failure:
            sys.exit(f"{failure}\nEverything else is written; add the rejected names to RESEEDED with a fresh seed.")
        print(f"{len(manifest['pieces'])} pieces under {ROOT}; bump VERSION in hellward/audio/bank.py and run the tests")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        out = args.out / "pieces.wav"
        labels = sampler(ROOT, [p.name for p in wanted()], out)
        out.with_suffix(".txt").write_text("".join(f"{start:7.2f}s  {name}\n" for start, name in labels))
        print(f"{len(labels)} pieces, {labels[-1][0]:.0f} s: {out}")


if __name__ == "__main__":
    main()
