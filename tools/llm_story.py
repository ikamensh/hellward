"""Walk the story as the player sees it: the LLM's seat for the words and panels.

    uv run python tools/llm_story.py              # step through beat by beat
    uv run python tools/llm_story.py list         # the beats in the player's order
    uv run python tools/llm_story.py show 14      # one beat: its words and its panel
    uv run python tools/llm_story.py show temple-before
    uv run python tools/llm_story.py all          # every beat, in order
    uv run python tools/llm_story.py all --notes  # ... plus what the painter was told
    uv run python tools/llm_story.py stills       # re-render the battle beats' stills

One beat is one thing the player sits through: a prologue shot, a story page, a
briefing's taunt, a fight's shape. Each beat names the panel the client shows;
open the path to see it. The order is the game's own (godot/game/scripts/game.gd):
the prologue, then per location its before page, its briefing, its fight, and its
after page — with each act's ending in place of its last location's after page.
A fight beat is watched, not played: its still, its waves, its monsters (each kind
shown once, where it first walks), its music, and how hard it was found to be.
See docs/story.md.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hellward.audio.music import BOSS_BLURBS, DUNGEONS  # noqa: E402
from hellward.sim.breaches import BREACHES  # noqa: E402
from hellward.sim.campaign import ACT_ENDS, LOCATIONS, ORDER, Location  # noqa: E402
from hellward.sim.content import CURSES, MONSTERS  # noqa: E402
from hellward.story import LAST_PAGES, STORIES  # noqa: E402

STORY_DIR = ROOT / "godot" / "game" / "assets" / "story"
PROLOGUE_DIR = STORY_DIR / "prologue"
STILLS_DIR = ROOT / "hellward" / "assets" / "story"   # levels/<key>.jpg, monsters.jpg: `stills` renders these
MODELS_DIR = ROOT / "godot" / "game" / "assets" / "models"
STRIP = ("fire", "thunder", "frost", "dead")   # one screen of four tower panels, side by side
VISIONS = ("bones-v0", "bones-v1", "bones-v2")   # the futures flickering above the bones

#: How hard each location was found: (veteran margin, best-bot margin) from docs/campaign.md's tuning —
#: monster life could rise by that factor before the bot loses, so higher is easier. Refresh with the doc.
DIFFICULTY_SOURCE = "2026-10-02 tuning, smart leaders"
DIFFICULTY: dict[str, tuple[float | None, float]] = {
    "tristram": (1.28, 1.39), "graveyard": (1.19, 2.07), "cathedral": (1.11, 2.58),
    "catacombs": (1.12, 2.31), "caves": (1.61, 1.80), "hells_gate": (1.23, 1.57),
    "docks": (None, 1.63), "spider_forest": (None, 2.26), "jungle": (None, 1.73),
    "drowned_city": (None, 1.91), "travincal": (None, 1.17), "temple": (None, 1.43),
}


@dataclass(frozen=True)
class Beat:
    key: str                    # "prologue/bones", "tristram-before", "tristram/briefing", ...
    head: str                   # "[i/n] HEAD": where the player is
    panels: tuple[str, ...]     # what the client shows, as paths from the repo root
    body: tuple[str, ...]       # the words, as written in the sources
    note: str = ""              # how it plays, shown always
    extra: tuple[str, ...] = ()  # --notes: the voice take, what the painter was told


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def prologue_beats() -> list[Beat]:
    """Every prologue shot in the timeline's order, each with the captions that sound over it."""
    timeline = json.loads((PROLOGUE_DIR / "timeline.json").read_text())
    shots, words = timeline["shots"], timeline["words"]
    beats = []
    for shot in shots:
        key = str(shot["key"])
        start, length = float(shot["start"]), float(shot["length"])
        over = [w for w in words if start <= float(w["at"]) < start + length]
        captions = tuple(str(w["text"]) for w in over)
        voices = tuple(dict.fromkeys(str(w["voice"]) for w in over if "voice" in w))
        if key == "title":
            beats.append(Beat("prologue/title", "PROLOGUE — the title",
                              (_rel(PROLOGUE_DIR / "lamp.jpg"),),
                              ("HELLWARD", "Keep it burning. (written, not spoken)"),
                              "the lamp catches again under the title"))
            continue
        panels = (_rel(PROLOGUE_DIR / f"{key}.jpg"),)
        note, extra = "", []
        if key in STRIP:
            note = "one of four tower panels, side by side on one screen; each lights on its word"
        if key == "bones":
            panels += tuple(_rel(PROLOGUE_DIR / f"{v}.jpg") for v in VISIONS)
            note = "the visions flicker above the bones, each held for less time than the one before"
        if voices:
            files = ", ".join(_rel(PROLOGUE_DIR / f"voice-{v}.wav") for v in voices)
            ran_over = " (one line runs over the cut from the last shot)" if len(voices) < len(over) else ""
            extra.append(f"voice: {files}{ran_over}")
        beats.append(Beat(f"prologue/{key}", f"PROLOGUE — {key}", panels,
                          captions or ("(no words: a roar)",), note, tuple(extra)))
    return beats


