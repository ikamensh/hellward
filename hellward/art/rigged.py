"""Baked, articulated 3D sprites for the Skeleton and Zombie comparison.

The offline bake rebuilds one mesh from its joint pose for every bearing and
frame. Runtime only loads RGBA cells; it never renders a mesh during battle.
The baked cells deliberately share the painted sheet's ground point and size.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from PIL import Image
from sagaforge import render3d as r3, restyle

from hellward.art import figures
from hellward.art.rig import DENSITY, PROJECTION, yaw

KINDS = ("skeleton", "zombie")
WALK = tuple(f"walk{i}" for i in range(1, 17))
FRAMES = WALK + figures.STRIKE + figures.HIT + figures.DEATH
ASSETS = Path(__file__).resolve().parent.parent / "assets" / "rigged"
_YAW = dict(zip(figures.ENHANCED_FACINGS, (0, -45, -90, -135, 180, 135, 90, 45)))


def sheet(kind: str) -> restyle.Sheet:
    if kind not in KINDS:
        raise ValueError(f"no baked 3D rig for {kind}")
    (width, height), (ox, oy) = figures.cell(kind)
    keys = [(f"{facing}/{frame}", {"facing": facing, "frame": frame})
            for facing in figures.facings(kind) for frame in FRAMES]
    return restyle.Sheet.layout(keys, cols=16, cell=(width * DENSITY, height * DENSITY),
                                origin=(ox * DENSITY, oy * DENSITY), scale=DENSITY)


def _effective(pose: figures.Pose, name: str) -> float:
    value = getattr(pose, name)
    if value is not None:
        return float(value)
    if name == "left_leg":
        return -pose.leg
    if name == "left":
        return -pose.arm
    return pose.arm


def _between(first: figures.Pose, second: figures.Pose) -> figures.Pose:
    """Halfway joint pose, with implicit opposing limbs made explicit."""
    values: dict[str, float | int | None] = {}
    for field in fields(figures.Pose):
        name = field.name
        if name == "death":
            values[name] = 0
        elif name in ("left_leg", "left", "right"):
            values[name] = (_effective(first, name) + _effective(second, name)) / 2
        else:
            values[name] = (getattr(first, name) + getattr(second, name)) / 2
    return figures.Pose(**values)


def render(kind: str, facing: str, frame: str) -> Image.Image:
    """Render an action from the common 3D body into its fixed transparent cell."""
    if kind not in KINDS or facing not in figures.facings(kind) or frame not in FRAMES:
        raise ValueError(f"unknown baked 3D frame {kind}/{facing}/{frame}")
    if not frame.startswith("walk"):
        return figures.render(kind, facing, frame)
    index = int(frame[4:]) - 1
    base = index // 2
    if index % 2 == 0:
        return figures.render(kind, facing, figures.walk(kind)[base])
    old_walk = figures.walk(kind)
    pose = _between(figures.pose_of(kind, old_walk[base]),
                    figures.pose_of(kind, old_walk[(base + 1) % len(old_walk)]))
    mesh = r3.scale(yaw(figures.BUILDERS[kind](pose), _YAW[facing]), figures.SCALE)
    size, origin = figures.cell(kind)
    return r3.render(mesh, PROJECTION, scale=DENSITY, canvas=size, origin=origin)


@dataclass
class _Rendered:
    frames: dict[str, Image.Image]


def bake(kind: str, destination: Path = ASSETS) -> Path:
    """Export every direction and action into a committed RGBA sprite sheet."""
    layout = sheet(kind)
    images = {cell.key: render(kind, cell.tags["facing"], cell.tags["frame"])
              for cell in layout.cells}
    destination.mkdir(parents=True, exist_ok=True)
    stem = destination / f"mon-{kind}"
    restyle.save_frames(_Rendered(images), layout, stem)
    return stem


def load(kind: str) -> tuple[restyle.Sheet, dict[str, Image.Image]]:
    """Reject incomplete or misregistered bakes before asset registration."""
    expected = sheet(kind)
    stem = ASSETS / f"mon-{kind}"
    actual, images = restyle.load_frames(stem)
    if (actual.cell, actual.origin, actual.scale) != (expected.cell, expected.origin, expected.scale):
        raise ValueError(f"{stem}: 3D bake no longer shares the monster canvas and ground point")
    if len(actual.cells) != len(expected.cells) or {cell.key for cell in actual.cells} != {cell.key for cell in expected.cells}:
        raise ValueError(f"{stem}: 3D bake has missing or unexpected frames")
    with Image.open(restyle.file(stem, "png")) as image:
        if image.size != actual.size:
            raise ValueError(f"{stem}: atlas dimensions do not match the manifest")
    if any(image.getbbox() is None for image in images.values()):
        raise ValueError(f"{stem}: a 3D frame is empty")
    return actual, images
