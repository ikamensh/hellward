"""The monsters as posed low-poly figures: guides and fallbacks for the painted sprites.

Fallen, skeletons and zombies have eight bearings and their own walk, hit and death poses. The other
monsters retain the original three-bearing, four-step walk. Poses are pushed past realistic so they
read at 30–80 px.

:func:`mesh` builds one frame; :func:`render` rasterises it into a cell whose feet sit on
:func:`cell` 's origin. Flyers are drawn hovering: their cell's origin is still the ground point.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import math

from PIL import Image
from sagaforge import render3d as r3
from sagaforge.render3d import Mesh

from hellward.art.rig import DENSITY, PROJECTION, blade, move, pitch, rod, roll, wing, yaw
from hellward.sim.content import MONSTERS

FACINGS = ("front", "back", "side")
WALK = ("walk1", "walk2", "walk3", "walk4")
ENHANCED = frozenset(("fallen", "skeleton", "zombie"))
ENHANCED_FACINGS = ("front", "front_right", "right", "back_right", "back", "back_left", "left", "front_left")
ENHANCED_WALK = tuple(f"walk{i}" for i in range(1, 9))
HIT = ("hit1", "hit2", "hit3")
DEATH = ("death1", "death2", "death3", "death4", "death5")
STRIKE = ("wind", "strike", "recover")
CAST = ("raise", "chant")
STRIDE = 0.2          # tiles walked per walk frame
SCALE = 2.0           # figures stand about twice life size on the tile grid: the camera shows height at 57%, and they must read at 1x
# The painted sheets use these shared canvases. Keep the feet fixed even when a pose changes.
ENHANCED_CELLS = {
    "fallen": ((104, 117), (52.0, 70.4387296736308)),
    "skeleton": ((124, 142), (62.0, 91.19392639587906)),
    "zombie": ((127, 132), (63.5, 86.82620078560831)),
}


def facings(kind: str) -> tuple[str, ...]:
    return ENHANCED_FACINGS if kind in ENHANCED else FACINGS


def walk(kind: str) -> tuple[str, ...]:
    return ENHANCED_WALK if kind in ENHANCED else WALK


def hit_frames(kind: str) -> tuple[str, ...]:
    return HIT if kind in ENHANCED else ()


def death_frames(kind: str) -> tuple[str, ...]:
    return DEATH if kind in ENHANCED else ()


def stride(kind: str) -> float:
    """Tiles per walk frame. A shorter zombie step keeps its limp alive at low speed."""
    return {"fallen": 0.085, "skeleton": 0.10, "zombie": 0.055}.get(kind, STRIDE)


def frames(kind: str) -> tuple[str, ...]:
    return walk(kind) + STRIKE + (CAST if MONSTERS[kind].leader else ()) + hit_frames(kind) + death_frames(kind)


@dataclass(frozen=True)
class Pose:
    leg: float = 0.0      # right leg forward (degrees); the left does the opposite
    arm: float = 0.0      # right arm forward; the left does the opposite
    lean: float = 0.0     # upper body forward
    twist: float = 0.0    # upper body turned to its left
    bob: float = 0.0      # body raised (tiles)
    lunge: float = 0.0    # upper body pushed forward (tiles)
    right: float | None = None   # the weapon arm's own swing, overriding ``arm``
    left: float | None = None
    flap: float = 0.0     # wings: 0 spread level, positive raised
    left_leg: float | None = None  # a limp does not mirror the leading leg
    head_roll: float = 0.0
    death: int = 0        # character-specific collapse, 1..5


POSES = {
    "walk1": Pose(leg=30, arm=-26, lean=5, flap=35),
    "walk2": Pose(leg=0, arm=0, lean=5, bob=0.03, flap=5),
    "walk3": Pose(leg=-30, arm=26, lean=5, flap=-25),
    "walk4": Pose(leg=0, arm=0, lean=5, bob=0.03, flap=5),
    "wind": Pose(leg=-10, lean=-12, twist=25, right=-165, left=25, flap=40),
    "strike": Pose(leg=20, lean=24, twist=-20, lunge=0.07, right=60, left=-25, flap=-20),
    "recover": Pose(leg=8, lean=12, twist=-8, lunge=0.03, right=25, left=-5, flap=10),
    "raise": Pose(lean=-6, right=-110, left=-100, bob=0.02),
    "chant": Pose(lean=-12, right=-170, left=-150, bob=0.06),
}

# Per-creature rhythm matters more than simply adding frames to the old shared cycle. The pairs at
# 1/5 are planted contacts; 3/7 are the passing feet. A zombie's left leg drags instead of mirroring
# the right, while a skeleton guards with its shield and the Fallen dives forward into each step.
ENHANCED_POSES: dict[str, dict[str, Pose]] = {
    "fallen": {
        "walk1": Pose(leg=42, arm=-30, lean=24, twist=-10, bob=-0.025, right=-28, left=35, head_roll=-6),
        "walk2": Pose(leg=24, arm=-18, lean=20, twist=-4, bob=0.015, right=-10, left=25),
        "walk3": Pose(leg=2, arm=0, lean=15, bob=0.045, right=18, left=8),
        "walk4": Pose(leg=-23, arm=18, lean=20, twist=6, bob=0.01, right=35, left=-12),
        "walk5": Pose(leg=-42, arm=30, lean=24, twist=10, bob=-0.025, right=38, left=-30, head_roll=6),
        "walk6": Pose(leg=-24, arm=18, lean=20, twist=4, bob=0.015, right=25, left=-24),
        "walk7": Pose(leg=-2, arm=0, lean=15, bob=0.045, right=0, left=-8),
        "walk8": Pose(leg=23, arm=-18, lean=20, twist=-6, bob=0.01, right=-20, left=12),
        "hit1": Pose(leg=12, lean=-12, twist=-15, right=-65, left=-25, head_roll=-12),
        "hit2": Pose(leg=-8, lean=-24, twist=-25, right=-85, left=-48, head_roll=-22, bob=-0.02),
        "hit3": Pose(leg=-18, lean=2, twist=-8, right=-25, left=-12, head_roll=-5),
        "death1": Pose(leg=30, lean=-20, twist=-20, right=-65, left=-60, head_roll=-24, death=1),
        "death2": Pose(leg=18, lean=12, twist=-34, right=-90, left=-85, death=2),
        "death3": Pose(leg=10, lean=20, twist=-40, right=-95, left=-100, death=3),
        "death4": Pose(leg=4, lean=12, right=-100, left=-100, death=4),
        "death5": Pose(right=-100, left=-100, death=5),
    },
    "skeleton": {
        "walk1": Pose(leg=36, lean=-2, twist=-5, bob=-0.01, right=-20, left=27),
        "walk2": Pose(leg=20, lean=0, twist=-2, bob=0.015, right=-8, left=33),
        "walk3": Pose(leg=2, lean=2, bob=0.025, right=5, left=38),
        "walk4": Pose(leg=-18, lean=0, twist=3, bob=0.01, right=20, left=34),
        "walk5": Pose(leg=-36, lean=-2, twist=5, bob=-0.01, right=30, left=27),
        "walk6": Pose(leg=-20, lean=0, twist=2, bob=0.015, right=18, left=32),
        "walk7": Pose(leg=-2, lean=2, bob=0.025, right=4, left=38),
        "walk8": Pose(leg=18, lean=0, twist=-3, bob=0.01, right=-12, left=34),
        "hit1": Pose(leg=15, lean=-8, twist=12, right=-55, left=70, head_roll=12),
        "hit2": Pose(leg=-12, lean=-22, twist=25, right=-80, left=95, head_roll=24),
        "hit3": Pose(leg=-8, lean=-3, twist=8, right=-18, left=42, head_roll=8),
        "death1": Pose(leg=16, lean=-24, twist=22, right=-80, left=110, head_roll=30, death=1),
        "death2": Pose(leg=-16, lean=20, twist=42, right=-110, left=125, death=2),
        "death3": Pose(leg=-25, lean=25, right=-110, left=125, death=3),
        "death4": Pose(death=4),
        "death5": Pose(death=5),
    },
    "zombie": {
        "walk1": Pose(leg=33, left_leg=-8, lean=18, twist=-7, bob=-0.02, right=54, left=80, head_roll=7),
        "walk2": Pose(leg=20, left_leg=-3, lean=20, twist=-3, bob=-0.005, right=62, left=75, head_roll=10),
        "walk3": Pose(leg=5, left_leg=4, lean=23, bob=0.015, right=70, left=68, head_roll=13),
        "walk4": Pose(leg=-10, left_leg=9, lean=22, twist=3, bob=0.005, right=75, left=59, head_roll=15),
        "walk5": Pose(leg=-26, left_leg=12, lean=18, twist=8, bob=-0.015, right=80, left=54, head_roll=10),
        "walk6": Pose(leg=-14, left_leg=7, lean=20, twist=5, bob=0.0, right=75, left=62, head_roll=5),
        "walk7": Pose(leg=0, left_leg=0, lean=24, bob=0.012, right=68, left=70, head_roll=0),
        "walk8": Pose(leg=18, left_leg=-5, lean=21, twist=-3, bob=0.0, right=59, left=75, head_roll=3),
        "hit1": Pose(leg=8, left_leg=-4, lean=2, twist=-12, right=80, left=88, head_roll=-16),
        "hit2": Pose(leg=-4, left_leg=2, lean=-14, twist=-20, right=96, left=105, head_roll=-28, bob=-0.015),
        "hit3": Pose(leg=5, left_leg=-2, lean=11, twist=-8, right=65, left=81, head_roll=-4),
        "death1": Pose(leg=10, left_leg=-10, lean=-8, twist=-14, right=100, left=110, head_roll=-23, death=1),
        "death2": Pose(leg=-12, left_leg=10, lean=25, twist=-19, right=112, left=116, head_roll=24, death=2),
        "death3": Pose(leg=-20, left_leg=22, lean=33, right=120, left=125, death=3),
        "death4": Pose(leg=-18, left_leg=18, death=4),
        "death5": Pose(death=5),
    },
}

INK = (26, 20, 24)
EYE = (255, 196, 60)
EMBER = (255, 90, 30)


def darker(c, k: float = 0.7):
    return tuple(int(v * k) for v in c[:3])


@dataclass(frozen=True)
class Build:
    """Proportions of a two-legged monster, in tiles."""

    hip: float
    leg_w: float
    torso: tuple[float, float, float]   # width, depth, height
    head: float                         # radius
    arm_len: float
    arm_w: float
    skin: tuple[int, int, int]
    legs_color: tuple[int, int, int]
    body_color: tuple[int, int, int]
    hunch: float = 0.0                  # permanent forward lean
    robe: tuple[int, int, int] | None = None
    reach: float = 0.0                  # arms held forward at rest (zombies)


def humanoid(b: Build, pose: Pose, *, head: Mesh, right_hand: Mesh = (), left_hand: Mesh = (), extra: Mesh = ()) -> Mesh:
    """Legs from the hip, then the upper body (torso, head, arms and what the hands hold) posed about it.

    ``head`` is built with its centre at the origin; hand meshes hang below the origin (the hand) with
    the weapon pointing along +y, the way an arm hanging at rest would hold it. ``extra`` rides on the
    upper body in body coordinates (a back-slung wing, a belly).
    """
    mesh: Mesh = []
    hip = b.hip
    lx = b.torso[0] * 0.28
    if b.robe is None:
        for side, swing in ((-1, pose.leg), (1, pose.left_leg if pose.left_leg is not None else -pose.leg)):
            leg = rod((0, 0, 0), (0, 0.02, -hip + b.leg_w * 0.4), b.leg_w, b.legs_color)
            leg += r3.box((0, 0.05, -hip + b.leg_w * 0.35), (b.leg_w * 1.1, b.leg_w * 1.8, b.leg_w * 0.7), darker(b.legs_color, 0.6))
            mesh += move(pitch(leg, swing, (0, 0, 0)), side * lx, 0, hip)
    else:
        hem = 0.06 + 0.05 * abs(pose.leg) / 30
        skirt = r3.cone((0, 0, 0.0), b.torso[0] * 0.55 + hem, hip * 1.3, b.robe, sides=9)
        skirt = pitch(skirt, -pose.leg * 0.15, (0, 0, hip))
        mesh += skirt
        for side, swing in ((-1, pose.leg), (1, pose.left_leg if pose.left_leg is not None else -pose.leg)):
            foot = r3.box((side * lx, 0.05 + swing * 0.003, 0.03), (b.leg_w, b.leg_w * 1.6, 0.06), darker(b.robe, 0.5))
            mesh += foot
    upper: Mesh = []
    tw, td, th = b.torso
    upper += r3.box((0, 0, hip + th / 2), (tw, td, th), b.body_color)
    upper += r3.box((0, 0, hip + th * 0.08), (tw * 1.05, td * 1.1, th * 0.16), darker(b.body_color, 0.6))  # belt
    upper += move(roll(head, pose.head_roll, (0, 0, 0)), 0, 0.01, hip + th + b.head * 0.85)
    upper += list(extra)
    shoulder_z = hip + th * 0.88
    for side, hand, own in ((-1, right_hand, pose.right), (1, left_hand, pose.left)):
        swing = own if own is not None else (pose.arm * (1 if side < 0 else -1))
        swing += b.reach
        arm = rod((0, 0, 0), (0, 0, -b.arm_len), b.arm_w, b.skin)
        arm += r3.box((0, 0.0, -b.arm_len), (b.arm_w * 1.25, b.arm_w * 1.25, b.arm_w * 1.1), darker(b.skin, 0.8))
        arm += move(list(hand), 0, 0, -b.arm_len)
        arm = pitch(arm, swing, (0, 0, 0))
        arm = roll(arm, side * -8, (0, 0, 0))
        upper += move(arm, side * (tw / 2 + b.arm_w * 0.45), 0, shoulder_z)
    upper = yaw(upper, pose.twist, (0, 0, hip))
    upper = pitch(upper, pose.lean + b.hunch, (0, 0, hip))
    mesh += move(upper, 0, pose.lunge, 0)
    return move(mesh, 0, 0, pose.bob)


def held(weapon: Mesh, up: float = 70.0, out: float = -18.0) -> Mesh:
    """A weapon built pointing forward (+y) from the hand, raised *up* degrees and angled *out* from the body.

    The front camera shows depth as screen-down one to one but height at only cos(55°): a blade held
    less steeply than about 60° reads as pointing at the ground.
    """
    return roll(pitch(weapon, up, (0, 0, 0)), out, (0, 0, 0))


def eyes(r: float, color=EYE, spread: float = 0.36, height: float = 0.1) -> Mesh:
    s = r * 0.22
    return [f for side in (-1, 1) for f in r3.box((side * r * spread, r * 0.86, r * height), (s, s * 0.6, s * 0.7), color)]


def on_ground(mesh: Mesh) -> Mesh:
    """Settle a posed collapse on the floor without changing the frame's ground anchor."""
    lowest = min(p[2] for face in mesh for p in face.points)
    return move(mesh, dz=0.02 - lowest)


