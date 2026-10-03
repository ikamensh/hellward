"""The Carver: a small ember-orange imp of the Fallen family with a crude cleaver in its right fist.

Hand-modelled (art/concept/carver.png; no generated sculpt): the body is built here from primitives, one flat
paint per part, and tools/blender/biped.py rigs it, bakes its maps from the mesh itself and walks it on the
imps' keyed cycle. build_imp is shared with the other two tiers (mon_devilkin.py, mon_dark_one.py)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import sculpted
from biped import HandBody, Spec, build, h_ball, h_box, h_cone, h_join, h_limb, h_paint  # noqa: E402


def C(r: float, g: float, b: float):
    """An sRGB paint as the linear vertex colour the albedo bake reads."""
    return tuple(((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b))


def LAB(rgb) -> tuple:
    """A paint's Lab centre for the material families (the same conversion family_weights uses)."""
    return tuple(float(v) for v in sculpted.to_lab(np.array([rgb]))[0])


# the tiers' shared skeleton (the right side; the left mirrors): a 1.15 m imp in an A-pose, facing +Y
JOINTS = {"hips": (0, 0, 0.62), "spine": (0, -0.005, 0.72), "chest": (0, 0, 0.84), "neck": (0, 0.005, 0.925),
          "skull": (0, 0.015, 0.985), "crown": (0, 0.015, 1.075)}
for _s, _side in ((1, "R"), (-1, "L")):
    JOINTS |= {f"shoulder.{_side}": (_s * 0.105, 0, 0.875), f"elbow.{_side}": (_s * 0.215, 0.005, 0.72),
               f"wrist.{_side}": (_s * 0.30, 0.01, 0.575), f"fingers.{_side}": (_s * 0.345, 0.015, 0.50),
               f"hip.{_side}": (_s * 0.065, 0, 0.60), f"knee.{_side}": (_s * 0.08, 0.025, 0.33),
               f"ankle.{_side}": (_s * 0.085, 0, 0.10), f"toe.{_side}": (_s * 0.085, 0.125, 0.035),
               f"heel.{_side}": (_s * 0.085, -0.045, 0.035)}

SOLE = {"ankle_z": 0.10, "heel": (-0.045, -0.065), "toe": (0.125, -0.065), "lift": 0.08}
EYES_AT = ((0.030, 1.028), (-0.030, 1.028))
FIST = (0.32, 0.012, 0.54)   # the right fist's centre (wrist to fingers, 0.45 along)

LOOKS = {
    "skin": {"colour": sculpted.grade(mottle=0.16, scale=0.03, grime=0.4, knee=0.35), "rough": sculpted.hide_rough},
    "leather": {"colour": sculpted.grade(mottle=0.2, scale=0.025), "rough": 0.9},
    "horn": {"colour": sculpted.grade(mottle=0.08, scale=0.02), "rough": 0.55},
    "steel": {"colour": sculpted.grade(sat=0.9, mottle=0.25, scale=0.02),
              "rough": lambda ao: 0.35 + 0.4 * (1 - ao), "metal": 0.35},
}


def families_for(paints: dict) -> dict:
    horn = [LAB(paints["horn"]), LAB(paints["dark"])]
    if "bone" in paints:
        horn.append(LAB(paints["bone"]))
    return {"skin": [LAB(paints["hide"])], "leather": [LAB(paints["leather"])], "horn": horn,
            "steel": [LAB(paints["steel"]), LAB(paints["iron"])]}


def _blade_test(elbow, wrist):
    """Verts of the gripped blade (never the forearm's own: it runs just behind the blade's window)."""
    import mathutils
    a, b = mathutils.Vector(elbow), mathutils.Vector(wrist)
    ab = b - a
    fx, fy = FIST[0], FIST[1]

    def near_arm(co) -> bool:
        u = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
        return ((co - (a + ab * u)).length < 0.032)

    def inside(co) -> bool:
        if near_arm(co):
            return False
        if 0.47 < co.z < 0.60:
            return ((co.x - fx) ** 2 + (co.y - fy) ** 2) ** 0.5 < 0.045
        return abs(co.x - fx) < 0.028 and abs(co.y - fy) < 0.028 and 0.60 <= co.z < 0.88

    return inside


