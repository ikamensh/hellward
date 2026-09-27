"""Repaint Hellward's stand-ins with an image model (see ``sagaforge.restyle`` and its guide).

    uv run python tools/restyle.py refresh DIR                    # every subject: dump, render (Codex), cut, preview
    uv run python tools/restyle.py --subjects mon-skeleton,towers refresh DIR
    uv run python tools/restyle.py dump DIR | render DIR | cut DIR [--force] | preview DIR
    uv run python tools/restyle.py ground DIR                     # every location's floor, painted over its stand-in
    uv run python tools/restyle.py --locations caves ground DIR   # one location's floor (a painted one is kept)
    uv run python tools/restyle.py worldmap DIR                   # the world map, painted over its stand-in
    uv run python tools/restyle.py keyart DIR                     # the title screen's painting, from words alone

Subjects: ``mon-<kind>`` (a row per facing, the frames across; Azazel is painted one facing per sheet so the
boss keeps its detail), ``towers`` (a row per rank, a column per kind) and ``gates`` (intact, damaged, broken).
Cut sheets are installed into ``hellward/assets/painted``; the game prefers them to the stand-ins.
Each sheet is padded with the key colour to 3:2, the shape Codex's image tool returns.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from sagaforge import restyle  # noqa: E402

from hellward.art import figures, mapart, structures, worldmap  # noqa: E402
from hellward.art.rig import DENSITY  # noqa: E402
from hellward.art.sprites import PAINTED, monster_sheet  # noqa: E402
from hellward.sim.content import MONSTERS  # noqa: E402
from hellward.sim.campaign import LOCATIONS  # noqa: E402

STYLE = ("Style: dark gothic action-RPG sprite art in the manner of the late-1990s pre-rendered classics of the genre: painterly, "
         "gritty and richly detailed, hard rim light from the upper left, deep shadows, muted earthen and bone colours with small "
         "saturated accents (glowing eyes, embers, magic). The camera looks down steeply from the front, three-quarter view. The sprites "
         "are shown at about half this size over a dark stone floor, so keep silhouettes bold and readable.")

MONSTER_SUBJECTS = {
    "fallen": "a Fallen: a small hunched red-skinned imp demon with long pointed ears, two small horns, a short snout and glowing "
              "yellow eyes, in a ragged brown loincloth, holding a short curved blade in its right hand",
    "shaman": "a Fallen Shaman: a small hunched crimson imp with a crest of gold and red feathers, long pointed ears and glowing "
              "yellow eyes, carrying a wooden staff topped with a small skull",
    "skeleton": "a Skeleton warrior: yellowed bones, a grinning skull with faint red eye-points, a rusty straight sword in its right "
                "hand and a round wooden shield with an iron boss on its left arm",
    "zombie": "a Zombie: a hunched rotting grey-green corpse in torn brown rags, slack jaw and pale glowing eyes, both arms reaching "
              "forward with clawed hands",
    "goatman": "a Goatman: a tall horned demon with a goat's head, dark swept-back horns, brown fur, glowing orange eyes and a short "
               "beard, wielding a long polearm with a broad blade",
    "gargoyle": "a Gargoyle: a crouched grey stone demon with dark leathery bat wings, short horns, glowing teal eyes and white claws, "
                "flying above the ground",
    "overlord": "an Overlord: a huge fat red-brown demon with a massive belly, a small horned head with tusks and glowing yellow eyes, "
                "swinging a spiked wooden club",
    "azazel": "Azazel the Flayer, the demon lord: a towering demon in black spiked armour over crimson hide, great curved ram horns, "
              "huge dark red bat wings, blazing orange eyes and a molten rune glowing on the chest, wielding a flaming greatsword",
    "priest": "a Bone Acolyte: a skeletal priest in a hooded, tattered ash-brown robe with a crimson stole, bareheaded, "
              "carrying a plain bone staff",
    "witch": "a Blood Witch: a slender sorceress with pale skin, long black hair and two small dark horns, in a long crimson gown with "
             "a high dark collar and a gold clasp, carrying a black staff topped with a red crystal",
    "flayer": "a Flayer: a tiny knee-high jungle fiend, hunched with bony limbs, a bone mask with a feather crest, glowing orange eyes, "
              "holding a short bone-tipped spear",
    "zealot": "a Zealot: a tall human fanatic in white-and-gold robes with a tall mitre-like hood, glowing brown eyes, "
              "swinging a long flail with a spiked head",
    "spider": "a Spider: a big eight-legged spider, low and wide, dark body with a red hourglass marking, legs moving in walk frames, "
              "mandibles clicking",
    "bat": "a Blood Bat: a small flying bat with wings spread, crimson body, glowing red eyes, pointed ears, "
           "hovering at gargoyle height",
    "hulk": "a Thorned Hulk: a huge broad brute of dark bark and thorns, long arms knuckle-walking, small head with glowing amber eyes, "
            "thorns sprouting from back and shoulders",
    "drowned": "a Drowned: a bloated pale blue-green corpse with weed hanging from its limbs, slack jaw, pale glowing eyes, "
               "arms reaching forward with clawed hands",
    "fetish": "a Fetish Shaman: a flayer with a huge feathered headdress of gold and red plumes, bone mask, glowing yellow eyes, "
              "carrying a staff topped with a smoking skull",
    "inquisitor": "an Inquisitor: a Zakarum zealot leader in heavy white-and-gold vestments, ornate gold-trimmed mitre, "
                  "holding a book in the left hand and raising an open palm in the right",
    "bone_priest": "the Bone Priest: a towering skeletal boss at 1.6x scale in a hooded ash-brown robe with a crimson stole, "
                   "a gold spiked crown, carrying a staff topped by a caged green orb",
}

FIXES = {
    "skeleton": "The ribs are flat bars on a box: paint a real rib cage and spine.",
    "priest": "The robe is a stiff cone: paint heavy flowing cloth that reaches the feet; the arms are bony.",
    "witch": "The gown is a stiff cone: paint flowing cloth that reaches the feet.",
    "gargoyle": "The wings are flat triangles: paint bat wings with finger bones and torn membrane, spread exactly as drawn.",
    "azazel": "The wings are flat triangles: paint bat wings with bones and membrane, spread exactly as drawn.",
    "zombie": "The arms are straight blocks: paint gaunt rotting arms in the same reach.",
    "spider": "The legs are thin rods: paint eight segmented spider legs with joints, moving naturally in walk frames.",
    "bat": "The wings are flat triangles: paint bat wings with finger bones and torn membrane, spread exactly as drawn.",
    "hulk": "The thorns are simple cones: paint gnarled bark and organic thorns growing from the body.",
    "drowned": "The weed is simple rods: paint wet seaweed and kelp draping naturally from the bloated body.",
    "fetish": "The headdress feathers are simple rods: paint layered feathers with barbs and natural curvature.",
    "bone_priest": "The cage is boxy rods: paint an ornate gold cage with filigree around the glowing orb.",
}

FRAME_WORDS = {
    "walk1": "walk, left foot forward", "walk2": "walk, passing", "walk3": "walk, right foot forward", "walk4": "walk, passing",
    "wind": "blow: wind-up, weapon raised high", "strike": "blow: the strike, weapon brought down", "recover": "blow: recovering",
    "raise": "spell: staff raised", "chant": "spell: chanting, both arms high",
}
FACING_WORDS = {"front": "facing the viewer (walking towards the camera)", "back": "facing away from the viewer",
                "side": "facing right, in profile (walking to the right)"}
SPLIT = {"azazel"}   # painted one facing per sheet
#: Sheets laid out in fewer columns than they have frames: a single row padded to 3:2 leaves an empty field
#: that both models filled (with a dark backdrop, or with giant figures).
COLUMNS = {"mon-azazel@side": 4}
PROVIDERS = ("codex", "openrouter")
CODEX_MODEL = "gpt-5.5"   # the configured default may be one a ChatGPT account refuses


@dataclass
class Subject:
    name: str
    sheet: restyle.Sheet
    images: dict[str, Image.Image]
    prompt: str
    install: str            # the painted sheet it becomes part of
    part_of: list[str]      # the keys of the installed sheet it provides


def monster_subjects(kind: str) -> list[Subject]:
    sheet, images = monster_sheet(kind)
    frames = figures.frames(kind)
    subjects = []
    parts = [(f"mon-{kind}@{facing}", [facing]) for facing in figures.FACINGS] if kind in SPLIT else [(f"mon-{kind}", list(figures.FACINGS))]
    for name, facings in parts:
        keys = [(f"{facing}/{frame}", {"facing": facing, "frame": frame}) for facing in facings for frame in frames]
        sub = restyle.Sheet.layout(keys, cols=COLUMNS.get(name, len(frames)), cell=sheet.cell, origin=sheet.origin, scale=sheet.scale)
        who = MONSTER_SUBJECTS[kind].split(':')[0]
        rows = (f"every cell: {who} {FACING_WORDS[facings[0]]}" if len(facings) == 1 else
                "; ".join(f"row {i + 1}: {who} {FACING_WORDS[f]}" for i, f in enumerate(facings)))
        per_row = COLUMNS.get(name, len(frames))
        cols = "; ".join(f"row {i // per_row + 1} column {i % per_row + 1}: {FRAME_WORDS[f]}" if per_row < len(frames)
                         else f"column {i + 1}: {FRAME_WORDS[f]}" for i, f in enumerate(frames))
        prompt = _prompt(sub, f"{rows}. {cols}. The poses differ from column to column on purpose; every row shows the same "
                              f"creature from another side, with the same pose in each column.", MONSTER_SUBJECTS[kind], FIXES.get(kind, ""))
        subjects.append(Subject(name, sub, {k: images[k] for k, _ in keys}, prompt, f"mon-{kind}", [k for k, _ in keys]))
    return subjects


def tower_subject() -> Subject:
    canvas, origin = structures.TOWER_CELL
    kinds = structures.TOWER_KINDS
    keys = [(f"{kind}/{rank}", {"kind": kind, "rank": rank}) for rank in range(3) for kind in kinds]
    sheet = restyle.Sheet.layout(keys, cols=len(kinds), cell=(canvas[0] * DENSITY, canvas[1] * DENSITY),
                                 origin=(origin[0] * DENSITY, origin[1] * DENSITY), scale=DENSITY)
    images = {key: structures.tower_image(tags["kind"], tags["rank"]) for key, tags in keys}
    layout = ("Columns, left to right: a fire pyre (a stone pillar carrying an iron brazier of roaring flame); a storm obelisk (a "
              "dark basalt obelisk with glowing blue runes and a floating blue crystal, copper coils from the second rank); a frost "
              "shrine (a cluster of pale blue ice crystals on a stone plinth); a plague totem (a bone pole of stacked skulls with "
              "glowing green eyes and a horned ram skull on top, over a pool of green venom); a bone altar (a stone slab piled with "
              "skulls and ribs, a violet-green flame growing with rank); a druid grove (a ring of standing stones around a twisted oak, "
              "leafier with each rank). Rows, top to bottom: the first, second and third rank of each; every rank is taller and grander "
              "than the one above it, on purpose.")
    prompt = _prompt(sheet, layout, "the six magical defence towers of a gothic cathedral, each standing on its own square stone plinth",
                     "Paint carved gothic stone, wrought iron and bone in place of the blocky shapes, keeping each tower's outline.")
    return Subject("towers", sheet, images, prompt, "towers", [k for k, _ in keys])


def gate_subject() -> Subject:
    canvas, origin = structures.GATE_CELL
    keys = [(look, {"look": look}) for look in structures.GATE_LOOKS]
    sheet = restyle.Sheet.layout(keys, cols=len(keys), cell=(canvas[0] * DENSITY, canvas[1] * DENSITY),
                                 origin=(origin[0] * DENSITY, origin[1] * DENSITY), scale=DENSITY)
    images = {look: structures.gate_image(look) for look, _ in keys}
    layout = ("Left to right: the gate whole; the same gate battered, two planks broken short and a band bent; the gate smashed, only "
              "splintered stumps and planks on the floor.")
    prompt = _prompt(sheet, layout, "a warded gate: a double door of dark oak planks bound with three iron bands, a gilded holy ward "
                                    "(a ring with a cross) on its face", "")
    return Subject("gates", sheet, images, prompt, "gates", [k for k, _ in keys])


def structure_subject() -> Subject:
    canvas, origin = structures.ARCH_CELL
    keys = [("arch", {}), ("pillar", {})]
    sheet = restyle.Sheet.layout(keys, cols=2, cell=(canvas[0] * DENSITY, canvas[1] * DENSITY),
                                 origin=(origin[0] * DENSITY, origin[1] * DENSITY), scale=DENSITY)
    images = {"arch": structures.arch_image(), "pillar": structures.pillar_image()}
    layout = ("Left: a gothic stone arch standing across a corridor: two square buttressed piers with pinnacles and a pointed arch "
              "between them, a small gilded ward on the keystone; the opening between the piers stays empty. Right: a gothic stone "
              "column with a carved base and capital, a three-branched candelabrum with lit candles on top.")
    prompt = _prompt(sheet, layout, "pieces of a desecrated gothic cathedral: dark grey carved stone, moss and cracks",
                     "Paint carved gothic stonework in place of the blocks, keeping each outline.")
    return Subject("structures", sheet, images, prompt, "structures", [k for k, _ in keys])


def _prompt(sheet: restyle.Sheet, layout: str, subject: str, fixes: str) -> str:
    w, h = sheet.size
    return (f"The background of this sprite sheet is a chroma key: it must stay pure flat magenta #FF00FF everywhere outside "
            f"the figures, as in the attached image. Edit target: the attached sprite sheet. It is a grid of {sheet.rows} rows by {sheet.cols} columns of {sheet.cell[0]}x"
            f"{sheet.cell[1]} px cells on a flat magenta #FF00FF background, inside an empty magenta margin; thin dark grey lines mark "
            f"the cell borders: keep the lines and the margin exactly where they are and keep each figure centred in its own cell. "
            f"{layout}\n\nThe subject: {subject}.\n\n{STYLE}\n\nThe drawings are rough low-poly stand-ins: repaint every cell as the "
            f"finished sprite, drawing the plausible version of whatever the stand-in gets wrong. {fixes}\n\nKeep exactly: each "
            f"figure's position, scale, pose, facing and where it stands. Every cell keeps the flat #FF00FF background with nothing "
            f"else on it: no ground, no shadow, no glow on the background, no text, no extra objects. Output the same layout.\n\n"
            f"The magenta is a chroma key that will be cut away: every pixel that is not part of a figure, in the cells and in the "
            f"margin, must stay pure flat #FF00FF. Do not paint a dark backdrop, a vignette or any lighting on the background.")


def subjects(selected: set[str] | None) -> list[Subject]:
    found = [s for kind in MONSTERS for s in monster_subjects(kind)] + [tower_subject(), gate_subject(), structure_subject()]
    if selected:
        found = [s for s in found if s.name in selected or s.install in selected]
    return found


def _padded_size(size: tuple[int, int], aspect: float = 1.5) -> tuple[int, int]:
    w, h = size
    return (w, round(w / aspect)) if w / h > aspect else (round(h * aspect), h)


def padded(image: Image.Image) -> Image.Image:
    w, h = image.size
    size = _padded_size(image.size)
    out = Image.new("RGB", size, restyle.MAGENTA)
    out.paste(image.convert("RGB"), ((size[0] - w) // 2, (size[1] - h) // 2))
    return out


def unpadded(rendered: Image.Image, sheet_size: tuple[int, int]) -> Image.Image:
    """The part of the model's output where the sheet was: the padding comes back scaled, never the grid's own frame."""
    pw, ph = _padded_size(sheet_size)
    sx, sy = rendered.width / pw, rendered.height / ph
    x0, y0 = (pw - sheet_size[0]) / 2 * sx, (ph - sheet_size[1]) / 2 * sy
    return rendered.crop((round(x0), round(y0), round(x0 + sheet_size[0] * sx), round(y0 + sheet_size[1] * sy)))


# -- Commands ---------------------------------------------------------------------------------


def cmd_dump(args: argparse.Namespace) -> None:
    args.dir.mkdir(parents=True, exist_ok=True)
    for s in subjects(args.subjects):
        s.sheet.save(args.dir / s.name, s.images)
        padded(Image.open(restyle.file(args.dir / s.name, "png"))).save(restyle.file(args.dir / s.name, "input.png"))
        restyle.file(args.dir / s.name, "prompt.txt").write_text(s.prompt)
        print(f"{s.name}: {s.sheet.size[0]}x{s.sheet.size[1]}, {len(s.sheet.cells)} cells of {s.sheet.cell[0]}x{s.sheet.cell[1]}")


def _render(directory: Path, s: Subject, provider: str, effort: str = "low") -> str:
    out = directory / s.name / f"{provider}.png"
    if out.exists():
        return f"{s.name}: kept {out}"
    source = restyle.file(directory / s.name, "input.png")
    prompt = restyle.file(directory / s.name, "prompt.txt").read_text()
    if provider == "codex":
        restyle.render_with_codex(source, prompt, out, model=CODEX_MODEL, effort=effort)
    else:
        usage = restyle.render_with_openrouter(source, prompt, out, model="google/gemini-3.1-flash-image-preview",
                                               api_key=restyle.openrouter_api_key(), aspect_ratio="3:2", image_size="2K")
        (directory / s.name / "usage.json").write_text(json.dumps(usage, indent=1))
    return f"{s.name}: rendered {out}"


def cmd_render(args: argparse.Namespace) -> None:
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(lambda s: _render(args.dir, s, args.provider, args.effort), subjects(args.subjects)):
            print(line, flush=True)


def cmd_cut(args: argparse.Namespace) -> None:
    PAINTED.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[Subject]] = {}
    for s in subjects(args.subjects):
        groups.setdefault(s.install, []).append(s)
    for install, parts in groups.items():
        frames: dict[str, Image.Image] = {}
        ok = True
        for s in parts:
            result = None
            for provider in (args.provider, *(p for p in PROVIDERS if p != args.provider)):
                rendered = args.dir / s.name / f"{provider}.png"
                if not rendered.exists():
                    continue
                try:
                    result = restyle.cut(s.sheet, unpadded(Image.open(rendered), s.sheet.size),
                                         Image.open(restyle.file(args.dir / s.name, "png")))
                    break
                except ValueError as rejected:   # the model broke the sheet (lost the key colour, the grid)
                    print(f"{s.name} ({provider}): rejected: {rejected}")
            if result is None:
                print(f"{s.name}: no render cuts cleanly; render it again")
                ok = False
                continue
            print(f"{s.name}: scale {result.registration.scale:.2f}, {len(result.flagged)} of {len(result.report)} cells flagged")
            for r in result.flagged:
                print(f"   {r.key}: coverage {r.coverage:.3f} vs {r.original_coverage:.3f}, drift {r.drift:.0f}px, edge {r.touches_edge}")
            if len(result.flagged) > args.tolerance and not args.force:
                ok = False
            frames.update(result.frames)
        if not ok:
            print(f"   {install}: not installed")
            continue
        whole = _whole(install)
        restyle.save_frames(_Frames(frames), whole, PAINTED / install)
        print(f"   installed {PAINTED / install}.png")


class _Frames:
    def __init__(self, frames: dict[str, Image.Image]) -> None:
        self.frames = frames


def _whole(install: str) -> restyle.Sheet:
    if install.startswith("mon-"):
        return monster_sheet(install[4:])[0]
    return {"towers": tower_subject, "gates": gate_subject, "structures": structure_subject}[install]().sheet


def cmd_preview(args: argparse.Namespace) -> None:
    args.dir.mkdir(parents=True, exist_ok=True)
    installs = sorted({s.install for s in subjects(args.subjects)})
    for install in installs:
        stem = PAINTED / install
        if not restyle.file(stem, "json").exists():
            continue
        sheet, painted = restyle.load_frames(stem)
        original = monster_sheet(install[4:])[1] if install.startswith("mon-") else {
            "towers": tower_subject, "gates": gate_subject, "structures": structure_subject}[install]().images
        keys = [c.key for c in sheet.cells]
        per_row = sheet.cols
        rows = []
        for r in range(sheet.rows):
            chunk = keys[r * per_row:(r + 1) * per_row]
            rows.append(restyle.strip(original, chunk, background=(40, 34, 34)))
            rows.append(restyle.strip(painted, chunk, background=(40, 34, 34)))
        out = Image.new("RGBA", (max(r.width for r in rows), sum(r.height for r in rows)))
        y = 0
        for row in rows:
            out.alpha_composite(row, (0, y))
            y += row.height
        out.save(args.dir / f"preview-{install}.png")
        print(f"wrote {args.dir / f'preview-{install}.png'}")


def cmd_refresh(args: argparse.Namespace) -> None:
    cmd_dump(args)
    cmd_render(args)
    cmd_cut(args)
    cmd_preview(args)


GROUND_PROMPT = (
    "Edit target: the attached top-down map of a tower-defence level, {w}x{h} px. Repaint it as a finished, richly detailed painted "
    "game map seen from above, in the manner of the late-1990s dark action-RPG classics: {words}. The lighter band that winds from "
    "the swirling hell portal of fire to the radiant golden sanctuary door is the path the monsters walk; the dark squares and "
    "blobs lying on the floor are obstacles and pits: keep each one where it is and paint it as what the words describe. The light "
    "is dim and even: do not paint strong spotlights or darkness, the game adds its own lighting.\n\n"
    "Keep exactly: the position and width of the path and every one of its turns, the square grid of floor tiles (every tile "
    "stays where it is: towers are built on them), the walls, the pits, the obstacles, the portal and the door. No text, no "
    "characters, no monsters, no towers. Output the same {w}x{h} layout.")


def _paint(source: Path, prompt: str, out: Path, provider: str, aspect: str) -> None:
    if out.exists():
        return
    if provider == "codex":
        restyle.render_with_codex(source, prompt, out, model=CODEX_MODEL, effort="low")
    else:
        restyle.render_with_openrouter(source, prompt, out, model="google/gemini-3.1-flash-image-preview",
                                       api_key=restyle.openrouter_api_key(), aspect_ratio=aspect, image_size="2K")


def _ground(directory: Path, key: str, provider: str) -> str:
    location = LOCATIONS[key]
    theme = mapart.THEMES[location.theme]
    image = mapart.stand_in(location.level, theme)
    small = image.resize((image.width // 2, image.height // 2), Image.LANCZOS)
    source = directory / f"ground-{key}.input.png"
    small.save(source)
    out = directory / f"ground-{key}" / f"{provider}.png"
    _paint(source, GROUND_PROMPT.format(w=small.width, h=small.height, words=theme.words), out, provider, "16:9")
    painted = Image.open(out).convert("RGB").resize(image.size, Image.LANCZOS)
    painted.save(mapart.painted(key))
    Image.blend(image, painted, 0.5).save(directory / f"ground-{key}-overlay.png")
    return f"installed {mapart.painted(key)}; compare {directory / f'ground-{key}-overlay.png'}"


def cmd_ground(args: argparse.Namespace) -> None:
    args.dir.mkdir(parents=True, exist_ok=True)
    PAINTED.mkdir(parents=True, exist_ok=True)
    keys = sorted(args.locations) if args.locations else [k for k in LOCATIONS if not mapart.painted(k).exists()]
    with ThreadPoolExecutor(args.jobs) as pool:
        for line in pool.map(lambda key: _ground(args.dir, key, args.provider), keys):
            print(line, flush=True)


WORLDMAP_PROMPT = (
    "Edit target: the attached map, {w}x{h} px, the world map of a dark gothic tower-defence game. Repaint it as one finished, richly "
    "detailed painting in the manner of the late-1990s dark action-RPG classics: a cut-away view of the ground under a medieval "
    "village at night. On the surface, under a starry sky with a blood-red moon: the burning village of Tristram on the left, a "
    "churchyard of crooked crosses and headstones with a crypt's mouth in the middle, and a great dark gothic cathedral with a "
    "spire on the right, its windows glowing red. Below the ground, layers of rock that grow darker and redder with depth, and "
    "four chambers joined by narrow tunnels, each exactly where the dark cavity is: under the cathedral a labyrinth hall lit "
    "violet with pillars; to the left, deeper, catacombs of bone-lined arches lit pale; to the right, deeper still, a cave with a "
    "glowing lava lake; at the bottom, the gate of hell: a huge burning archway of black stone in fire and smoke.\n\n"
    "Keep exactly: where each chamber, tunnel, building and the moon is, and the horizon line. No text, no labels, no people, no "
    "monsters. Output the same {w}x{h} layout.")


def cmd_worldmap(args: argparse.Namespace) -> None:
    args.dir.mkdir(parents=True, exist_ok=True)
    image = worldmap.stand_in()
    small = image.resize((image.width // 2, image.height // 2), Image.LANCZOS)
    source = args.dir / "worldmap.input.png"
    small.save(source)
    out = args.dir / "worldmap" / f"{args.provider}.png"
    _paint(source, WORLDMAP_PROMPT.format(w=small.width, h=small.height), out, args.provider, "16:10" if args.provider == "codex" else "3:2")
    painted = Image.open(out).convert("RGB").resize(image.size, Image.LANCZOS)
    painted.save(worldmap.PAINTED, quality=92)
    Image.blend(image, painted, 0.5).save(args.dir / "worldmap-overlay.png")
    print(f"installed {worldmap.PAINTED}; compare {args.dir / 'worldmap-overlay.png'}")


KEYART_PROMPT = (
    "Create a new image with the built-in image_gen tool: a wide 3:2 landscape painting for the title screen of a dark gothic "
    "tower-defence game called Hellward, in the manner of the late-1990s dark action-RPG box art and loading screens. The nave of "
    "a desecrated gothic cathedral at night, seen from low down: a long torn crimson carpet with gold trim runs from the "
    "foreground to a radiant golden sanctuary door at the far end; on either side stand magical towers: a stone pillar with an "
    "iron brazier of roaring fire, a dark obelisk crowned with a floating blue crystal crackling with lightning, a cluster of "
    "glowing blue ice crystals, a totem of stacked skulls with green glowing eyes. From a swirling hell portal on the left a "
    "horde pours in: small red imp demons, skeletons, a horned goatman, gargoyles in the air, and at their head a hunched shaman "
    "with a skull staff whose violet curse snakes towards the fire tower. Candlelight, embers in the air, deep shadows, painterly "
    "and gritty, rich detail. Keep the upper middle third darker and calmer for the title text. No text, no letters, no logo. "
    "Save the generated image as {out}; finish by printing the path.")


def cmd_keyart(args: argparse.Namespace) -> None:
    import subprocess

    args.dir.mkdir(parents=True, exist_ok=True)
    out = args.dir / "keyart" / "codex.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        result = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", "-m", CODEX_MODEL,
                                 "-c", f"model_reasoning_effort={args.effort}", "-C", str(out.parent), "-"],
                                input=KEYART_PROMPT.format(out=out), capture_output=True, text=True, timeout=900)
        if not out.exists():
            raise RuntimeError(f"codex did not write {out}:\n{(result.stdout + result.stderr)[-2000:]}")
    image = Image.open(out).convert("RGB")
    PAINTED.mkdir(parents=True, exist_ok=True)
    image.save(PAINTED / "title.jpg", quality=92)
    print(f"installed {PAINTED / 'title.jpg'} ({image.width}x{image.height})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--subjects", type=lambda s: set(s.split(",")), default=None)
    parser.add_argument("--locations", type=lambda s: set(s.split(",")), default=None, help="floors to paint (ground)")
    parser.add_argument("--provider", choices=PROVIDERS, default="codex", help="render with, and cut this one's render first")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--effort", default="low", help="Codex's reasoning effort: raise it when the painter drops instructions")
    parser.add_argument("--tolerance", type=int, default=2, help="flagged cells a sheet may have and still be installed")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("command", choices=("dump", "render", "cut", "preview", "refresh", "ground", "worldmap", "keyart"))
    parser.add_argument("dir", type=Path)
    args = parser.parse_args()
    globals()[f"cmd_{args.command}"](args)


if __name__ == "__main__":
    main()
