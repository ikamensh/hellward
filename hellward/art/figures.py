"""The monsters as posed low-poly figures: the stand-ins the painted sprites are made from.

Every monster has the same frames: a four-step walk (contact, passing, contact, passing), a three-phase
blow for battering doors (wind-up, strike, recover) and, for leaders, a two-phase incantation (raise,
chant). Each is drawn in three facings: ``front`` (walking towards the camera), ``back`` and ``side``
(walking to the right); walking left is the side facing mirrored. Poses are pushed past realistic so
they read at 30–80 px.

:func:`mesh` builds one frame; :func:`render` rasterises it into a cell whose feet sit on
:func:`cell` 's origin. Flyers are drawn hovering: their cell's origin is still the ground point.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from PIL import Image
from sagaforge import render3d as r3
from sagaforge.render3d import Mesh

from hellward.art.rig import DENSITY, PROJECTION, Vec, blade, move, pitch, rod, roll, wing, yaw
from hellward.sim.content import MONSTERS

FACINGS = ("front", "back", "side")
WALK = ("walk1", "walk2", "walk3", "walk4")
STRIKE = ("wind", "strike", "recover")
CAST = ("raise", "chant")
STRIDE = 0.2          # tiles walked per walk frame
SCALE = 2.0           # figures stand about twice life size on the tile grid: the camera shows height at 57%, and they must read at 1x


def frames(kind: str) -> tuple[str, ...]:
    return WALK + STRIKE + (CAST if MONSTERS[kind].leader else ())


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
        for side, swing in ((-1, pose.leg), (1, -pose.leg)):
            leg = rod((0, 0, 0), (0, 0.02, -hip + b.leg_w * 0.4), b.leg_w, b.legs_color)
            leg += r3.box((0, 0.05, -hip + b.leg_w * 0.35), (b.leg_w * 1.1, b.leg_w * 1.8, b.leg_w * 0.7), darker(b.legs_color, 0.6))
            mesh += move(pitch(leg, swing, (0, 0, 0)), side * lx, 0, hip)
    else:
        hem = 0.06 + 0.05 * abs(pose.leg) / 30
        skirt = r3.cone((0, 0, 0.0), b.torso[0] * 0.55 + hem, hip * 1.3, b.robe, sides=9)
        skirt = pitch(skirt, -pose.leg * 0.15, (0, 0, hip))
        mesh += skirt
        for side, swing in ((-1, pose.leg), (1, -pose.leg)):
            foot = r3.box((side * lx, 0.05 + swing * 0.003, 0.03), (b.leg_w, b.leg_w * 1.6, 0.06), darker(b.robe, 0.5))
            mesh += foot
    upper: Mesh = []
    tw, td, th = b.torso
    upper += r3.box((0, 0, hip + th / 2), (tw, td, th), b.body_color)
    upper += r3.box((0, 0, hip + th * 0.08), (tw * 1.05, td * 1.1, th * 0.16), darker(b.body_color, 0.6))  # belt
    upper += move(head, 0, 0.01, hip + th + b.head * 0.85)
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
    return humanoid(b, pose, head=head, right_hand=right, left_hand=[])


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
    return humanoid(b, pose, head=head, right_hand=sword, left_hand=shield, extra=ribs)


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


BUILDERS = {
    "fallen": fallen, "shaman": lambda p: fallen(p, shaman=True), "skeleton": skeleton, "zombie": zombie,
    "goatman": goatman, "gargoyle": gargoyle, "overlord": overlord, "azazel": azazel, "priest": priest, "witch": witch,
}

#: Zombies shamble; overlords and the boss stride heavily; gargoyles flap rather than step.
GAITS = {"zombie": 0.6, "overlord": 0.75, "azazel": 0.7, "gargoyle": 0.5}


def pose_of(kind: str, frame: str) -> Pose:
    pose = POSES[frame]
    gait = GAITS.get(kind, 1.0)
    if frame in WALK and gait != 1.0:
        pose = replace(pose, leg=pose.leg * gait, arm=pose.arm * gait)
    return pose


def mesh(kind: str, facing: str, frame: str) -> Mesh:
    built = BUILDERS[kind](pose_of(kind, frame))
    turn = {"front": 0.0, "back": 180.0, "side": -90.0}[facing]
    return r3.scale(yaw(built, turn), SCALE)


# -- Cells ------------------------------------------------------------------------------------


@lru_cache(maxsize=None)
def cell(kind: str) -> tuple[tuple[int, int], tuple[float, float]]:
    """``((width, height), (origin_x, origin_y))`` of a frame image in logical pixels; the origin is the ground point."""
    left = top = right = 0.0
    bottom = 4.0
    for facing in FACINGS:
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
