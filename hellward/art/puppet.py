"""Painted 2.5D characters: fixed skins articulated by continuous motion curves.

Author one bind pose per bearing. Pixels are assigned to overlapping bone parts,
then the same parts supply walk, impact and collapse. Preparing the textures is
an offline operation; joint motion runs through the engine's retained sprites.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops

from hellward.art import figures
from hellward.art.rig import DENSITY

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "puppet"
KINDS = ("fallen", "skeleton", "zombie")
CYCLE = {"fallen": 0.64, "skeleton": 0.60, "zombie": 0.38}
HIT_LIFE = 0.30
DEATH_LIFE = {"fallen": 1.15, "skeleton": 1.45, "zombie": 1.70}
BEARINGS = dict(zip(figures.ENHANCED_FACINGS,
                    ((0, 1), (0.707, 0.707), (1, 0), (0.707, -0.707),
                     (0, -1), (-0.707, -0.707), (-1, 0), (-0.707, 0.707))))
BONES = {
    "torso": ("root", "neck"), "head": ("neck", "crown"),
    "r_upper_arm": ("r_shoulder", "r_elbow"), "r_forearm": ("r_elbow", "r_wrist"),
    "l_upper_arm": ("l_shoulder", "l_elbow"), "l_forearm": ("l_elbow", "l_wrist"),
    "r_thigh": ("r_hip", "r_knee"), "r_shin": ("r_knee", "r_ankle"),
    "l_thigh": ("l_hip", "l_knee"), "l_shin": ("l_knee", "l_ankle"),
    "cloth": ("root", "hem"),
}


@dataclass
class Rig:
    joints: dict[str, np.ndarray]
    order: tuple[str, ...]
    scale: float
    origin: np.ndarray


@dataclass
class Skin:
    rig: Rig
    parts: dict[str, Image.Image]


@dataclass
class Part:
    """A bone-aligned texture; UV center and length remain in source coordinates."""
    image: Image.Image
    center: np.ndarray
    length: float


@dataclass
class Transform:
    center: tuple[float, float]
    size: tuple[float, float]
    rotation: float


Endpoints = dict[str, tuple[np.ndarray, np.ndarray]]


def _polygon(size: tuple[int, int], points) -> np.ndarray:
    mask = Image.new("L", size)
    ImageDraw.Draw(mask).polygon([tuple(point) for point in points], fill=255)
    return np.asarray(mask) > 0


@lru_cache(maxsize=24)
def rig(kind: str, facing: str) -> Rig:
    data = _definition(kind)
    view = data["views"][facing]
    return Rig({key: np.array(point, dtype=float) for key, point in view["joints"].items()},
               tuple(view["order"]), data["height"] / view["height"],
               np.array(view["ground"], dtype=float))


@lru_cache(maxsize=3)
def _definition(kind: str) -> dict:
    return json.loads((ASSETS / f"{kind}-rig.json").read_text())


@lru_cache(maxsize=24)
def skin(kind: str, facing: str) -> Skin:
    data = _definition(kind)
    view = data["views"][facing]
    with Image.open(ASSETS / data["image"]) as source:
        image = source.convert("RGBA").crop(tuple(view["crop"]))
    joints = rig(kind, facing).joints
    yy, xx = np.mgrid[:image.height, :image.width]
    pixels = np.stack((xx, yy), axis=-1)
    names = tuple(BONES)
    scores = []
    for name, (a, b) in BONES.items():
        start, end = joints[a], joints[b]
        vector = end - start
        t = np.clip(np.sum((pixels - start) * vector, axis=-1) / np.dot(vector, vector), 0, 1)
        closest = start + t[:, :, None] * vector
        scores.append(np.sum((pixels - closest) ** 2, axis=-1))
    labels = np.argmin(np.stack(scores), axis=0)
    rgba = np.array(image)
    red_skin = (rgba[:, :, 0].astype(float) > rgba[:, :, 1] * 1.65) & (rgba[:, :, 0].astype(float) > rgba[:, :, 2] * 1.65)
    for name, polygons in view["regions"].items():
        for polygon in polygons:
            region = _polygon(image.size, polygon)
            # The Fallen's frayed skirt and crescent blade overlap its red legs.
            # Keep the exposed flesh attached to the leg rather than the cloth.
            if kind == "fallen" and name == "cloth":
                region &= ~red_skin
            elif kind == "fallen" and name == "r_forearm":
                region &= ~red_skin | (yy < joints["r_wrist"][1] + 35)
            labels[region] = names.index(name)
    alpha = np.array(image.getchannel("A"))
    alpha[alpha < 12] = 0
    image.putalpha(Image.fromarray(alpha))
    parts = {}
    for index, name in enumerate(names):
        # Overlap joint edges with the existing paint. This exposes no artificial
        # flat-color caps when one bone rotates relative to its neighbor.
        mask = Image.fromarray(np.where(labels == index, 255, 0).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))
        part = image.copy()
        part.putalpha(Image.fromarray(np.minimum(np.array(mask), alpha)))
        parts[name] = part
    for target, definition in view.get("copies", {}).items():
        if isinstance(definition, str):
            original, donor = definition, None
        else:
            original = definition["bone"]
            donor = skin(kind, definition["view"])
        donor_parts, donor_joints = (parts, joints) if donor is None else (donor.parts, donor.rig.joints)
        a, b = BONES[original]
        ta, tb = BONES[target]
        copied = _affine(donor_parts[original], donor_joints[a], donor_joints[b], joints[ta], joints[tb])
        parts[target] = ImageEnhance.Brightness(copied).enhance(0.80)
    return Skin(rig(kind, facing), parts)


def _affine(part: Image.Image, start: np.ndarray, end: np.ndarray,
            target_start: np.ndarray, target_end: np.ndarray) -> Image.Image:
    source_vector, target_vector = end - start, target_end - target_start
    length = np.linalg.norm(source_vector)
    source_axis = source_vector / length
    target_length = np.linalg.norm(target_vector)
    target_axis = target_vector / target_length
    source_basis = np.column_stack((source_axis, (-source_axis[1], source_axis[0])))
    target_basis = np.column_stack((target_axis * target_length / length,
                                    (-target_axis[1], target_axis[0])))
    matrix = target_basis @ source_basis.T
    inverse = np.linalg.inv(matrix)
    offset = start - inverse @ target_start
    return part.transform(part.size, Image.Transform.AFFINE,
                          (inverse[0, 0], inverse[0, 1], offset[0],
                           inverse[1, 0], inverse[1, 1], offset[1]), Image.Resampling.BICUBIC)


@lru_cache(maxsize=264)
def part(kind: str, facing: str, name: str) -> Part:
    """Prepare a trimmed texture with its bone pointing down the image Y axis."""
    source = skin(kind, facing)
    a, b = BONES[name]
    start, end = source.rig.joints[a], source.rig.joints[b]
    vector = end - start
    length = float(np.linalg.norm(vector))
    axis = vector / length
    cross = np.array((axis[1], -axis[0]))
    basis = np.column_stack((cross, axis))
    bounds = source.parts[name].getbbox()
    if bounds is None:
        raise ValueError(f"{kind}/{facing}/{name}: no painted pixels assigned to bone")
    left, top, right, bottom = bounds
    corners = np.array(((left, top), (right, top), (right, bottom), (left, bottom)))
    uv = (corners - start) @ basis
    low, high = np.floor(uv.min(axis=0)) - 6, np.ceil(uv.max(axis=0)) + 6
    offset = start + basis @ low
    size = tuple(int(value) for value in high - low)
    image = source.parts[name].transform(size, Image.Transform.AFFINE,
        (basis[0, 0], basis[0, 1], offset[0], basis[1, 0], basis[1, 1], offset[1]),
        Image.Resampling.BICUBIC)
    image = image.resize((max(1, round(size[0] * source.rig.scale)),
                          max(1, round(size[1] * source.rig.scale))), Image.Resampling.LANCZOS)
    alpha = image.getchannel("A")
    edge = ImageChops.subtract(alpha.filter(ImageFilter.MaxFilter(3)), alpha)
    outline = Image.new("RGBA", image.size, (22, 15, 17, 0))
    outline.putalpha(edge.point(lambda value: value * 180 // 255))
    image = Image.alpha_composite(outline, image)
    return Part(image, (low + high) * 0.5, length)


def transform(kind: str, facing: str, name: str, start: np.ndarray, end: np.ndarray) -> Transform:
    source, texture = rig(kind, facing), part(kind, facing, name)
    vx, vy = float(end[0] - start[0]), float(end[1] - start[1])
    length = math.hypot(vx, vy)
    ax, ay = vx / length, vy / length
    ratio = length / texture.length
    width = _width(kind, name)
    cx = float(start[0]) + ay * float(texture.center[0]) * width + ax * float(texture.center[1]) * ratio
    cy = float(start[1]) - ax * float(texture.center[0]) * width + ay * float(texture.center[1]) * ratio
    scale = source.scale / DENSITY
    return Transform(((cx - float(source.origin[0])) * scale, (cy - float(source.origin[1])) * scale),
                     (texture.image.width * width / DENSITY, texture.image.height * ratio / DENSITY),
                     math.degrees(math.atan2(-ax, ay)))


def _width(kind: str, name: str) -> float:
    return {"head": 1.36, "torso": 1.22}.get(name, 1.05) if kind == "skeleton" else 1.0


def register(game, kinds: tuple[str, ...]) -> None:
    for kind in kinds:
        for facing in figures.facings(kind):
            for name in BONES:
                game.assets.image_from_pil(f"puppet/{kind}/{facing}/{name}", part(kind, facing, name).image)
    # Full-resolution masks are only needed during texture preparation.
    skin.cache_clear()


def walk_joints(kind: str, facing: str, phase: float, source: Rig) -> dict[str, np.ndarray]:
    rest = source.joints
    points = {key: point.copy() for key, point in rest.items()}
    forward = np.array(BEARINGS[facing], dtype=float)
    # A stride contains two contacts. Half of the distance is travelled during
    # each planted interval; a passing foot follows a raised return arc.
    stride = CYCLE[kind] * 48 * DENSITY * 0.5 / source.scale
    bob = {"fallen": 10.0, "skeleton": 4.0, "zombie": 2.0}[kind] * math.cos(phase * math.tau * 2)
    sway = {"fallen": 3.0, "skeleton": 1.5, "zombie": 5.0}[kind]
    upper = np.array((sway * math.sin(phase * math.tau), bob))
    for key in ("root", "neck", "crown", "r_shoulder", "l_shoulder", "r_hip", "l_hip", "hem"):
        points[key] += upper
    for side, shift in (("r", 0.0), ("l", 0.5)):
        p = (phase + shift) % 1.0
        contact = 0.64 if kind == "zombie" else 0.55
        planted = p < contact
        t = p / contact if planted else (p - contact) / (1 - contact)
        travel = (0.5 - t) * stride if planted else -math.cos(t * math.pi) * stride * 0.5
        lift_height = {"fallen": 29.0, "skeleton": 25.0, "zombie": 15.0}[kind]
        if kind == "zombie" and side == "l":
            lift_height = 5.0
            travel *= 0.65
        lift = 0.0 if planted else lift_height * math.sin(math.pi * t)
        projected = forward * (1.0, 0.50)
        ankle = rest[f"{side}_ankle"] + projected * travel + (0, -lift)
        points[f"{side}_ankle"] = ankle
        hip = points[f"{side}_hip"]
        rest_mid = (rest[f"{side}_hip"] + rest[f"{side}_ankle"]) * 0.5
        bend = rest[f"{side}_knee"] - rest_mid
        points[f"{side}_knee"] = (hip + ankle) * 0.5 + bend + forward * lift * 0.25
        arm_phase = math.cos((phase + shift) * math.tau)
        strength = {"fallen": 35.0, "skeleton": 18.0, "zombie": 10.0}[kind]
        if kind == "skeleton" and side == "l":
            strength = 6.0  # the shield stays guarded
        points[f"{side}_elbow"] = rest[f"{side}_elbow"] + upper - forward * arm_phase * strength * 0.4
        points[f"{side}_wrist"] = rest[f"{side}_wrist"] + upper - forward * arm_phase * strength
    points["hem"] += (3 * math.sin(phase * math.tau - 0.7), 0)
    if kind == "skeleton":
        points["crown"] = points["neck"] + (points["crown"] - points["neck"]) * 1.28
    elif kind == "zombie":
        points["crown"] += (4 * math.sin(phase * math.tau - 0.8), 1)
    return points


def _rotate(point: np.ndarray, pivot: np.ndarray, degrees: float) -> np.ndarray:
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    x, y = point - pivot
    return pivot + (c * x - s * y, s * x + c * y)


def _curve(time: float, keys: tuple[tuple[float, float], ...]) -> float:
    if time <= keys[0][0]:
        return keys[0][1]
    for (a, av), (b, bv) in zip(keys, keys[1:]):
        if time <= b:
            t = (time - a) / (b - a)
            return av + (bv - av) * t * t * (3 - 2 * t)
    return keys[-1][1]


def live_pose(kind: str, facing: str, distance: float, *, hit: float = -1.0,
              attack: float = -1.0) -> Endpoints:
    """Add reactions to the current gait rather than switching to a new body."""
    source = rig(kind, facing)
    points = walk_joints(kind, facing, distance / CYCLE[kind] if attack < 0 else 0.23, source)
    forward = BEARINGS[facing]
    side = forward[0] if abs(forward[0]) > 0.1 else 1.0
    upper = ("neck", "crown", "r_shoulder", "l_shoulder", "r_elbow", "l_elbow", "r_wrist", "l_wrist", "hem")
    if attack >= 0:
        phase = (attack * 1.2) % 1.0
        wind = _curve(phase, ((0, 0), (0.38, 1), (0.53, -1), (0.72, 0), (1, 0)))
        lean = _curve(phase, ((0, 0), (0.38, -0.4), (0.54, 1), (0.78, 0), (1, 0)))
        for name in upper:
            points[name] = _rotate(points[name], points["root"], 8 * side * lean)
        amplitude = {"fallen": 80, "skeleton": 95, "zombie": 70}[kind]
        for limb in (("r", "l") if kind == "zombie" else ("r",)):
            pivot = points[f"{limb}_shoulder"]
            points[f"{limb}_elbow"] = _rotate(points[f"{limb}_elbow"], pivot, amplitude * side * wind)
            points[f"{limb}_wrist"] = _rotate(points[f"{limb}_wrist"], pivot, amplitude * side * wind)
            points[f"{limb}_wrist"] = _rotate(points[f"{limb}_wrist"], points[f"{limb}_elbow"], -22 * side * wind)
    if hit >= 0:
        recoil = _curve(hit, ((0, 0), (0.055, 1), (0.13, 0.65), (HIT_LIFE, 0)))
        lean = {"fallen": 21, "skeleton": 18, "zombie": 16}[kind]
        for name in upper:
            points[name] = _rotate(points[name], points["root"], -lean * side * recoil)
        points["crown"] = _rotate(points["crown"], points["neck"], -14 * side * recoil)
        points["r_wrist"] = _rotate(points["r_wrist"], points["r_elbow"], 22 * side * recoil)
        points["l_wrist"] = _rotate(points["l_wrist"], points["l_elbow"], 15 * side * recoil)
    return {name: (points[a], points[b]) for name, (a, b) in BONES.items()}


def _center(kind: str, facing: str, name: str, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    texture = part(kind, facing, name)
    vector = b - a
    length = np.linalg.norm(vector)
    axis = vector / length
    cross = np.array((axis[1], -axis[0]))
    return a + cross * texture.center[0] * _width(kind, name) + axis * texture.center[1] * length / texture.length


def death_pose(kind: str, facing: str, initial: Endpoints, time: float, fall: int) -> Endpoints:
    """Bone scatter, quick imp topple, and a delayed heavy corpse collapse."""
    source = rig(kind, facing)
    floor = (source.joints["r_ankle"][1] + source.joints["l_ankle"][1]) * 0.5 + 10
    root = source.joints["root"]
    target_root = np.array((root[0], floor - 25))
    result = {}
    scatter = {
        "head": (-76, -13, 105), "torso": (0, -7, -85), "cloth": (9, -5, 85),
        "r_upper_arm": (48, -7, 74), "r_forearm": (72, -3, -83),
        "l_upper_arm": (-42, -5, -100), "l_forearm": (-31, -17, 65),
        "r_thigh": (20, 5, 68), "r_shin": (38, 12, -72),
        "l_thigh": (-14, 5, -78), "l_shin": (-45, 11, 89),
    }
    for index, (name, (a, b)) in enumerate(initial.items()):
        texture = part(kind, facing, name)
        start_center = _center(kind, facing, name, a, b)
        start_vector = b - a
        start_length = float(np.linalg.norm(start_vector))
        start_angle = math.degrees(math.atan2(-start_vector[0], start_vector[1]))
        if kind == "skeleton":
            delay = 0.055 + 0.015 * (index % 4)
            t = min(1.0, max(0.0, (time - delay) / 0.40))
            dx, dy, angle = scatter[name]
            target = np.array((root[0] + dx * fall, floor + dy))
            target_angle = angle * fall
            target_length = start_length * (0.55 if name == "torso" else 0.88 if name != "head" else 1.0)
            arc = 30 if name == "head" else 12
        else:
            duration = 0.47 if kind == "fallen" else 0.76
            t = min(1.0, max(0.0, time / duration))
            turn = (77 if kind == "fallen" else -86) * fall
            relative = _rotate(start_center, root, turn) - root
            target = target_root + relative * (0.75, 0.22)
            target_angle = start_angle + turn
            target_length = start_length * (0.65 if name in ("torso", "cloth") else 0.88 if name != "head" else 1.0)
            if "shin" in name or "thigh" in name:
                target_angle += (28 if "l_" in name else -24) * fall
            arc = 0
        ease = t * t * (3 - 2 * t)
        center = start_center + (target - start_center) * ease
        center[1] -= arc * math.sin(math.pi * t)
        difference = (target_angle - start_angle + 180) % 360 - 180
        angle = math.radians(start_angle + difference * ease)
        axis = np.array((-math.sin(angle), math.cos(angle)))
        cross = np.array((axis[1], -axis[0]))
        length = start_length + (target_length - start_length) * ease
        start = center - cross * texture.center[0] * _width(kind, name) - axis * texture.center[1] * length / texture.length
        result[name] = (start, start + axis * length)
    return result

