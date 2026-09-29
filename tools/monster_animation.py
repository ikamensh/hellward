"""Make and install small painted animation strips for the first three monsters.

    uv run python tools/monster_animation.py guide zombie impact /tmp/zombie --facings front_right
    # Paint /tmp/zombie/mon-zombie-impact-input.png with the existing mon-zombie.png as style reference.
    uv run python tools/monster_animation.py cut zombie impact /tmp/zombie RENDERED.png
    uv run python tools/monster_animation.py merge zombie impact /tmp/zombie
    uv run python tools/monster_animation.py guide fallen walk-full /tmp/fallen --facings back_left
    uv run python tools/monster_animation.py cut fallen walk-full /tmp/fallen RENDERED.png --unpadded --register-to APPROVED_GUIDE_STEM

``guide`` writes a 3:2 padded edit target and an unpadded guide. Use ``cut --unpadded``
when the model edited the unpadded guide instead. ``cut`` registers the result against the
guide, or against an approved painted guide with the identical manifest when ``--register-to``
is supplied. It refuses flagged cells. Inspect the transparent cut sheet before ``merge``;
the latter replaces just those keys in the installed supplemental sheet. Existing keys survive.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from sagaforge import restyle  # noqa: E402

from hellward.art import figures  # noqa: E402
from hellward.art.rig import DENSITY  # noqa: E402
from hellward.art.sprites import PAINTED  # noqa: E402

DEFAULT_FACINGS = ("front_right", "back_right", "back_left", "left", "front_left")
STRIP_FRAMES = {
    "walk": ("walk1", "walk3", "walk5", "walk7"),
    "walk-even": ("walk2", "walk4", "walk6", "walk8"),
    "walk-full": figures.ENHANCED_WALK,
    "impact": figures.HIT + figures.DEATH,
    "door": figures.STRIKE,
}
INSTALL_SUFFIX = {"walk": "bearings", "walk-even": "bearings", "walk-full": "bearings",
                  "impact": "enhanced", "door": "doors"}


def _stem(args: argparse.Namespace, stage: str) -> Path:
    return args.directory / f"mon-{args.kind}-{args.strip}-{stage}"


def _facings(args: argparse.Namespace) -> tuple[str, ...]:
    if args.facings:
        names = tuple(args.facings.split(","))
    elif args.strip in ("impact", "walk-full"):
        raise ValueError(f"{args.strip} guide needs --facings (one bearing per 8-cell sheet is recommended)")
    else:
        names = DEFAULT_FACINGS
    if len(set(names)) != len(names) or any(name not in figures.facings(args.kind) for name in names):
        raise ValueError(f"invalid or repeated facings {names}; choose from {figures.facings(args.kind)}")
    return names


def _layout(kind: str, strip: str, facings: tuple[str, ...]) -> restyle.Sheet:
    keys = [(f"{facing}/{frame}", {"facing": facing, "frame": frame})
            for facing in facings for frame in STRIP_FRAMES[strip]]
    (w, h), origin = figures.cell(kind)
    return restyle.Sheet.layout(keys, cols=3 if strip == "door" else 4,
                                cell=(w * DENSITY, h * DENSITY),
                                origin=(origin[0] * DENSITY, origin[1] * DENSITY), scale=DENSITY)


def _padded_size(size: tuple[int, int]) -> tuple[int, int]:
    w, h = size
    return (w, round(w / 1.5)) if w / h > 1.5 else (round(h * 1.5), h)


def _padded(image: Image.Image) -> Image.Image:
    w, h = image.size
    pw, ph = _padded_size(image.size)
    padded = Image.new("RGB", (pw, ph), restyle.MAGENTA)
    padded.paste(image.convert("RGB"), ((pw - w) // 2, (ph - h) // 2))
    return padded


def _unpadded(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    pw, ph = _padded_size(size)
    sx, sy = image.width / pw, image.height / ph
    x, y = (pw - size[0]) / 2 * sx, (ph - size[1]) / 2 * sy
    return image.crop((round(x), round(y), round(x + size[0] * sx), round(y + size[1] * sy)))


def _validate(sheet: restyle.Sheet, kind: str) -> None:
    (w, h), origin = figures.cell(kind)
    expected_canvas = ((w * DENSITY, h * DENSITY), (origin[0] * DENSITY, origin[1] * DENSITY), DENSITY)
    if (sheet.cell, sheet.origin, sheet.scale) != expected_canvas:
        raise ValueError(f"{kind} strip has a mismatched cell, origin or scale")
    keys = [c.key for c in sheet.cells]
    if len(keys) != len(set(keys)):
        raise ValueError("strip contains duplicate frame keys")
    allowed = {f"{f}/{frame}" for f in figures.facings(kind) for frame in figures.frames(kind)}
    unknown = set(keys) - allowed
    if unknown:
        raise ValueError(f"strip contains unknown frame keys {sorted(unknown)}")


def _load_checked(path: Path) -> tuple[restyle.Sheet, dict[str, Image.Image]]:
    sheet, frames = restyle.load_frames(path)
    with Image.open(restyle.file(path, "png")) as image:
        if image.size != sheet.size:
            raise ValueError(f"{path}: image is {image.size}, manifest expects {sheet.size}")
    return sheet, frames


def guide(args: argparse.Namespace) -> None:
    facings = _facings(args)
    sheet = _layout(args.kind, args.strip, facings)
    images = {c.key: figures.render(args.kind, c.tags["facing"], c.tags["frame"]) for c in sheet.cells}
    args.directory.mkdir(parents=True, exist_ok=True)
    stem = _stem(args, "guide")
    sheet.save(stem, images)
    input_path = restyle.file(_stem(args, "input"), "png")
    _padded(Image.open(restyle.file(stem, "png"))).save(input_path)
    print(f"{len(sheet.cells)} cells: {input_path} (3:2 edit target)")
    print(f"Reference: {restyle.file(PAINTED / f'mon-{args.kind}', 'png')}")


def cut(args: argparse.Namespace) -> None:
    sheet = restyle.Sheet.load(_stem(args, "guide"))
    _validate(sheet, args.kind)
    allowed = {f"{f}/{frame}" for f in figures.facings(args.kind) for frame in STRIP_FRAMES[args.strip]}
    if any(c.key not in allowed for c in sheet.cells):
        raise ValueError("guide has keys outside the requested strip type")
    guide_path = restyle.file(_stem(args, "guide"), "png")
    rendered = Image.open(args.rendered)
    if not args.unpadded:
        rendered = _unpadded(rendered, sheet.size)
    if args.register_to:
        approved = restyle.Sheet.load(args.register_to)
        if approved != sheet:
            raise ValueError("registration reference metadata must exactly match the guide: "
                             "cell, ground origin, scale, grid, and frame positions")
    reference_path = restyle.file(args.register_to, "png") if args.register_to else guide_path
    result = restyle.cut(sheet, rendered, Image.open(reference_path))
    for report in result.flagged:
        print(f"FLAGGED {report.key}: drift {report.drift:.1f}px, feet {report.feet_drift:.1f}px, edge {report.touches_edge}")
    if result.flagged and not args.force:
        raise ValueError(f"{len(result.flagged)} cells failed cut checks; inspect them, then rerun with --force if valid")
    stem = _stem(args, "cut")
    restyle.save_frames(result, sheet, stem)
    print(f"Saved {len(result.frames)} registered cells: {restyle.file(stem, 'png')}; flagged {len(result.flagged)}")


def merge(args: argparse.Namespace) -> None:
    sheet, incoming = _load_checked(_stem(args, "cut"))
    _validate(sheet, args.kind)
    allowed = {f"{f}/{frame}" for f in figures.facings(args.kind) for frame in STRIP_FRAMES[args.strip]}
    if incoming.keys() - allowed:
        raise ValueError("cut sheet has keys outside the requested strip type")
    destination = args.install / f"mon-{args.kind}-{INSTALL_SUFFIX[args.strip]}"
    if restyle.file(destination, "json").exists():
        existing_sheet, existing = _load_checked(destination)
        _validate(existing_sheet, args.kind)
        order = [(c.key, c.tags) for c in existing_sheet.cells]
        order.extend((c.key, c.tags) for c in sheet.cells if c.key not in existing)
        existing.update(incoming)
        incoming = existing
    else:
        order = [(c.key, c.tags) for c in sheet.cells]
    merged = restyle.Sheet.layout(order, cols=4 if args.strip == "impact" else sheet.cols,
                                 cell=sheet.cell, origin=sheet.origin, scale=sheet.scale)
    args.install.mkdir(parents=True, exist_ok=True)
    restyle.save_frames(SimpleNamespace(frames=incoming), merged, destination)
    print(f"Installed {len(sheet.cells)} cells into {restyle.file(destination, 'png')} ({len(incoming)} total)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("guide", "cut", "merge"))
    parser.add_argument("kind", choices=sorted(figures.ENHANCED))
    parser.add_argument("strip", choices=tuple(STRIP_FRAMES))
    parser.add_argument("directory", type=Path)
    parser.add_argument("rendered", type=Path, nargs="?", help="painted 3:2 sheet for cut")
    parser.add_argument("--facings", help="comma-separated bearings for guide; impact and walk-full require this")
    parser.add_argument("--install", type=Path, default=PAINTED, help="destination for merge")
    parser.add_argument("--force", action="store_true", help="accept flagged cut cells after visual inspection")
    parser.add_argument("--unpadded", action="store_true", help="rendered image edited the unpadded guide PNG")
    parser.add_argument("--register-to", type=Path, metavar="SHEET_STEM",
                        help="cut against an approved painted guide with the same cells and pivot")
    args = parser.parse_args()
    if args.command == "cut" and args.rendered is None:
        parser.error("cut requires RENDERED.png")
    if args.register_to and args.command != "cut":
        parser.error("--register-to applies only to cut")
    {"guide": guide, "cut": cut, "merge": merge}[args.command](args)


if __name__ == "__main__":
    main()
