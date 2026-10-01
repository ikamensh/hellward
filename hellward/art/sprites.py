"""Every picture the game shows, registered with the game's asset manager under a stable name.

The three enhanced monsters combine their original painted frames, optional small supplemental
paintings, and rendered guides for unpainted bearings and actions. Other monsters load a matching
painted sheet or their cached low-poly stand-ins.
``HELLWARD_ART=procedural`` ignores the paintings. Towers, gates and the ground work the same way.

Names: ``mon/<kind>/<facing>/<frame>`` with the facings ``front``, ``back``, ``right``, ``left``;
``tower/<kind>/<rank>``; ``gate/<look>``; ``arch``; ``pillar``; ``ground/<location>/<layout>`` (:func:`ground`).
"""

from __future__ import annotations

import hashlib
import os
import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps
from saga2d import Game
from sagaforge import restyle

from hellward.art import figures, mapart, puppet, rig, rigged, structures, worldmap
from hellward.art.rig import DENSITY
from hellward.sim.content import MONSTERS
from hellward.sim.campaign import Location

PAINTED = Path(__file__).resolve().parent.parent / "assets" / "painted"
_SOURCES = [Path(m.__file__) for m in (figures, rig, structures, mapart, worldmap)]


def art_version() -> str:
    digest = hashlib.sha1()
    for source in _SOURCES:
        digest.update(source.read_bytes())
    return digest.hexdigest()[:12]


def procedural() -> bool:
    return os.environ.get("HELLWARD_ART", "") == "procedural"


@dataclass(frozen=True)
class Cell:
    size: tuple[float, float]       # logical
    origin: tuple[float, float]     # logical: where the ground point sits in the image


def _monster_layout(kind: str) -> restyle.Sheet:
    (w, h), origin = figures.cell(kind)
    frames = figures.frames(kind)
    keys = [(f"{facing}/{frame}", {"facing": facing, "frame": frame}) for facing in figures.facings(kind) for frame in frames]
    return restyle.Sheet.layout(keys, cols=len(frames), cell=(w * DENSITY, h * DENSITY),
                                origin=(origin[0] * DENSITY, origin[1] * DENSITY), scale=DENSITY)


def monster_sheet(kind: str) -> tuple[restyle.Sheet, dict[str, Image.Image]]:
    """The stand-in frames of one monster as a restyle sheet: a row per facing, its frames across."""
    sheet = _monster_layout(kind)
    images = {c.key: figures.render(kind, c.tags["facing"], c.tags["frame"]) for c in sheet.cells}
    return sheet, images


def _render_kind(kind: str, cache: Path) -> None:
    sheet, images = monster_sheet(kind)
    restyle.save_frames(_Uncut(images), sheet, cache / f"mon-{kind}")


class _Uncut:
    """Stands in for a restyle cut so :func:`restyle.save_frames` stores rendered frames as they are."""

    def __init__(self, frames: dict[str, Image.Image]) -> None:
        self.frames = frames


def _load_monster(kind: str, cache: Path) -> tuple[restyle.Sheet, dict[str, Image.Image], frozenset[str]]:
    if kind in figures.ENHANCED:
        return _load_enhanced(kind, cache)
    if _painted_matches(kind):
        sheet, frames = restyle.load_frames(PAINTED / f"mon-{kind}")
        return sheet, frames, _registered_keys(frames)
    if not procedural() and restyle.file(PAINTED / f"mon-{kind}", "json").exists():
        warnings.warn(f"painted sheet for {kind} no longer matches its frames; drawing the stand-in")
    sheet, frames = restyle.load_frames(cache / f"mon-{kind}")
    return sheet, frames, frozenset()


def _registered_keys(frames: dict[str, Image.Image]) -> frozenset[str]:
    """Legacy ``side`` paint is registered as both true game-facing names."""
    keys: set[str] = set()
    for key in frames:
        facing, frame = key.split("/")
        if facing == "side":
            keys.update((f"right/{frame}", f"left/{frame}"))
        else:
            keys.add(key)
    return frozenset(keys)