def build_imp(kind: str, height: float, paints: dict, horns: list, extras=None, bulk: float = 1.0,
              iron_wraps: bool = False) -> HandBody:
    """A Fallen-family tier: `horns` [(base, tip, r), ...] per side in +X (mirrored), `extras(parts)` adds the
    kind's own gear (necklace, collar). `paints`: hide, leather, horn, dark, steel, iron, eye (linear)."""
    P, parts = paints, []
    add = lambda o, paint: parts.append(h_paint(o, P[paint]))  # noqa: E731
    R = lambda r: r * bulk   # noqa: E731

    add(h_ball("pelvis", (0, 0, 0.60), R(0.105), (1.0, 0.85, 0.8)), "hide")
    add(h_ball("belly", (0, 0.008, 0.715), R(0.10), (0.95, 0.85, 1.0)), "hide")
    add(h_ball("chest", (0, 0, 0.845), R(0.11), (1.05, 0.8, 0.95)), "hide")
    add(h_limb("neck", (0, 0.005, 0.895), (0, 0.015, 0.965), R(0.045), R(0.042)), "hide")
    add(h_ball("head", (0, 0.02, 1.015), 0.082, (1.0, 0.95, 1.05)), "hide")
    add(h_ball("jaw", (0, 0.07, 0.98), 0.048, (0.8, 0.9, 0.7)), "hide")
    add(h_ball("brow", (0, 0.055, 1.045), 0.045, (1.1, 0.7, 0.5)), "hide")
    for s in (1, -1):
        sh, el, wr, fg = (JOINTS[f"{b}.{'R' if s > 0 else 'L'}"] for b in ("shoulder", "elbow", "wrist", "fingers"))
        Sx = lambda x: s * x  # noqa: E731
        add(h_ball(f"delt.{s}", (Sx(0.105), 0, 0.875), R(0.045)), "hide")
        add(h_limb(f"upper.{s}", sh, el, R(0.034), R(0.029)), "hide")
        add(h_ball(f"elb.{s}", el, R(0.030)), "hide")
        add(h_limb(f"fore.{s}", el, wr, R(0.029), R(0.023)), "hide")
        fist = (Sx(0.32), 0.012, 0.54)
        add(h_ball(f"fist.{s}", fist, R(0.034), (0.9, 1.0, 1.15)), "hide")
        for i, dx in enumerate((-0.018, 0.0, 0.018)):
            add(h_cone(f"claw.{s}.{i}", (fist[0] + dx, 0.030, 0.520), (fist[0] + dx, 0.042, 0.482), 0.008), "dark")
        hip, knee, ank = (JOINTS[f"{b}.{'R' if s > 0 else 'L'}"] for b in ("hip", "knee", "ankle"))
        add(h_limb(f"thigh.{s}", hip, knee, R(0.048), R(0.036)), "hide")
        add(h_ball(f"knee.{s}", knee, R(0.038)), "hide")
        add(h_limb(f"shin.{s}", knee, ank, R(0.034), R(0.022)), "hide")
        add(h_ball(f"ank.{s}", ank, R(0.024)), "hide")
        for i, dx in enumerate((-0.023, 0.023)):
            add(h_box(f"hoof.{s}.{i}", (Sx(0.085) + dx, 0.045, 0.032), (0.042, 0.13, 0.062)), "dark")
        add(h_cone(f"ear.{s}", (Sx(0.055), 0.005, 1.045), (Sx(0.21), -0.03, 1.10), 0.034, squash=(1, 0.45, 1)),
            "hide")
        for i, (base, tip, r) in enumerate(horns):
            add(h_cone(f"horn.{s}.{i}", (Sx(base[0]), base[1], base[2]), (Sx(tip[0]), tip[1], tip[2]), r), "horn")
        mid0 = tuple(el[j] + (wr[j] - el[j]) * 0.35 for j in range(3))
        mid1 = tuple(el[j] + (wr[j] - el[j]) * 0.75 for j in range(3))
        add(h_limb(f"wrap.{s}", mid0, mid1, R(0.033), R(0.028)), "iron" if iron_wraps else "leather")
    for i, s in enumerate((1, -1)):
        add(h_ball(f"eye.{i}", (s * 0.030, 0.088, 1.028), 0.013), "eye")
    beltr = R(0.115)
    add(h_ball("belt", (0, 0, 0.635), beltr, (1.0, 0.88, 0.22)), "leather")
    add(h_box("buckle", (0, beltr * 0.88, 0.635), (0.045, 0.015, 0.035)), "iron")
    add(h_box("cloth.f", (0, 0.095, 0.51), (0.125, 0.018, 0.17)), "leather")
    add(h_box("cloth.b", (0, -0.095, 0.51), (0.125, 0.018, 0.17)), "leather")
    strapy = R(0.088) + 0.002
    add(h_box("strap.l", (-0.03, strapy, 0.83), (0.028, 0.014, 0.24), rot=(0, 0, 25)), "leather")
    add(h_box("strap.r", (0.03, strapy, 0.83), (0.028, 0.014, 0.24), rot=(0, 0, -25)), "leather")
    # the cleaver, upright in the right fist (rigid to the hand: it never leaves the grip)
    fx, fy, fz = FIST
    add(h_limb("grip", (fx, fy, fz - 0.055), (fx, fy, fz + 0.02), 0.013, 0.013), "leather")
    add(h_box("guard", (fx, fy, fz + 0.032), (0.085, 0.022, 0.018)), "iron")
    add(h_box("blade", (fx, fy, fz + 0.145), (0.046, 0.011, 0.21)), "steel")
    add(h_cone("tip", (fx, fy, fz + 0.245), (fx, fy, fz + 0.30), 0.023, squash=(1, 0.24, 1)), "steel")
    if extras:
        extras(parts, add, P)
    obj = h_join(parts, kind)
    return HandBody(obj, dict(JOINTS), height, rigid={"hand.R": _blade_test(JOINTS["elbow.R"], JOINTS["wrist.R"])},
                    sole=dict(SOLE))


CARVER = {n: C(*v) for n, v in {
    "hide": (0.60, 0.20, 0.08), "leather": (0.23, 0.14, 0.09), "horn": (0.82, 0.74, 0.58),
    "dark": (0.10, 0.08, 0.07), "steel": (0.52, 0.55, 0.58), "iron": (0.28, 0.27, 0.28),
    "eye": (1.0, 0.85, 0.20)}.items()}
CARVER_HORNS = [((0.032, 0.005, 1.075), (0.048, -0.025, 1.15), 0.016)]


def make_carver() -> HandBody:
    return build_imp("carver", 1.15, CARVER, CARVER_HORNS)


if __name__ == "__main__":
    build(Spec("carver", 1.15, hand=make_carver, eyes=(1.0, 0.72, 0.15), eyes_at=EYES_AT, eyes_find="fixed",
               families=families_for(CARVER), looks=LOOKS,
               keyed={"k": 1.085, "stride": 0.16, "walk_s": 0.7, "idle_s": 3.0, "crouch": 0.1}))