# -- The monsters ------------------------------------------------------------------------------


def fallen(pose: Pose, *, shaman: bool = False) -> Mesh:
    skin = (176, 52, 38) if not shaman else (160, 44, 58)
    b = Build(hip=0.19, leg_w=0.07, torso=(0.2, 0.14, 0.17), head=0.105, arm_len=0.16, arm_w=0.055,
              skin=skin, legs_color=darker(skin, 0.8), body_color=(92, 60, 40), hunch=16)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    head += r3.box((0, b.head * 0.6, -b.head * 0.35), (b.head * 1.0, b.head * 0.9, b.head * 0.5), darker(skin, 0.85))  # snout
    for side in (-1, 1):   # long pointed ears
        head += rod((side * b.head * 0.8, 0, b.head * 0.2), (side * b.head * 2.0, -0.02, b.head * 0.75), 0.03, darker(skin, 0.9))
        head += r3.cone((side * b.head * 0.45, 0, b.head * 0.7), 0.025, 0.07, (230, 210, 170), sides=5)
    head += eyes(b.head)
    if shaman:
        for i, dx in enumerate((-0.07, 0.0, 0.07)):   # a crest of feathers
            head += rod((dx * 0.6, -0.03, b.head * 0.8), (dx, -0.08, b.head * 2.3), 0.03, ((200, 170, 60), (210, 60, 40), (200, 170, 60))[i])
        staff = rod((0, -0.02, 0.05), (0, 0.05, -0.2), 0.03, (98, 72, 48))
        staff += rod((0, -0.02, 0.05), (0, -0.09, 0.42), 0.03, (98, 72, 48))
        staff += r3.sphere((0, -0.1, 0.47), 0.06, (228, 216, 190), rings=4, sides=6)   # a skull on top
        staff += r3.box((0, -0.05, 0.46), (0.04, 0.02, 0.025), INK)
        right = staff
    else:
        right = blade((0, 0.0, -0.01), (0, 0.2, 0.0), 0.07, (196, 196, 206))
        right += rod((0, -0.02, 0.0), (0, 0.03, -0.03), 0.03, (70, 50, 40))
        right = held(right, 62)
    return humanoid(b, pose, head=head, right_hand=right if pose.death < 4 else [], left_hand=[])