def _load_checked(path: Path) -> tuple[restyle.Sheet, dict[str, Image.Image]]:
    """Reject a sheet whose image size disagrees with its manifest before cells are cropped."""
    sheet, frames = restyle.load_frames(path)
    with Image.open(restyle.file(path, "png")) as image:
        if image.size != sheet.size:
            raise ValueError(f"{path}: painted image is {image.size}, manifest expects {sheet.size}")
    return sheet, frames


def _in_canvas(image: Image.Image, source: restyle.Sheet, target: restyle.Sheet) -> Image.Image:
    """Place an old painted cell on the new common canvas by its physical ground pivot."""
    if source.scale != target.scale:
        raise ValueError(f"painted monster scale {source.scale} != {target.scale}")
    x = round(target.origin[0] - source.origin[0])
    y = round(target.origin[1] - source.origin[1])
    if x < 0 or y < 0 or x + image.width > target.cell[0] or y + image.height > target.cell[1]:
        raise ValueError("painted monster cell does not fit its enhanced canvas")
    canvas = Image.new("RGBA", target.cell)
    canvas.alpha_composite(image, (x, y))
    return canvas


def _painted_enhanced(kind: str) -> tuple[restyle.Sheet, dict[str, Image.Image]]:
    """Resolve approved base and supplemental paintings without rendering guides."""
    sheet = _monster_layout(kind)
    expected = {c.key for c in sheet.cells}
    frames: dict[str, Image.Image] = {}
    base = PAINTED / f"mon-{kind}"
    if restyle.file(base, "json").exists():
        old_sheet, old = _load_checked(base)
        expected_old = {f"{f}/{frame}" for f in figures.FACINGS for frame in figures.WALK + figures.STRIKE}
        if len(old_sheet.cells) != len(old) or set(old) != expected_old:
            raise ValueError(f"{base}: expected the original 21 front/back/side walk and attack keys")
        # The old painted four-step cycle becomes an eight-step hold cycle. It remains painterly
        # throughout, while an as-yet-unpainted octant uses one coherent procedural walk clip.
        for facing in ("front", "back", "right"):
            source_facing = "side" if facing == "right" else facing
            for i, frame in enumerate(figures.walk(kind)):
                source = f"{source_facing}/walk{i // 2 + 1}"
                key = f"{facing}/{frame}"
                frames[key] = _in_canvas(old[source], old_sheet, sheet)
            for frame in figures.STRIKE:
                key = f"{facing}/{frame}"
                frames[key] = _in_canvas(old[f"{source_facing}/{frame}"], old_sheet, sheet)
    supplied: set[str] = set()
    for suffix in ("enhanced", "bearings", "doors"):
        supplemental = PAINTED / f"mon-{kind}-{suffix}"
        if not restyle.file(supplemental, "json").exists():
            continue
        extra_sheet, extra = _load_checked(supplemental)
        if len(extra_sheet.cells) != len(extra):
            raise ValueError(f"{supplemental}: duplicate frame keys")
        if extra_sheet.cell != sheet.cell or extra_sheet.origin != sheet.origin or extra_sheet.scale != sheet.scale:
            raise ValueError(f"{supplemental}: cell, origin and scale must match the enhanced monster sheet")
        unknown = extra.keys() - expected
        if unknown:
            raise ValueError(f"{supplemental}: unknown frame keys {sorted(unknown)}")
        repeated = extra.keys() & supplied
        if repeated:
            raise ValueError(f"{supplemental}: duplicate supplemental frame keys {sorted(repeated)}")
        frames.update(extra)
        supplied.update(extra)
        # Hold the four painted contacts and passing poses between their keys instead of
        # interleaving them with flat procedural frames. That keeps every walk clip one style.
        for facing in figures.facings(kind):
            walk_keys = [f"{facing}/{frame}" for frame in figures.walk(kind)]
            given = [i for i, key in enumerate(walk_keys) if key in extra]
            if not given:
                continue
            for i, key in enumerate(walk_keys):
                if key in frames:
                    continue
                nearest = min(given, key=lambda j: min((i - j) % len(walk_keys), (j - i) % len(walk_keys)))
                frames[key] = extra[walk_keys[nearest]]
    return sheet, frames