def page_beats(story_key: str) -> list[Beat]:
    """One beat per page of a story: its panel and its paragraphs."""
    story = STORIES[story_key]
    place, _, when = story.key.partition("/")
    if when == "end":
        head = f"Act {'I' * story.act} ends"
    else:
        head = f"{LOCATIONS[place].name} — {'before' if when == 'before' else 'after'} the fight"
    beats = []
    for n, page in enumerate(story.pages, 1):
        tail = f" (page {n} of {len(story.pages)})" if len(story.pages) > 1 else ""
        extra = [f"paint: {page.panel}"]
        if page.refs:
            extra.append(f"refs: {', '.join(page.refs)}")
        if page.base:
            extra.append(f"base: prologue/{page.base}.jpg (painted as an edit of it)")
        beats.append(Beat(page.key, head + tail, (_rel(STORY_DIR / f"{page.key}.jpg"),),
                          tuple(page.text), extra=tuple(extra)))
    return beats


def briefing_beat(location: Location) -> Beat:
    """A briefing's story: the Bone Priest's taunt, the lesson, what the map said."""
    return Beat(f"{location.key}/briefing", f"{location.name} — briefing", (),
                (f"\u201c{location.taunt}\u201d — the Bone Priest", f"lesson: {location.lesson}",
                 f"map: {location.blurb}"),
                f"no new panel: the briefing plays over the before panel, dimmed "
                f"({location.key}-before.jpg)")


def modelled(kind: str) -> bool:
    """Whether a monster kind has its own model, as the client checks (survey.gd); else a stand-in."""
    return (MODELS_DIR / f"mon_{kind}.glb").is_file()


def first_walk() -> dict[str, str]:
    """Every monster kind's first location in the campaign's order (authored waves only)."""
    first: dict[str, str] = {}
    for key in ORDER:
        for wave in LOCATIONS[key].waves:
            for group in wave.groups:
                first.setdefault(group.kind, key)
    return first


def walked_kinds() -> list[str]:
    """Every kind the player can meet, in the roster's order: authored waves and breaches."""
    walked = set(first_walk())
    for spec in BREACHES.values():
        walked.update(group.kind for group in spec.groups)
    return [kind for kind in MONSTERS if kind in walked]


def _wave_mix(location: Location, index: int) -> str:
    """One wave's bodies: counts per kind in first-appearance order, leaders with their curses
    and what they raise — display names throughout, as the monster sheet labels them."""
    counts: dict[str, int] = {}
    for group in location.waves[index].groups:
        counts[group.kind] = counts.get(group.kind, 0) + group.count
    parts = []
    for kind, count in counts.items():
        kind = str(kind)
        monster = MONSTERS[kind]
        if monster.boss:
            parts.append(f"{monster.name} [BOSS]")
            continue
        bit = f"{monster.name} ×{count}"
        if monster.leader is not None:
            arts = [CURSES[c].name for c in monster.leader.curses]
            if monster.leader.raises:
                arts.append(f"raises {MONSTERS[monster.leader.raises].name}")
            bit += f" ({', '.join(arts)})"
        parts.append(bit)
    return f"w{index + 1} \u2018{location.wave_names[index]}\u2019: " + ", ".join(parts)