def skeleton(pose: Pose) -> Mesh:
    bone = (222, 214, 190)
    b = Build(hip=0.3, leg_w=0.045, torso=(0.2, 0.1, 0.22), head=0.085, arm_len=0.23, arm_w=0.04,
              skin=bone, legs_color=bone, body_color=(196, 186, 160), hunch=4)
    head = r3.sphere((0, 0, 0), b.head, bone, rings=4, sides=7)
    head += r3.box((0, b.head * 0.55, -b.head * 0.55), (b.head * 1.1, b.head * 0.7, b.head * 0.5), darker(bone, 0.92))  # jaw
    head += eyes(b.head, color=(24, 10, 10), spread=0.4, height=0.15)
    head += [f for side in (-1, 1) for f in r3.box((side * b.head * 0.38, b.head * 0.8, b.head * 0.15), (0.02, 0.01, 0.015), (255, 90, 40))]
    ribs = []
    for i in range(3):
        ribs += r3.box((0, 0.052, 0.3 + 0.06 + i * 0.055), (0.2, 0.012, 0.018), (150, 140, 118))
    sword = blade((0, 0.0, 0.0), (0, 0.34, 0.05), 0.06, (170, 160, 150))
    sword += rod((-0.05, 0.015, 0.0), (0.05, 0.015, 0.0), 0.025, (120, 90, 60))
    sword = held(sword)
    shield = r3.cylinder((0, 0, 0), 0.13, 0.03, (116, 80, 50), sides=9)
    shield = pitch(shield, 90, (0, 0, 0))
    shield += r3.sphere((0, 0.04, 0), 0.03, (160, 150, 140), rings=3, sides=5)
    shield = move(shield, 0.03, 0.04, 0.02)
    if pose.death >= 4:
        # A skeletal warrior does not topple as one solid body: the bones scatter and settle.
        spread = 1.0 if pose.death == 4 else 0.82
        remains: Mesh = []
        remains += r3.sphere((0.17 * spread, -0.03, 0.085), 0.085, bone, rings=4, sides=7)
        remains += r3.box((0.17 * spread, 0.045, 0.045), (0.09, 0.025, 0.025), darker(bone, 0.8))
        for index, (x, y, a) in enumerate(((-0.18, 0.05, -35), (-0.08, -0.09, 50), (0.02, 0.14, -55), (0.24, 0.16, 30))):
            length = 0.20 if index < 2 else 0.14
            limb = rod((-length / 2, 0, 0), (length / 2, 0, 0), 0.035, bone)
            remains += move(yaw(limb, a), x * spread, y * spread, 0.055)
        for i in range(3):
            remains += r3.box((-0.06 + i * 0.055, 0.0, 0.045), (0.018, 0.16, 0.025), (150, 140, 118))
        remains += move(pitch(shield, 80, (0, 0, 0)), -0.28 * spread, -0.13, 0.08)
        remains += move(pitch(sword, 80, (0, 0, 0)), 0.33 * spread, 0.12, 0.06)
        return on_ground(remains)
    body = humanoid(b, pose, head=head if pose.death < 3 else [], right_hand=sword, left_hand=shield, extra=ribs)
    if pose.death >= 2:
        body = pitch(body, (0, 28, 58)[pose.death - 1], (0, 0, 0.05))
    if pose.death == 3:
        body += r3.sphere((0.22, -0.08, 0.11), 0.085, bone, rings=4, sides=7)
    return on_ground(body) if pose.death else body