def _load_enhanced(kind: str, cache: Path) -> tuple[restyle.Sheet, dict[str, Image.Image], frozenset[str]]:
    if procedural():
        sheet, frames = restyle.load_frames(cache / f"mon-{kind}")
        return sheet, frames, frozenset()
    sheet, painted = _painted_enhanced(kind)
    if len(painted) == len(sheet.cells):
        return sheet, painted, frozenset(painted)
    _, frames = restyle.load_frames(cache / f"mon-{kind}")
    frames.update(painted)
    return sheet, frames, frozenset(painted)


def _painted_matches(kind: str) -> bool:
    if kind in figures.ENHANCED:
        return False
    stem = PAINTED / f"mon-{kind}"
    if procedural() or not restyle.file(stem, "json").exists():
        return False
    wanted = {f"{facing}/{frame}" for frame in figures.frames(kind) for facing in figures.facings(kind)}
    return {c.key for c in restyle.Sheet.load(stem).cells} == wanted


def _needs_render(kind: str, cache: Path) -> bool:
    if restyle.file(cache / f"mon-{kind}", "json").exists():
        return False
    if kind in figures.ENHANCED and not procedural():
        sheet, painted = _painted_enhanced(kind)
        return len(painted) != len(sheet.cells)
    return not _painted_matches(kind)


def warm(cache_dir: Path, *, skip: frozenset[str] = frozenset()) -> Path:
    """Render every missing stand-in the paintings do not replace into the cache, in parallel; returns the folder."""
    cache = cache_dir / f"art-{art_version()}"
    cache.mkdir(parents=True, exist_ok=True)
    missing = [kind for kind in MONSTERS if kind not in skip and _needs_render(kind, cache)]
    if missing:
        with ProcessPoolExecutor(min(len(missing), os.cpu_count() or 4)) as pool:
            list(pool.map(_render_kind, missing, [cache] * len(missing)))
    return cache


@dataclass
class Art:
    monster: dict[str, Cell]
    tower: Cell
    gate: Cell
    arch: Cell
    pillar: Cell
    painted: set[str]
    monster_painted: dict[str, frozenset[str]]  # registered facing/frame names resolved from paintings
    rigged: frozenset[str]             # kinds with a baked 3D alternative registered
    monster_style: str                 # painted, puppet, mixed, or rigged; fixed when the game loads art
    puppets: frozenset[str] = frozenset()


def _cell(canvas: tuple[float, float], origin: tuple[float, float]) -> Cell:
    return Cell((float(canvas[0]), float(canvas[1])), (float(origin[0]), float(origin[1])))