def battle_beat(location: Location, *, first: bool = False) -> Beat:
    """A fight's shape, watched not played: its still, waves, new monsters, music, hardship."""
    waves = location.waves
    bodies = sum(group.count for wave in waves for group in wave.groups)
    born = first_walk()
    new = list(dict.fromkeys(group.kind for wave in waves for group in wave.groups
                               if born[group.kind] == location.key))  # kinds walking here first
    body = [f"{len(waves)} waves, {bodies} bodies"]
    # What the client tells the player the fight is for (intro.gd title card, main.gd announce).
    body.append("objective: Hold the sanctuary — where your lantern burns — until the last wave breaks. (the client's title card)")
    body += [_wave_mix(location, i) for i in range(len(waves))]
    if new:
        marked = [f"{MONSTERS[kind].name} (stand-in)" if not modelled(kind)
                  else MONSTERS[kind].name for kind in new]
        body.append(f"new here: {', '.join(marked)}")
    if location.key in BREACHES:
        spec = BREACHES[location.key]
        pack = ", ".join(f"{MONSTERS[g.kind].name} ×{g.count}" for g in spec.pack)
        body.append(f"breach after w{spec.after_wave + 1}: {spec.name} — {spec.elite_name} "
                    f"({MONSTERS[spec.elite.kind].name}) + {pack}")
        body.append(f"sealed entrance: {spec.blurb}")  # the briefing screen shows name and blurb
    body.append(f"music: battle_{location.key} — {DUNGEONS[location.key].blurb} (playing since the briefing)")
    walking = list(dict.fromkeys(g.kind for g in waves[-1].groups if MONSTERS[g.kind].boss))
    for kind in walking:
        body.append(f"the last wave breaks in with boss ({MONSTERS[kind].name}) — {BOSS_BLURBS[kind]}")
    veteran, best = DIFFICULTY[location.key]
    gauge = f"\u00d7{veteran:g} veteran / \u00d7{best:g} best bot" if veteran is not None \
        else f"\u00d7{best:g} best bot"
    body.append(f"hardship {gauge} ({DIFFICULTY_SOURCE}; higher = easier)")
    panels = (_rel(STILLS_DIR / "levels" / f"{location.key}.jpg"),)
    note = "overhead, as the demo plays it"
    if first:
        panels = (_rel(STILLS_DIR / "monsters.jpg"),) + panels
        note += "; monsters.jpg shows every kind that walks, as the battle shows it, a red post for a stand-in"
    return Beat(f"{location.key}/battle", f"{location.name} — the fight", panels, tuple(body), note)


def beats() -> list[Beat]:
    """The whole story in the player's order: the prologue, then per location its before page, its
    briefing, its fight, and its after page — each act's ending in place of its last location's after page."""
    out = prologue_beats()
    for key in ORDER:
        location = LOCATIONS[key]
        out += page_beats(f"{key}/before")
        out.append(briefing_beat(location))
        out.append(battle_beat(location, first=key == ORDER[0]))
        if key in ACT_ENDS.values():
            out += page_beats(LAST_PAGES[location.act])
        else:
            out += page_beats(f"{key}/after")
    return out


def formatted(beat: Beat, index: int, total: int, *, notes: bool = False) -> str:
    """One beat as the player gets it: where they are, what they see, what they read."""
    lines = [f"[{index}/{total}] {beat.head}  ({beat.key})"]
    lines += [f"panel: {panel}" for panel in beat.panels]
    if beat.note:
        lines.append(beat.note)
    lines += ["", *beat.body]
    if notes and beat.extra:
        lines += ["", *beat.extra]
    return "\n".join(lines)


def summary(beat: Beat) -> str:
    """One line for the list: the first words, cut short."""
    first = beat.body[0] if beat.body else ""
    return first if len(first) <= 64 else first[:63] + "…"