def zombie(pose: Pose) -> Mesh:
    skin = (122, 138, 104)
    b = Build(hip=0.28, leg_w=0.075, torso=(0.26, 0.17, 0.26), head=0.1, arm_len=0.26, arm_w=0.07,
              skin=skin, legs_color=(84, 70, 58), body_color=(96, 82, 66), hunch=14, reach=62)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    head += r3.box((0.02, b.head * 0.6, -b.head * 0.5), (b.head * 1.0, b.head * 0.6, b.head * 0.45), (70, 40, 40))  # slack jaw
    head += eyes(b.head, color=(220, 240, 160), spread=0.4)
    head = roll(head, 14, (0, 0, -b.head))   # lolling
    rags = r3.box((0.05, 0.09, 0.28 + 0.1), (0.12, 0.01, 0.16), (70, 58, 46))
    rags += r3.box((0, 0.0, 0.28 + 0.29), (0.3, 0.19, 0.04), (110, 96, 78))
    claws = []
    for dx in (-0.025, 0.0, 0.025):
        claws += rod((dx, 0.0, 0.0), (dx * 1.4, 0.05, -0.06), 0.015, (60, 50, 40))
    return humanoid(b, pose, head=head, right_hand=claws, left_hand=claws, extra=rags)


def goatman(pose: Pose) -> Mesh:
    fur = (118, 84, 58)
    b = Build(hip=0.34, leg_w=0.075, torso=(0.24, 0.16, 0.26), head=0.095, arm_len=0.25, arm_w=0.06,
              skin=(132, 100, 74), legs_color=fur, body_color=(96, 70, 50), hunch=6)
    head = r3.box((0, 0.02, 0), (b.head * 1.5, b.head * 1.6, b.head * 1.6), (126, 94, 66))
    head += r3.box((0, b.head * 1.2, -b.head * 0.35), (b.head * 0.9, b.head * 1.6, b.head * 0.8), (140, 110, 80))  # muzzle
    head += r3.box((0, b.head * 1.95, -b.head * 0.3), (b.head * 0.5, b.head * 0.2, b.head * 0.35), INK)
    for side in (-1, 1):   # swept horns
        horn = rod((side * b.head * 0.55, 0, b.head * 0.7), (side * b.head * 1.5, -0.08, b.head * 1.9), 0.045, (70, 60, 52))
        horn += rod((side * b.head * 1.5, -0.08, b.head * 1.9), (side * b.head * 2.1, -0.02, b.head * 1.3), 0.035, (60, 52, 46))
        head += horn
    head += eyes(b.head * 1.1, color=(255, 170, 40), spread=0.42, height=0.3)
    beard = r3.pyramid((0, b.head * 1.5, -b.head * 0.8), (0.06, 0.04), -0.1, (90, 70, 50))
    head += beard
    pole = rod((0, -0.14, 0.02), (0, 0.5, 0.02), 0.03, (96, 70, 44))
    pole += blade((0, 0.44, 0.02), (0, 0.66, 0.1), 0.12, (176, 170, 164))
    pole += blade((0, 0.47, 0.02), (0, 0.42, -0.1), 0.08, (150, 146, 140))
    pole = held(pole, 72, -10)
    return humanoid(b, pose, head=head, right_hand=pole, left_hand=[])


def gargoyle(pose: Pose) -> Mesh:
    stone = (112, 116, 124)
    b = Build(hip=0.22, leg_w=0.07, torso=(0.24, 0.17, 0.2), head=0.09, arm_len=0.2, arm_w=0.06,
              skin=stone, legs_color=darker(stone, 0.85), body_color=(104, 108, 116), hunch=28)
    head = r3.box((0, 0.02, 0), (b.head * 1.6, b.head * 1.7, b.head * 1.4), stone)
    head += r3.box((0, b.head * 1.1, -b.head * 0.3), (b.head * 1.2, b.head * 0.8, b.head * 0.6), darker(stone, 0.9))
    for side in (-1, 1):
        head += rod((side * b.head * 0.5, 0, b.head * 0.6), (side * b.head * 1.1, -0.1, b.head * 1.9), 0.04, (60, 60, 66))
    head += eyes(b.head * 1.05, color=(120, 255, 210), spread=0.42, height=0.25)
    wings = []
    for side in (-1, 1):
        wings += wing((side * 0.08, -0.08, 0.22 + 0.15), 0.62, 0.34, side, 30 + pose.flap, (84, 78, 96))
    claws = []
    for dx in (-0.025, 0.025):
        claws += rod((dx, 0.0, 0.0), (dx * 1.5, 0.06, -0.07), 0.018, (220, 220, 214))
    body = humanoid(b, replace(pose, leg=pose.leg * 0.4), head=head, right_hand=claws, left_hand=claws, extra=wings)
    return move(body, 0, 0, 0.32)   # it flies


def overlord(pose: Pose) -> Mesh:
    skin = (136, 60, 44)
    b = Build(hip=0.36, leg_w=0.12, torso=(0.42, 0.3, 0.34), head=0.1, arm_len=0.3, arm_w=0.11,
              skin=skin, legs_color=darker(skin, 0.75), body_color=(128, 58, 44), hunch=8)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    head += r3.box((0, b.head * 0.5, -b.head * 0.55), (b.head * 1.5, b.head * 0.9, b.head * 0.55), darker(skin, 0.85))
    for side in (-1, 1):
        head += r3.cone((side * b.head * 0.6, 0, b.head * 0.5), 0.035, 0.13, (230, 220, 190), sides=5)
        head += r3.cone((side * b.head * 0.6, b.head * 0.75, -b.head * 0.55), 0.02, 0.06, (240, 230, 200), sides=4)  # tusks
    head += eyes(b.head, color=(255, 220, 60))
    belly = r3.sphere((0, 0.07, 0.36 + 0.13), 0.22, (150, 72, 54), rings=5, sides=9)
    belly += r3.box((0, 0.0, 0.36 + 0.02), (0.46, 0.33, 0.07), (60, 40, 30))
    club = rod((0, -0.04, 0.0), (0, 0.46, 0.08), 0.06, (84, 60, 40))
    club += r3.sphere((0, 0.5, 0.1), 0.1, (90, 64, 42), rings=4, sides=7)
    for dx, dz in ((0.08, 0.1), (-0.08, 0.1), (0, 0.19), (0, 0.02)):
        club += r3.cone((dx, 0.5, 0.1 + (dz - 0.1)), 0.02, 0.08 if dz != 0.02 else -0.08, (200, 200, 205), sides=4)
    club = held(club, 60, -25)
    return humanoid(b, pose, head=head, right_hand=club, left_hand=[], extra=belly)


