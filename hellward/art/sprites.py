"""Every picture the game shows, registered with the game's asset manager under a stable name.

A monster's frames come from its painted sheet in ``hellward/assets/painted/`` when there is one whose
cells match :func:`hellward.art.figures.frames`, otherwise from the low-poly stand-in, rendered once
into a cache (in parallel: forty seconds of rendering on one core) and read from there afterwards.
``HELLWARD_ART=procedural`` ignores the paintings. Towers, gates and the ground work the same way.

Names: ``mon/<kind>/<facing>/<frame>`` with the facings ``front``, ``back``, ``right``, ``left``;
``tower/<kind>/<rank>``; ``gate/<look>``; ``arch``; ``pillar``; ``ground``.
"""

from __future__ import annotations

import hashlib
import os
import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps
from saga2d import Game
from sagaforge import restyle

from hellward.art import figures, mapart, rig, structures
from hellward.art.rig import DENSITY
from hellward.sim.content import MONSTERS
from hellward.sim.level import Level

PAINTED = Path(__file__).resolve().parent.parent / "assets" / "painted"
_SOURCES = [Path(m.__file__) for m in (figures, rig, structures, mapart)]


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


def monster_sheet(kind: str) -> tuple[restyle.Sheet, dict[str, Image.Image]]:
    """The stand-in frames of one monster as a restyle sheet: a row per facing, its frames across."""
    (w, h), origin = figures.cell(kind)
    frames = figures.frames(kind)
    keys = [(f"{facing}/{frame}", {"facing": facing, "frame": frame}) for facing in figures.FACINGS for frame in frames]
    sheet = restyle.Sheet.layout(keys, cols=len(frames), cell=(w * DENSITY, h * DENSITY),
                                 origin=(origin[0] * DENSITY, origin[1] * DENSITY), scale=DENSITY)
    images = {key: figures.render(kind, tags["facing"], tags["frame"]) for key, tags in keys}
    return sheet, images


def _render_kind(kind: str, cache: Path) -> None:
    sheet, images = monster_sheet(kind)
    restyle.save_frames(_Uncut(images), sheet, cache / f"mon-{kind}")


class _Uncut:
    """Stands in for a restyle cut so :func:`restyle.save_frames` stores rendered frames as they are."""

    def __init__(self, frames: dict[str, Image.Image]) -> None:
        self.frames = frames


def _load_monster(kind: str, cache: Path) -> tuple[restyle.Sheet, dict[str, Image.Image], bool]:
    wanted = {f"{facing}/{frame}" for frame in figures.frames(kind) for facing in figures.FACINGS}
    painted = PAINTED / f"mon-{kind}"
    if not procedural() and restyle.file(painted, "json").exists():
        sheet, frames = restyle.load_frames(painted)
        if set(frames) == wanted:
            return sheet, frames, True
        warnings.warn(f"painted sheet for {kind} no longer matches its frames; drawing the stand-in")
    sheet, frames = restyle.load_frames(cache / f"mon-{kind}")
    return sheet, frames, False


def warm(cache_dir: Path) -> Path:
    """Render every missing stand-in into the cache, in parallel; returns the cache folder."""
    cache = cache_dir / f"art-{art_version()}"
    cache.mkdir(parents=True, exist_ok=True)
    missing = [k for k in MONSTERS if not restyle.file(cache / f"mon-{k}", "json").exists()]
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


def _cell(canvas: tuple[float, float], origin: tuple[float, float]) -> Cell:
    return Cell((float(canvas[0]), float(canvas[1])), (float(origin[0]), float(origin[1])))


def register(game: Game, level: Level, cache_dir: Path) -> Art:
    cache = warm(cache_dir)
    assets = game.assets
    painted: set[str] = set()
    cells: dict[str, Cell] = {}
    for kind in MONSTERS:
        sheet, frames, is_painted = _load_monster(kind, cache)
        if is_painted:
            painted.add(kind)
        cw, ch = sheet.cell
        cells[kind] = Cell((cw / DENSITY, ch / DENSITY), (sheet.origin[0] / DENSITY, sheet.origin[1] / DENSITY))
        for key, image in frames.items():
            facing, frame = key.split("/")
            if facing == "side":
                assets.image_from_pil(f"mon/{kind}/right/{frame}", image)
                assets.image_from_pil(f"mon/{kind}/left/{frame}", ImageOps.mirror(image))
            else:
                assets.image_from_pil(f"mon/{kind}/{facing}/{frame}", image)
    towers = _painted_cells("towers")
    for kind in structures.TOWER_KINDS:
        for rank in range(3):
            key = f"{kind}/{rank}"
            image = towers.get(key) if towers else None
            assets.image_from_pil(f"tower/{key}", image if image is not None else structures.tower_image(kind, rank))
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
    ground = mapart.ground(level) if not procedural() else mapart.stand_in(level)
    assets.image_from_pil("ground", ground)
    if (PAINTED / "ground.png").exists() and not procedural():
        painted.add("ground")
    return Art(cells, _cell(*structures.TOWER_CELL), _cell(*structures.GATE_CELL), _cell(*structures.ARCH_CELL),
               _cell(*structures.PILLAR_CELL), painted)


def _painted_cells(name: str) -> dict[str, Image.Image] | None:
    stem = PAINTED / name
    if procedural() or not restyle.file(stem, "json").exists():
        return None
    return restyle.load_frames(stem)[1]