def walk(all_beats: list[Beat], *, notes: bool = False) -> int:
    """Step through the beats: Enter goes on, a number or key jumps, `list` looks around."""
    total = len(all_beats)
    print(f"{total} beats, as the player meets them. Enter goes on; `p` goes back; a number or key "
          f"jumps; `notes` shows what the painter was told; `quit` leaves.")
    index = 0
    print(formatted(all_beats[0], 1, total, notes=notes))
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        word = line.lower()
        if word in ("quit", "q"):
            return 0
        if word == "list":
            for n, beat in enumerate(all_beats, 1):
                print(f"{n:>3}  {beat.key:<22} {summary(beat)}")
            continue
        if word == "notes":
            notes = not notes
            print(f"notes {'on' if notes else 'off'}")
            print(formatted(all_beats[index], index + 1, total, notes=notes))
            continue
        if word in ("", "n", "next"):
            index += 1
        elif word in ("p", "prev", "previous"):
            index -= 1
        elif word.isdigit() and 1 <= int(word) <= total:
            index = int(word) - 1
        else:
            keys = [n for n, beat in enumerate(all_beats) if beat.key == word]
            if not keys:
                print(f"no beat {line!r} — a number 1..{total}, a key, `list`, or `quit`")
                continue
            index = keys[0]
        if index >= total:
            index = total - 1
            print("the end: keep it burning.")
            continue
        if index < 0:
            index = 0
            print("the lamp is lit: the story begins above.")
            continue
        print(formatted(all_beats[index], index + 1, total, notes=notes))


# -- Stills ------------------------------------------------------------------------------------------------------------


def _capture(*args: str) -> None:
    """One Godot capture through the repo's wrapper: never the bare binary (godot/AGENTS.md)."""
    import subprocess

    subprocess.run([str(ROOT / "godot" / "tools" / "godot-capture.sh"), "--path", "game",
                    "--fixed-fps", "30", "res://scenes/capture.tscn", "--", *args],
                   cwd=ROOT / "godot", check=True, capture_output=True, text=True)