def azazel(pose: Pose) -> Mesh:
    hide = (112, 26, 30)
    armour = (46, 36, 40)
    b = Build(hip=0.62, leg_w=0.16, torso=(0.56, 0.34, 0.5), head=0.15, arm_len=0.5, arm_w=0.14,
              skin=hide, legs_color=armour, body_color=armour, hunch=6)
    head = r3.box((0, 0.02, 0), (b.head * 1.6, b.head * 1.5, b.head * 1.5), hide)
    head += r3.box((0, b.head * 0.75, -b.head * 0.5), (b.head * 1.2, b.head * 0.6, b.head * 0.6), darker(hide, 0.8))
    for side in (-1, 1):   # great ram horns
        horn = rod((side * b.head * 0.7, 0, b.head * 0.5), (side * b.head * 2.2, -0.12, b.head * 1.6), 0.08, (40, 34, 30))
        horn += rod((side * b.head * 2.2, -0.12, b.head * 1.6), (side * b.head * 2.6, 0.02, b.head * 0.8), 0.06, (30, 26, 24))
        horn += rod((side * b.head * 2.6, 0.02, b.head * 0.8), (side * b.head * 2.4, 0.1, b.head * 0.3), 0.04, (230, 210, 170))
        head += horn
    head += eyes(b.head * 1.1, color=(255, 120, 20), spread=0.4, height=0.2)
    extra = []
    for side in (-1, 1):   # pauldrons with spikes
        extra += r3.box((side * 0.33, 0, 0.62 + 0.46), (0.2, 0.3, 0.12), (70, 50, 52))
        extra += r3.cone((side * 0.38, 0, 0.62 + 0.52), 0.05, 0.16, (200, 190, 180), sides=5)
        extra += wing((side * 0.14, -0.16, 0.62 + 0.4), 1.05, 0.6, side, 38 + pose.flap * 0.4, (70, 22, 26))
    extra += r3.box((0, 0.17, 0.62 + 0.3), (0.2, 0.02, 0.2), (255, 110, 30))   # a molten rune on the chest
    sword = blade((0, 0.0, 0.0), (0, 0.9, 0.18), 0.16, (255, 120, 40))   # a flaming greatsword
    sword += blade((0, 0.02, 0.01), (0, 0.8, 0.16), 0.07, (255, 220, 120))
    sword += rod((-0.12, 0.0, 0.0), (0.12, 0.0, 0.0), 0.05, (60, 40, 30))
    sword = held(sword, 66, -22)
    return humanoid(b, pose, head=head, right_hand=sword, left_hand=[], extra=extra)


def priest(pose: Pose) -> Mesh:
    bone = (222, 214, 190)
    robe = (62, 50, 44)   # ash and soot: nothing near the magenta the sheets are keyed on
    b = Build(hip=0.3, leg_w=0.05, torso=(0.22, 0.14, 0.26), head=0.09, arm_len=0.24, arm_w=0.05,
              skin=bone, legs_color=robe, body_color=robe, robe=robe, hunch=6)
    head = r3.sphere((0, 0, 0), b.head, bone, rings=4, sides=7)
    head += eyes(b.head, color=(120, 255, 150), spread=0.4, height=0.15)
    hood = r3.cone((0, -0.02, -b.head * 0.2), b.head * 1.35, b.head * 2.4, darker(robe, 0.8), sides=8)
    head = hood + head
    crown = []
    for i in range(5):
        x = (i - 2) * 0.035
        crown += r3.cone((x, 0.04, b.head * 0.95), 0.015, 0.07, (190, 160, 70), sides=4)
    head += crown
    stole = r3.box((0, 0.075, 0.3 + 0.13), (0.07, 0.01, 0.26), (140, 30, 40))
    staff = rod((0, -0.02, 0.05), (0, 0.04, -0.25), 0.032, (60, 56, 50))
    staff += rod((0, -0.02, 0.05), (0, -0.1, 0.5), 0.032, (60, 56, 50))
    staff += r3.sphere((0, -0.11, 0.57), 0.065, (110, 255, 150), rings=4, sides=7)
    for side in (-1, 1):
        staff += rod((0, -0.1, 0.5), (side * 0.07, -0.12, 0.62), 0.02, bone)
    return humanoid(b, pose, head=head, right_hand=staff, left_hand=[], extra=stole)


def witch(pose: Pose) -> Mesh:
    skin = (214, 176, 160)
    gown = (120, 20, 34)
    b = Build(hip=0.33, leg_w=0.05, torso=(0.18, 0.12, 0.26), head=0.08, arm_len=0.24, arm_w=0.042,
              skin=skin, legs_color=gown, body_color=gown, robe=gown, hunch=0)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    hair = r3.box((0, -0.03, -0.04), (b.head * 2.2, b.head * 1.4, b.head * 2.6), (30, 18, 22))
    head = hair + head
    for side in (-1, 1):
        head += rod((side * b.head * 0.5, 0, b.head * 0.6), (side * b.head * 1.3, -0.05, b.head * 1.9), 0.03, (40, 30, 34))
        head += rod((side * b.head * 1.3, -0.05, b.head * 1.9), (side * b.head * 1.0, 0.03, b.head * 2.5), 0.022, (40, 30, 34))
    head += eyes(b.head, color=(255, 60, 60), spread=0.38, height=0.1)
    collar = r3.box((0, 0, 0.33 + 0.25), (0.26, 0.16, 0.04), (60, 12, 20))
    collar += r3.box((0, 0.064, 0.33 + 0.14), (0.05, 0.01, 0.1), (220, 170, 60))
    staff = rod((0, -0.02, 0.05), (0, 0.04, -0.25), 0.028, (40, 26, 30))
    staff += rod((0, -0.02, 0.05), (0, -0.1, 0.48), 0.028, (40, 26, 30))
    crystal = r3.pyramid((0, -0.11, 0.5), (0.08, 0.08), 0.1, (230, 40, 60)) + r3.pyramid((0, -0.11, 0.5), (0.08, 0.08), -0.07, (180, 20, 40))
    staff += move(crystal, 0, 0, 0.04)
    return humanoid(b, pose, head=head, right_hand=staff, left_hand=[], extra=collar)


# -- Act II monsters -----------------------------------------------------------------------------


