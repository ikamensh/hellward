"""Towers, gates, arches and pillars as low-poly stand-ins, drawn with the monsters' camera.

A tower stands on one tile: its model origin is the tile's centre on the ground. Each tower kind has
three ranks that grow taller and grander; the fire, the crystal, the ice and the venom glow drawn here
are the resting look, and the scene lays live light and particles over them.

A gate spans a corridor that runs down the screen; its origin is the door tile's centre. The arch
around it (two piers on the flanking wall tiles and a pointed lintel) is drawn separately, so the gate
can break while the arch stands.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image
from sagaforge import render3d as r3
from sagaforge.render3d import Mesh

from hellward.art.rig import DENSITY, PROJECTION, move, pitch, rod, roll, yaw

STONE = (92, 86, 84)
STONE_DARK = (62, 58, 60)
IRON = (58, 52, 52)
GOLD = (206, 164, 72)
BONE = (214, 204, 176)

TOWER_KINDS = ("pyre", "storm", "frost", "plague")
GATE_LOOKS = ("intact", "damaged", "broken")


def plinth(rank: int, color=STONE, top=STONE_DARK) -> Mesh:
    mesh = r3.box((0, 0, 0.07), (0.72, 0.64, 0.14), color)
    mesh += r3.box((0, 0, 0.18), (0.58, 0.5, 0.08), top)
    if rank >= 1:
        for x in (-0.3, 0.3):
            for y in (-0.26, 0.26):
                mesh += r3.cone((x, y, 0.14), 0.05, 0.12 + 0.06 * rank, (70, 64, 64), sides=5)
    return mesh


def flame(z: float, size: float) -> Mesh:
    mesh = r3.cone((0, 0, z), 0.16 * size, 0.42 * size, (255, 110, 30), sides=7)
    mesh += r3.cone((0.05 * size, 0.03, z), 0.1 * size, 0.3 * size, (255, 170, 50), sides=6)
    mesh += r3.cone((-0.06 * size, 0.02, z), 0.09 * size, 0.26 * size, (255, 140, 40), sides=6)
    mesh += r3.cone((0, 0.05, z), 0.07 * size, 0.2 * size, (255, 236, 150), sides=6)
    return mesh


def pyre(rank: int) -> Mesh:
    height = (0.95, 1.25, 1.55)[rank]
    mesh = plinth(rank)
    mesh += r3.cylinder((0, 0, 0.22), 0.15, height, STONE, sides=8)
    mesh += r3.cylinder((0, 0, 0.22 + height * 0.45), 0.17, 0.05, STONE_DARK, sides=8)   # a carved band
    top = 0.22 + height
    bowl = 0.22 + 0.06 * rank
    mesh += r3.cone((0, 0, top + 0.16), bowl, -0.2, IRON, sides=10)
    mesh += r3.cylinder((0, 0, top + 0.12), bowl + 0.02, 0.05, (84, 70, 62), sides=10)
    if rank >= 1:
        for i in range(4 + 2 * rank):
            a = 2 * math.pi * i / (4 + 2 * rank)
            mesh += r3.cone((math.cos(a) * bowl, math.sin(a) * bowl, top + 0.14), 0.025, 0.1 + 0.04 * rank, (40, 34, 34), sides=4)
    if rank == 2:
        mesh += r3.cylinder((0, 0, 0.22 + height * 0.75), 0.165, 0.04, GOLD, sides=8)
    mesh += flame(top + 0.15, 1.0 + 0.35 * rank)
    return mesh


def crystal(z: float, size: float, color, dark) -> Mesh:
    return r3.pyramid((0, 0, z), (size, size), size * 1.3, color) + r3.pyramid((0, 0, z), (size, size), -size * 1.0, dark)


def storm(rank: int) -> Mesh:
    height = (1.3, 1.65, 2.0)[rank]
    basalt = (54, 58, 74)
    mesh = plinth(rank, color=(70, 72, 84), top=(50, 52, 62))
    w = 0.28
    mesh += r3.box((0, 0, 0.22 + height / 2), (w, w, height), basalt)
    mesh += r3.pyramid((0, 0, 0.22 + height), (w, w), 0.14, (44, 48, 62))
    for i in range(3):   # glowing runes up the face
        mesh += r3.box((0, w / 2 + 0.005, 0.36 + i * height * 0.25), (0.08, 0.01, 0.06), (120, 200, 255))
    if rank >= 1:
        for i in range(rank + 1):   # copper coils
            mesh += r3.cylinder((0, 0, 0.3 + i * 0.22), w * 0.8, 0.035, (176, 110, 60), sides=8)
    z = 0.22 + height + 0.3
    mesh += crystal(z, 0.16 + 0.03 * rank, (140, 210, 255), (70, 130, 220))
    if rank == 2:
        for a in (0, 120, 240):
            x, y = 0.3 * math.cos(math.radians(a)), 0.3 * math.sin(math.radians(a))
            mesh += move(crystal(0, 0.07, (160, 220, 255), (80, 140, 220)), x, y, z - 0.1)
    return mesh


def frost(rank: int) -> Mesh:
    ice, deep = (176, 224, 246), (104, 164, 210)
    mesh = plinth(rank, color=(104, 112, 122), top=(84, 92, 104))
    spikes = [(0, 0, 0.62), (0.16, 0.05, 0.4), (-0.15, 0.07, 0.36), (0.05, -0.15, 0.34), (-0.07, 0.17, 0.3)]
    spikes += [(0.2, -0.12, 0.28), (-0.2, -0.1, 0.3)] if rank >= 1 else []
    for x, y, h in spikes:
        h *= (1.7, 2.1, 2.5)[rank]
        lean = math.degrees(math.atan2(math.hypot(x, y), 0.6)) * 0.9
        spike = r3.cylinder((0, 0, 0), 0.055, h * 0.7, ice, sides=6) + r3.cone((0, 0, h * 0.7), 0.055, h * 0.35, deep, sides=6)
        spike = pitch(spike, lean * (y / (math.hypot(x, y) or 1)), (0, 0, 0))
        spike = roll(spike, lean * (x / (math.hypot(x, y) or 1)), (0, 0, 0))
        mesh += move(spike, x, y, 0.22)
    if rank == 2:
        mesh += crystal(2.05, 0.15, (220, 244, 255), (130, 190, 235))
    return mesh


def plague(rank: int) -> Mesh:
    rot, glow = (78, 64, 50), (130, 230, 70)
    mesh = plinth(rank, color=(70, 64, 54), top=(52, 60, 42))
    mesh += r3.cylinder((0, 0, 0.18), 0.22, 0.08, (60, 90, 40), sides=10)   # a pool of venom
    height = (1.15, 1.45, 1.75)[rank]
    mesh += r3.cylinder((0, 0, 0.22), 0.05, height, rot, sides=6)
    skulls = 2 + rank
    for i in range(skulls):
        z = 0.34 + i * (height - 0.12) / skulls
        skull = r3.sphere((0, 0, 0), 0.085, BONE, rings=4, sides=7)
        skull += r3.box((0, 0.06, -0.035), (0.09, 0.05, 0.05), (196, 186, 160))
        for side in (-1, 1):
            skull += r3.box((side * 0.03, 0.078, 0.01), (0.025, 0.01, 0.022), glow)
        mesh += move(yaw(skull, (i % 2) * 40 - 20), 0, 0, z)
    top = 0.22 + height
    ram = r3.sphere((0, 0, 0), 0.1 + 0.02 * rank, BONE, rings=4, sides=7)
    for side in (-1, 1):
        ram += rod((side * 0.07, 0, 0.05), (side * 0.2, -0.05, 0.14), 0.04, (120, 110, 90))
        ram += rod((side * 0.2, -0.05, 0.14), (side * 0.22, 0.05, -0.02), 0.035, (100, 92, 76))
        ram += r3.box((side * 0.04, 0.09, 0.01), (0.03, 0.01, 0.03), glow)
    mesh += move(ram, 0, 0, top + 0.06)
    if rank >= 1:
        for side in (-1, 1):
            mesh += move(crystal(0, 0.06, glow, (70, 150, 40)), side * 0.28, 0.15, 0.3)
    return mesh


TOWER_BUILDERS = {"pyre": pyre, "storm": storm, "frost": frost, "plague": plague}


def gate(look: str) -> Mesh:
    """The warded gate across a corridor, 1 tile wide: two oak leaves bound in iron with a gilded ward."""
    oak, dark = (104, 70, 44), (74, 50, 32)
    mesh: Mesh = []
    if look == "broken":
        for x, h, t in ((-0.38, 0.22, -12), (-0.2, 0.12, 8), (0.1, 0.18, -6), (0.33, 0.28, 10)):
            mesh += roll(r3.box((x, 0, h / 2), (0.1, 0.07, h), oak), t, (x, 0, 0))
        for x, y, a in ((-0.2, 0.3, 30), (0.25, 0.25, -50), (0.0, -0.3, 80)):
            mesh += yaw(r3.box((x, y, 0.025), (0.42, 0.09, 0.04), dark), a, (x, y, 0))
        mesh += r3.box((0.1, 0.15, 0.02), (0.3, 0.04, 0.03), IRON)
        return mesh
    planks = 6
    for i in range(planks):
        x = -0.45 + (i + 0.5) * 0.9 / planks
        h = 1.45 - 0.08 * abs(i - (planks - 1) / 2)
        if look == "damaged" and i in (1, 4):
            h *= 0.55
        color = oak if i % 2 else dark
        mesh += r3.box((x, 0, h / 2), (0.9 / planks - 0.01, 0.08, h), color)
    for z in (0.25, 0.8, 1.2):
        band = r3.box((0, 0.045, z), (0.92, 0.02, 0.06), IRON)
        if look == "damaged" and z == 0.8:
            band = roll(band, 8, (0, 0, z))
        mesh += band
    mesh += r3.box((0, 0.06, 0.68), (0.03, 0.01, 1.3), (40, 34, 30))   # the seam between the leaves
    ward = r3.cylinder((0, 0, 0), 0.14, 0.012, GOLD, sides=12)
    mesh += move(pitch(ward, 90, (0, 0, 0)), 0, 0.06, 0.95)
    mesh += r3.box((0, 0.07, 0.95), (0.03, 0.01, 0.2), (255, 230, 150))
    mesh += r3.box((0, 0.07, 0.99), (0.14, 0.01, 0.035), (255, 230, 150))
    return mesh


def arch() -> Mesh:
    """Two piers on the flanking wall tiles and a pointed lintel over the door tile."""
    mesh: Mesh = []
    for side in (-1, 1):
        mesh += r3.box((side * 0.92, 0, 0.95), (0.8, 0.7, 1.9), (82, 76, 76))
        mesh += r3.box((side * 0.92, 0, 1.93), (0.88, 0.78, 0.1), (66, 62, 64))
        mesh += r3.pyramid((side * 0.92, 0, 1.98), (0.5, 0.5), 0.35, (70, 64, 66))   # a pinnacle
        mesh += r3.box((side * 0.54, 0.12, 0.85), (0.08, 0.46, 1.7), (96, 90, 88))   # the jamb
    mesh += r3.box((0, 0, 1.75), (1.0, 0.4, 0.28), (88, 82, 80))
    mesh += r3.pyramid((0, 0, 1.89), (1.0, 0.4), 0.45, (74, 68, 70))
    mesh += r3.box((0, 0.21, 1.72), (0.16, 0.02, 0.16), (206, 164, 72))    # a keystone ward
    return mesh


def pillar() -> Mesh:
    mesh = r3.box((0, 0, 0.08), (0.62, 0.62, 0.16), STONE_DARK)
    mesh += r3.cylinder((0, 0, 0.16), 0.19, 1.6, (100, 94, 92), sides=10)
    mesh += r3.box((0, 0, 1.8), (0.5, 0.5, 0.12), STONE_DARK)
    for i in range(3):   # a candelabrum on top
        x = (i - 1) * 0.14
        mesh += r3.cylinder((x, 0, 1.86), 0.03, 0.12, (230, 220, 200), sides=5)
        mesh += r3.cone((x, 0, 1.98), 0.02, 0.06, (255, 200, 90), sides=5)
    return mesh


def _render(mesh: Mesh, canvas: tuple[float, float], origin: tuple[float, float]) -> Image.Image:
    return r3.render(mesh, PROJECTION, scale=DENSITY, canvas=canvas, origin=origin)


TOWER_CELL = ((72, 150), (36, 128))    # (canvas, origin of the tile centre) in logical px
GATE_CELL = ((60, 80), (30, 60))
ARCH_CELL = ((136, 150), (68, 118))
PILLAR_CELL = ARCH_CELL                 # the two share a painted sheet, and a sheet has one cell


@lru_cache(maxsize=None)
def tower_image(kind: str, rank: int) -> Image.Image:
    return _render(TOWER_BUILDERS[kind](rank), *TOWER_CELL)


@lru_cache(maxsize=None)
def gate_image(look: str) -> Image.Image:
    return _render(gate(look), *GATE_CELL)


@lru_cache(maxsize=None)
def arch_image() -> Image.Image:
    return _render(arch(), *ARCH_CELL)


@lru_cache(maxsize=None)
def pillar_image() -> Image.Image:
    return _render(pillar(), *PILLAR_CELL)


def tower_top(kind: str, rank: int) -> float:
    """Height in tiles of the tower's burning, glowing or grinning top: where its magic leaves from."""
    return {
        "pyre": 0.22 + (0.95, 1.25, 1.55)[rank] + 0.3,
        "storm": 0.22 + (1.3, 1.65, 2.0)[rank] + 0.45,
        "frost": 0.22 + 0.62 * (1.7, 2.1, 2.5)[rank] * 1.02,
        "plague": 0.22 + (1.15, 1.45, 1.75)[rank] + 0.08,
    }[kind]