def label_monsters(png: Path, kinds: list[str]) -> Image.Image:
    """The survey's monster sheet with each kind named under its feet, from the scene's own layout
    (survey.gd: 7 columns in the given order, the camera's fov 40 over 1920x1080)."""
    cols = 7
    rows = math.ceil(len(kinds) / cols)
    flying = {k for k, m in MONSTERS.items() if m.flying}
    campos = (0.0, 9.0 + rows * 1.5, rows * 3.4 + 9.0)
    target = (0.0, 1.0, (rows - 1) * 1.7)

    def sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return a[0] - b[0], a[1] - b[1], a[2] - b[2]

    def norm(v: tuple[float, float, float]) -> tuple[float, float, float]:
        length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
        return v[0] / length, v[1] / length, v[2] / length

    def cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
        return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]

    forward = norm(sub(target, campos))
    right = norm(cross(forward, (0.0, 1.0, 0.0)))
    up = cross(right, forward)
    tan_half = math.tan(math.radians(20.0))

    def project(p: tuple[float, float, float]) -> tuple[float, float]:
        v = sub(p, campos)
        cx = v[0] * right[0] + v[1] * right[1] + v[2] * right[2]
        cy = v[0] * up[0] + v[1] * up[1] + v[2] * up[2]
        cz = v[0] * forward[0] + v[1] * forward[1] + v[2] * forward[2]
        return 960 * (1 + (cx / cz) / (tan_half * 16 / 9)), 540 * (1 - (cy / cz) / tan_half)

    image = Image.open(png).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    for i, kind in enumerate(kinds):
        # Under the feet, where flyers hover included: near the body collides with the row above.
        feet = ((i % cols - (cols - 1) / 2) * 3.0, 1.2 if kind in flying else 0.0, (i // cols) * 3.4)
        x, y = project(feet)
        name = MONSTERS[kind].name
        if not modelled(kind):
            name += " *"
        draw.text((x, y + 16), name, font=font, anchor="ma", fill=(236, 222, 190),
                  stroke_width=3, stroke_fill=(10, 6, 6))
    draw.text((960, 1040), "* a tinted stand-in, red post beside it", font=font, anchor="ma",
              fill=(236, 222, 190), stroke_width=3, stroke_fill=(10, 6, 6))
    return image


def _jpeg(image: Image.Image, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    image.resize((1600, int(image.height * 1600 / image.width + 0.5)), Image.LANCZOS).save(out, "JPEG", quality=86)


def stills() -> int:
    """Render what the battle beats show into hellward/assets/story/: each location overhead as the demo
    plays it (as survey.sh frames it) and every kind that walks, labeled, on one sheet. A few minutes."""
    import subprocess

    tmp = Path(tempfile.mkdtemp(prefix="hw-stills-"))
    failures = []
    try:
        kinds = walked_kinds()
        flying = ",".join(k for k in kinds if MONSTERS[k].flying)
        sheet = tmp / "monsters.png"
        try:
            _capture("scene=res://scenes/survey.tscn", "res=1920x1080", "what=monsters",
                     f"kinds={','.join(kinds)}", f"flying={flying}", f"out={sheet}")
            _jpeg(label_monsters(sheet, kinds), STILLS_DIR / "monsters.jpg")
            print(f"still {STILLS_DIR.name}/monsters.jpg ({len(kinds)} kinds)", flush=True)
        except subprocess.CalledProcessError as error:
            print(f"failed monsters: {error.stderr[-500:]}", flush=True)
            failures.append("monsters")
        levels = tmp / "locations"
        levels.mkdir()
        for key in ORDER:
            out = levels / f"{key}.png"
            try:
                _capture("scene=res://scenes/main.tscn", "shot=overview", f"snap={out}", "frames=900",
                         "timeout=220", "demo", f"location={key}")
                _jpeg(Image.open(out).convert("RGB"), STILLS_DIR / "levels" / f"{key}.jpg")
                print(f"still {STILLS_DIR.name}/levels/{key}.jpg", flush=True)
            except subprocess.CalledProcessError as error:
                print(f"failed {key}: {error.stderr[-500:]}", flush=True)
                failures.append(key)
    finally:
        for png in tmp.rglob("*.png"):
            png.unlink()
        (tmp / "locations").rmdir()
        tmp.rmdir()
    if failures:
        print(f"failed: {', '.join(failures)}", flush=True)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", choices=("list", "show", "all", "stills"), default=None,
                        help="list the beats, show one, print every one, render the stills; no command walks them")
    parser.add_argument("beat", nargs="?", default=None, help="`show`'s beat: a number or a key")
    parser.add_argument("--notes", action="store_true", help="add what the painter was told")
    args = parser.parse_args(argv)
    if args.command == "stills":
        return stills()
    all_beats = beats()
    total = len(all_beats)
    if args.command == "list":
        for n, beat in enumerate(all_beats, 1):
            print(f"{n:>3}  {beat.key:<22} {summary(beat)}")
        return 0
    if args.command == "show":
        if args.beat is None:
            print("`show` needs a beat: a number 1..%d or a key" % total)
            return 1
        if args.beat.isdigit() and 1 <= int(args.beat) <= total:
            index = int(args.beat) - 1
        else:
            keys = [n for n, beat in enumerate(all_beats) if beat.key == args.beat.lower()]
            if not keys:
                print(f"no beat {args.beat!r} — `list` names them")
                return 1
            index = keys[0]
        print(formatted(all_beats[index], index + 1, total, notes=args.notes))
        return 0
    if args.command == "all":
        for n, beat in enumerate(all_beats, 1):
            print(formatted(beat, n, total, notes=args.notes))
            print()
        return 0
    if args.beat is not None:
        print("a bare beat needs `show`: `show %s`" % args.beat)
        return 1
    return walk(all_beats, notes=args.notes)


if __name__ == "__main__":
    sys.exit(main())