def flayer(pose: Pose) -> Mesh:
    """Tiny jungle fiend, knee-high, hunched, bony limbs, bone mask with feather crest, short spear."""
    skin = (180, 60, 40)
    b = Build(hip=0.12, leg_w=0.045, torso=(0.14, 0.1, 0.13), head=0.08, arm_len=0.12, arm_w=0.04,
              skin=skin, legs_color=(120, 40, 30), body_color=(140, 50, 35), hunch=22)
    head = r3.box((0, 0, 0), (b.head * 1.3, b.head * 1.1, b.head * 1.2), (80, 60, 50))  # bone mask
    head += r3.box((0, b.head * 0.5, -b.head * 0.25), (b.head * 0.8, b.head * 0.7, b.head * 0.5), (60, 45, 40))
    for side in (-1, 1):   # feather crest
        head += rod((side * b.head * 0.35, -0.02, b.head * 0.9), (side * b.head * 0.6, -0.06, b.head * 1.8), 0.02, (200, 170, 60))
    head += eyes(b.head, color=(255, 180, 40), spread=0.45, height=0.2)
    spear = rod((0, -0.02, 0.0), (0, 0.22, 0.02), 0.025, (110, 90, 70))
    spear += blade((0, 0.18, 0.02), (0, 0.35, 0.05), 0.05, (180, 170, 160))
    spear = held(spear, 55)
    return humanoid(b, pose, head=head, right_hand=spear, left_hand=[])


def zealot(pose: Pose) -> Mesh:
    """Tall human fanatic in white-and-gold robes, tall mitre-like hood, long flail."""
    skin = (220, 190, 170)
    robe = (245, 235, 210)
    gold = (210, 170, 40)
    b = Build(hip=0.36, leg_w=0.055, torso=(0.22, 0.14, 0.28), head=0.085, arm_len=0.28, arm_w=0.045,
              skin=skin, legs_color=robe, body_color=robe, robe=robe, hunch=2)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    head += eyes(b.head, color=(40, 30, 20), spread=0.35, height=0.1)
    mitre = r3.pyramid((0, -0.02, -b.head * 0.15), (b.head * 1.1, b.head * 1.1), b.head * 2.6, robe)
    mitre += r3.box((0, 0, -b.head * 0.2), (b.head * 1.2, b.head * 0.8, b.head * 0.4), gold)
    head = mitre + head
    stole = r3.box((0, 0.06, 0.3 + 0.12), (0.06, 0.01, 0.28), gold)
    flail = rod((0, -0.03, 0.02), (0, 0.05, -0.28), 0.025, (120, 90, 60))
    chain = []
    for i in range(3):
        z = -0.32 - i * 0.09
        chain += r3.sphere((0, 0.03, z), 0.035, (160, 130, 80), rings=3, sides=5)
    flail += chain
    flail = held(flail, 65, -15)
    return humanoid(b, pose, head=head, right_hand=flail, left_hand=[], extra=stole)


def spider(pose: Pose) -> Mesh:
    """Big eight-legged spider, low and wide, dark body with red hourglass, walk frames move legs."""
    body_color = (40, 20, 25)
    leg_color = (20, 10, 15)
    hourglass = (220, 40, 40)
    mesh: Mesh = []
    # Cephalothorax (front body) - main body where legs attach
    thorax = r3.sphere((0, 0, 0), 0.18, body_color, rings=5, sides=7)
    mesh += thorax
    # Abdomen (large rear body) joined to thorax
    abd = r3.sphere((0, -0.38, 0.05), 0.3, body_color, rings=6, sides=8)
    abd += r3.box((0, -0.38, 0.3), (0.12, 0.08, 0.06), hourglass)
    abd += r3.box((0, -0.38, 0.36), (0.08, 0.06, 0.04), hourglass)
    # Pedicel (narrow waist joining abdomen to thorax)
    abd += r3.cylinder((0, -0.18, 0.0), 0.04, 0.2, body_color, sides=6)
    mesh += abd
    # Mandibles (chelicerae)
    for side in (-1, 1):
        mand = rod((side * 0.1, 0.15, 0.05), (side * 0.18, 0.22, -0.02), 0.025, leg_color)
        mesh += mand
    # Eyes (cluster of 8 small eyes on front of thorax)
    for dx in (-0.04, 0.04):
        for dy in (-0.03, 0.0, 0.03):
            mesh += r3.box((dx, 0.15, 0.1), (0.015, 0.015, 0.015), (255, 180, 30))
    # Eight legs attached to thorax at proper positions (4 pairs along thorax sides)
    leg_phase = pose.leg / 30.0  # -1 to 1
    # Leg attachment points on thorax: 4 pairs at different y positions
    leg_pairs = [
        (-1, -35, 0.12), (-1, -10, 0.04), (-1, 15, -0.04), (-1, 40, -0.12),  # left side
        (1, -35, 0.12), (1, -10, 0.04), (1, 15, -0.04), (1, 40, -0.12),    # right side
    ]
    for side, ang_base, attach_y in leg_pairs:
        swing = leg_phase * 35 * (1 if side < 0 else -1)
        ang = math.radians(ang_base + swing)
        # Attach at thorax side
        attach_x = side * 0.18
        attach_z = 0.05
        # Two segments per leg
        seg1_end = (attach_x + side * 0.25 * math.cos(ang), attach_y + 0.25 * math.sin(ang), attach_z - 0.05)
        seg2_end = (seg1_end[0] + side * 0.22 * math.cos(ang * 0.7),
                    seg1_end[1] + 0.22 * math.sin(ang * 0.7), -0.05)
        mesh += rod((attach_x, attach_y, attach_z), seg1_end, 0.022, leg_color)
        mesh += rod(seg1_end, seg2_end, 0.018, leg_color)
    return move(mesh, 0, 0, 0.1)


def bat(pose: Pose) -> Mesh:
    """Blood bat, wings spread, small body; flies like the gargoyle (same height offset)."""
    body_color = (100, 20, 40)
    wing_color = (140, 30, 60)
    mesh: Mesh = []
    # Small body
    mesh += r3.sphere((0, 0, 0), 0.07, body_color, rings=4, sides=6)
    mesh += r3.box((0, 0.04, -0.02), (0.05, 0.06, 0.04), (80, 15, 30))  # snout
    mesh += eyes(0.07, color=(255, 60, 80), spread=0.5, height=0.15)
    # Ears
    for side in (-1, 1):
        mesh += rod((side * 0.05, 0, 0.06), (side * 0.12, -0.02, 0.15), 0.015, body_color)
    # Wings
    spread = 30 + pose.flap * 0.8
    for side in (-1, 1):
        mesh += wing((side * 0.05, -0.02, 0.05), 0.55, 0.25, side, spread, wing_color)
    return move(mesh, 0, 0, 0.32)  # same hover as gargoyle