def _tower_outline(image: Image.Image) -> Image.Image:
    """Separate a tower's silhouette from detailed ground at gameplay scale."""
    image = image.convert("RGBA")
    solid = image.getchannel("A").point(lambda alpha: 255 if alpha >= 96 else 0)
    dark = Image.new("RGBA", image.size, (20, 16, 18, 0))
    dark.putalpha(solid.filter(ImageFilter.MaxFilter(7)).point(lambda alpha: alpha * 190 // 255))
    light = Image.new("RGBA", image.size, (230, 204, 156, 0))
    light.putalpha(solid.filter(ImageFilter.MaxFilter(3)).point(lambda alpha: alpha * 165 // 255))
    return Image.alpha_composite(Image.alpha_composite(dark, light), image)


def register(game: Game, cache_dir: Path) -> Art:
    assets = game.assets
    style = os.environ.get("HELLWARD_MONSTER_STYLE", "painted")
    if style not in {"painted", "mixed", "rigged", "puppet"}:
        raise ValueError(f"HELLWARD_MONSTER_STYLE must be painted, mixed, rigged, or puppet; got {style!r}")
    if procedural():
        style = "painted"
    puppet_kinds = frozenset(puppet.KINDS) if style == "puppet" else frozenset()
    cache = warm(cache_dir, skip=puppet_kinds)
    if puppet_kinds:
        puppet.register(game, puppet.KINDS)
    painted: set[str] = set()
    monster_painted: dict[str, frozenset[str]] = {}
    cells: dict[str, Cell] = {}
    for kind in MONSTERS:
        if kind in puppet_kinds:
            cells[kind] = _cell(*figures.cell(kind))
            monster_painted[kind] = frozenset()
            painted.add(kind)
            continue
        sheet, frames, provenance = _load_monster(kind, cache)
        monster_painted[kind] = provenance
        if provenance:
            painted.add(kind)
        cw, ch = sheet.cell
        cells[kind] = Cell((cw / DENSITY, ch / DENSITY), (sheet.origin[0] / DENSITY, sheet.origin[1] / DENSITY))
        for key, image in frames.items():
            facing, frame = key.split("/")
            if kind in figures.ENHANCED:
                assets.image_from_pil(f"mon/{kind}/{facing}/{frame}", image)
            elif facing == "side":
                assets.image_from_pil(f"mon/{kind}/right/{frame}", image)
                assets.image_from_pil(f"mon/{kind}/left/{frame}", ImageOps.mirror(image))
            else:
                assets.image_from_pil(f"mon/{kind}/{facing}/{frame}", image)
    rigged_kinds: set[str] = set()
    if style in {"mixed", "rigged"}:
        for kind in rigged.KINDS:
            layout, images = rigged.load(kind)
            if (layout.cell, layout.origin) != (
                (round(cells[kind].size[0] * DENSITY), round(cells[kind].size[1] * DENSITY)),
                (cells[kind].origin[0] * DENSITY, cells[kind].origin[1] * DENSITY),
            ):
                raise ValueError(f"{kind}: rigged and painted cells have different ground pivots")
            for key, image in images.items():
                assets.image_from_pil(f"mon3d/{kind}/{key}", image)
            rigged_kinds.add(kind)
    towers = _painted_cells("towers")
    for kind in structures.TOWER_KINDS:
        for rank in range(3):
            key = f"{kind}/{rank}"
            image = towers.get(key) if towers else None
            source = image if image is not None else structures.tower_image(kind, rank)
            assets.image_from_pil(f"tower/{key}", _tower_outline(source))
    if towers:
        painted.add("towers")
    gates = _painted_cells("gates")
    for look in structures.GATE_LOOKS:
        image = gates.get(look) if gates else None
        assets.image_from_pil(f"gate/{look}", image if image is not None else structures.gate_image(look))
    standing = _painted_cells("structures") or {}
    assets.image_from_pil("arch", standing.get("arch") or structures.arch_image())
    assets.image_from_pil("pillar", standing.get("pillar") or structures.pillar_image())
    if standing:
        painted.add("structures")
    title = PAINTED / "title.jpg"
    if title.exists():
        image = Image.open(title).convert("RGB")
        width = 1280 * DENSITY
        height = round(image.height * width / image.width)
        image = image.resize((width, height), Image.LANCZOS)
        top = (height - 800 * DENSITY) // 2
        assets.image_from_pil("title", image.crop((0, top, width, top + 800 * DENSITY)))
    assets.image_from_pil("worldmap", worldmap.picture(act=1))
    assets.image_from_pil("worldmap-2", worldmap.picture(act=2))
    return Art(cells, _cell(*structures.TOWER_CELL), _cell(*structures.GATE_CELL), _cell(*structures.ARCH_CELL),
               _cell(*structures.PILLAR_CELL), painted, monster_painted, frozenset(rigged_kinds), style, puppet_kinds)


def ground(game: Game, location: Location) -> str:
    """Register a location's floor the first time a defence there begins; its image name."""
    name = f"ground/{location.key}/{mapart.layout_fingerprint(location.level)}"
    if not game.assets.has_image(name):
        level = location.level
        theme = mapart.THEMES[location.theme]
        image = mapart.stand_in(level, theme) if procedural() else mapart.ground(location.key, level, theme)
        game.assets.image_from_pil(name, image)
    return name


def _painted_cells(name: str) -> dict[str, Image.Image] | None:
    stem = PAINTED / name
    if procedural() or not restyle.file(stem, "json").exists():
        return None
    return restyle.load_frames(stem)[1]