def hulk(pose: Pose) -> Mesh:
    """Thorned Hulk: huge broad brute of bark and thorns, long arms, small head, knuckle-walking."""
    bark = (80, 60, 40)
    thorn = (140, 100, 60)
    thorn_tip = (180, 160, 80)
    b = Build(hip=0.55, leg_w=0.14, torso=(0.55, 0.35, 0.45), head=0.09, arm_len=0.55, arm_w=0.12,
              skin=bark, legs_color=bark, body_color=(70, 55, 35), hunch=30)
    head = r3.sphere((0, 0, 0), b.head, bark, rings=4, sides=6)
    head += r3.box((0, b.head * 0.4, -b.head * 0.3), (b.head * 1.1, b.head * 0.8, b.head * 0.5), (60, 45, 30))
    head += eyes(b.head, color=(200, 180, 60), spread=0.4, height=0.2)
    # Thorns on back and shoulders
    extra: Mesh = []
    for x in (-0.22, 0.22):
        extra += rod((x, 0.05, 0.52), (x, 0.1, 0.75), 0.035, thorn)
        extra += r3.cone((x, 0.1, 0.75), 0.025, 0.08, thorn_tip, sides=4)
    for i in range(3):
        z = 0.55 + i * 0.12
        extra += rod((0, 0.08, z), (0, 0.15, z + 0.18), 0.025, thorn)
        extra += r3.cone((0, 0.15, z + 0.18), 0.018, 0.06, thorn_tip, sides=4)
    # Knuckle-walking: arms forward, hands on ground
    fist = r3.box((0, 0, 0), (b.arm_w * 1.8, b.arm_w * 1.8, b.arm_w * 1.5), (60, 45, 30))
    return humanoid(b, replace(pose, arm=-40, right=-50, left=-50), head=head,
                    right_hand=fist, left_hand=fist, extra=extra)


def drowned(pose: Pose) -> Mesh:
    """Bloated drowned corpse, pale blue-green, weed hanging off it, arms reaching."""
    skin = (70, 100, 110)
    weed = (40, 80, 50)
    b = Build(hip=0.28, leg_w=0.08, torso=(0.3, 0.22, 0.32), head=0.095, arm_len=0.3, arm_w=0.06,
              skin=skin, legs_color=(50, 75, 85), body_color=(80, 110, 120), hunch=18, reach=70)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    head += r3.box((0.02, b.head * 0.5, -b.head * 0.4), (b.head * 1.1, b.head * 0.7, b.head * 0.5), (50, 60, 70))  # slack jaw
    head += eyes(b.head, color=(160, 220, 200), spread=0.45, height=0.15)
    head = roll(head, 10, (0, 0, -b.head))
    # Weed hanging from body
    extra: Mesh = []
    for dx in (-0.12, -0.04, 0.04, 0.12):
        w = rod((dx, 0.15, 0.4), (dx + 0.03, 0.22, 0.2), 0.015, weed)
        w += rod((dx, 0.15, 0.4), (dx - 0.02, 0.18, 0.1), 0.012, weed)
        extra += w
    claws = []
    for dx in (-0.02, 0.0, 0.02):
        claws += rod((dx, 0.0, 0.0), (dx * 1.3, 0.06, -0.08), 0.012, (40, 50, 55))
    return humanoid(b, pose, head=head, right_hand=claws, left_hand=claws, extra=extra)


def fetish(pose: Pose) -> Mesh:
    """Fetish Shaman: a flayer with a big feathered headdress and a staff with a smoking skull (chant frames)."""
    skin = (160, 40, 60)
    b = Build(hip=0.13, leg_w=0.05, torso=(0.15, 0.11, 0.14), head=0.085, arm_len=0.14, arm_w=0.045,
              skin=skin, legs_color=(110, 30, 45), body_color=(130, 45, 55), hunch=20)
    head = r3.box((0, 0, 0), (b.head * 1.4, b.head * 1.2, b.head * 1.3), (70, 40, 50))  # bone mask
    head += r3.box((0, b.head * 0.5, -b.head * 0.25), (b.head * 0.9, b.head * 0.8, b.head * 0.5), (50, 35, 40))
    # Large feathered headdress
    for i, dx in enumerate((-0.1, -0.05, 0.0, 0.05, 0.1)):
        color = (200, 160, 50) if i % 2 == 0 else (210, 60, 50)
        head += rod((dx * 0.8, -0.03, b.head * 1.0), (dx * 1.5, -0.1, b.head * 2.8), 0.035, color)
    head += eyes(b.head, color=(255, 200, 60), spread=0.5, height=0.2)
    # Staff with smoking skull
    staff = rod((0, -0.02, 0.05), (0, 0.04, -0.25), 0.03, (90, 70, 50))
    staff += rod((0, -0.02, 0.05), (0, -0.1, 0.55), 0.03, (90, 70, 50))
    staff += r3.sphere((0, -0.11, 0.6), 0.07, (220, 200, 170), rings=4, sides=6)  # skull
    # Smoke from skull
    staff += r3.cone((0, -0.08, 0.65), 0.06, 0.15, (80, 80, 90, 120), sides=6)
    staff += r3.cone((0, -0.05, 0.75), 0.04, 0.1, (60, 60, 70, 80), sides=6)
    return humanoid(b, pose, head=head, right_hand=staff, left_hand=[])


def inquisitor(pose: Pose) -> Mesh:
    """Zakarum Inquisitor: a zealot leader in heavier gold vestments, a book in one hand and a raised open palm (chant frames)."""
    skin = (210, 180, 160)
    vestment = (250, 240, 210)
    gold = (220, 180, 50)
    b = Build(hip=0.38, leg_w=0.06, torso=(0.25, 0.16, 0.3), head=0.09, arm_len=0.3, arm_w=0.05,
              skin=skin, legs_color=vestment, body_color=vestment, robe=vestment, hunch=0)
    head = r3.sphere((0, 0, 0), b.head, skin, rings=4, sides=7)
    head += eyes(b.head, color=(30, 25, 20), spread=0.35, height=0.1)
    # Ornate mitre with gold trim
    mitre = r3.pyramid((0, -0.02, -b.head * 0.15), (b.head * 1.2, b.head * 1.2), b.head * 3.0, vestment)
    for side in (-1, 1):
        mitre += rod((side * b.head * 0.9, 0, b.head * 1.2), (side * b.head * 1.6, 0, b.head * 2.8), 0.025, gold)
    mitre += r3.box((0, 0, -b.head * 0.2), (b.head * 1.3, b.head * 0.9, b.head * 0.5), gold)
    head = mitre + head
    # Book in left hand
    book = r3.box((0, 0, 0), (0.12, 0.02, 0.16), (40, 30, 20))
    book += r3.box((0, -0.01, 0.08), (0.11, 0.03, 0.01), gold)
    book += r3.box((0.055, -0.01, 0.0), (0.01, 0.03, 0.16), (60, 40, 20))  # spine
    # Right hand raised open palm (chanting)
    palm = r3.box((0, 0, 0), (0.07, 0.015, 0.09), skin)
    for dx in (-0.025, -0.008, 0.008, 0.025):
        palm += rod((dx, 0.015, 0.0), (dx * 1.1, 0.06, 0.0), 0.01, skin)
    return humanoid(b, pose, head=head, right_hand=palm, left_hand=book)


def bone_priest(pose: Pose) -> Mesh:
    """Bone Priest boss: reuse the priest rig at 1.6x with a gold spiked crown and a staff topped by a caged green orb (chant frames)."""
    bone = (222, 214, 190)
    robe = (62, 50, 44)
    gold = (210, 170, 30)
    orb = (60, 220, 120)
    b = Build(hip=0.48, leg_w=0.08, torso=(0.35, 0.22, 0.42), head=0.144, arm_len=0.384, arm_w=0.08,
              skin=bone, legs_color=robe, body_color=robe, robe=robe, hunch=6)
    head = r3.sphere((0, 0, 0), b.head, bone, rings=4, sides=7)
    head += eyes(b.head, color=(120, 255, 150), spread=0.4, height=0.15)
    hood = r3.cone((0, -0.02, -b.head * 0.2), b.head * 1.35, b.head * 2.4, darker(robe, 0.8), sides=8)
    head = hood + head
    # Gold spiked crown
    crown = []
    for i in range(7):
        x = (i - 3) * 0.045
        crown += r3.cone((x, 0.04, b.head * 0.95), 0.022, 0.1, gold, sides=4)
        crown += r3.cone((x, 0.04, b.head * 1.0), 0.012, 0.06, (255, 255, 200), sides=4)
    head += crown
    stole = r3.box((0, 0.075, 0.3 + 0.13), (0.07, 0.01, 0.26), (140, 30, 40))
    # Staff with caged green orb
    staff = rod((0, -0.02, 0.05), (0, 0.04, -0.4), 0.04, (60, 56, 50))
    staff += rod((0, -0.02, 0.05), (0, -0.16, 0.8), 0.04, (60, 56, 50))
    # Cage around orb
    cage = []
    for i in range(6):
        a = 2 * math.pi * i / 6
        cage += rod((0, -0.16, 0.7), (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.9), 0.015, gold)
    cage += r3.box((0, -0.16, 0.7), (0.2, 0.01, 0.2), gold)
    cage += r3.box((0, -0.16, 0.9), (0.2, 0.01, 0.2), gold)
    cage += r3.sphere((0, -0.16, 0.8), 0.09, orb, rings=5, sides=7)
    staff += cage
    return humanoid(b, pose, head=head, right_hand=staff, left_hand=[], extra=stole)


BUILDERS = {
    "fallen": fallen, "shaman": lambda p: fallen(p, shaman=True), "skeleton": skeleton, "zombie": zombie,
    "goatman": goatman, "gargoyle": gargoyle, "overlord": overlord, "azazel": azazel, "priest": priest, "witch": witch,
    "flayer": flayer, "zealot": zealot, "spider": spider, "bat": bat, "hulk": hulk,
    "drowned": drowned, "fetish": fetish, "inquisitor": inquisitor, "bone_priest": bone_priest,
}

#: Zombies shamble; overlords and the boss stride heavily; gargoyles flap rather than step.
GAITS = {"zombie": 0.6, "overlord": 0.75, "azazel": 0.7, "gargoyle": 0.5, "hulk": 0.7, "bat": 0.5,
         "flayer": 1.1, "zealot": 1.0, "spider": 1.2, "drowned": 0.7, "fetish": 1.0, "inquisitor": 0.95, "bone_priest": 0.6}


def pose_of(kind: str, frame: str) -> Pose:
    pose = ENHANCED_POSES[kind][frame] if kind in ENHANCED and frame in ENHANCED_POSES[kind] else POSES[frame]
    gait = GAITS.get(kind, 1.0)
    if kind not in ENHANCED and frame in WALK and gait != 1.0:
        pose = replace(pose, leg=pose.leg * gait, arm=pose.arm * gait)
    return pose


def mesh(kind: str, facing: str, frame: str) -> Mesh:
    pose = pose_of(kind, frame)
    built = BUILDERS[kind](pose)
    turn = {"front": 0.0, "front_right": -45.0, "right": -90.0, "back_right": -135.0,
            "back": 180.0, "back_left": 135.0, "left": 90.0, "front_left": 45.0,
            "side": -90.0}[facing]
    if kind == "zombie" and pose.death and facing not in ("back", "back_right", "back_left"):
        # A forward collapse is seen from the front and sides in true profile.
        built = on_ground(pitch(built, (0, -20, -43, -66, -82)[pose.death - 1], (0, 0, 0.06)))
    turned = yaw(built, turn)
    if kind == "zombie" and pose.death and facing in ("back", "back_right", "back_left"):
        # From behind, falling directly away would foreshorten to a standing-looking column.
        # Let the corpse topple sideways across the screen while the facing remains back.
        direction = -1 if facing == "back_left" else 1
        turned = on_ground(roll(turned, direction * (0, 18, 42, 68, 82)[pose.death - 1], (0, 0, 0.06)))
        if facing != "back" and pose.death >= 2:
            turned = move(turned, dx=0.07 if facing == "back_right" else -0.07)
    if kind == "fallen" and pose.death:
        # Screen-plane tumble after turning: the side views read as fallen bodies too.
        turned = on_ground(roll(turned, (0, 22, 50, 72, 86)[pose.death - 1], (0, 0, 0.07)))
        if pose.death >= 4:
            turned += blade((0.22, 0.08, 0.025), (0.42, 0.18, 0.025), 0.06, (196, 196, 206))
    return r3.scale(turned, SCALE)


# -- Cells ------------------------------------------------------------------------------------


@lru_cache(maxsize=None)
def cell(kind: str) -> tuple[tuple[int, int], tuple[float, float]]:
    """``((width, height), (origin_x, origin_y))`` of a frame image in logical pixels; the origin is the ground point."""
    if kind in ENHANCED_CELLS:
        return ENHANCED_CELLS[kind]
    left = top = right = 0.0
    bottom = 4.0
    for facing in facings(kind):
        for frame in frames(kind):
            x0, y0, x1, y1 = r3.bounds(mesh(kind, facing, frame), PROJECTION)
            left, right = min(left, x0), max(right, x1)
            top, bottom = min(top, y0), max(bottom, y1)
    half = max(-left, right) + 3
    width = int(2 * half + 0.5)
    height = int(bottom - top + 6 + 0.5)
    return (width, height), (width / 2, height - bottom - 3)


def render(kind: str, facing: str, frame: str) -> Image.Image:
    size, origin = cell(kind)
    return r3.render(mesh(kind, facing, frame), PROJECTION, scale=DENSITY, canvas=size, origin=origin)
