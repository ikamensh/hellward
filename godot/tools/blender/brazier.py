"""An iron brazier: a spun bowl with a rolled lip, held by three tripod legs that rise from scrolled feet, hug
the bowl and curl over its rim; a ring braces the legs, a turned knob hangs under the bowl. Coals heap in it:
dark lumps on a glowing bed. The game adds flames and light at `fx_fire_1`, on the coals."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from village import Mesh, Vector, Z, finish, newell  # noqa: E402

m = Mesh("brazier", seed=41)
r = m.rng
B = 0.86          # the bowl's foot
COALS = B + 0.29  # the top of the heap, level with the rim


def revolve(profile, sides: int, mat: str, metres: float = 0.6, smooth: bool = True, phase: float = 0.0):
    """Turn (radius, z) pairs about the Z axis. Faces look to the right of the direction the profile runs:
    out when it climbs an outside, up over a rim, in when it drops down an inside."""
    rings = []
    for rad, z in profile:
        if rad < 1e-6:
            rings.append([m.bm.verts.new((0, 0, z))] * sides)
        else:
            rings.append([m.bm.verts.new((rad * math.cos(phase + 2 * math.pi * j / sides),
                                          rad * math.sin(phase + 2 * math.pi * j / sides), z)) for j in range(sides)])
    s = 0.0
    for i in range(len(profile) - 1):
        (r0, z0), (r1, z1) = profile[i], profile[i + 1]
        seg = math.hypot(r1 - r0, z1 - z0)
        v0, v1 = s / metres, (s + seg) / metres
        s += seg
        for j in range(sides):
            j1 = (j + 1) % sides
            quad = [rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]]
            u0 = j / sides * 2 * math.pi * max(r0, r1, 0.05) / metres
            u1 = (j + 1) / sides * 2 * math.pi * max(r0, r1, 0.05) / metres
            uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            keep = [k for k in range(4) if quad[k] is not quad[k - 1]]   # a ring shrunk to a point: a triangle
            quad, uvs = [quad[k] for k in keep], [uvs[k] for k in keep]
            a = 2 * math.pi * (j + 0.5) / sides + phase
            want = Vector((math.cos(a), math.sin(a), 0)) * (z1 - z0) - Z * (r1 - r0)
            if newell([v.co for v in quad]).dot(want) < 0:
                quad, uvs = quad[::-1], uvs[::-1]
            m.face(quad, uvs, mat, smooth)


# the bowl: outside up to a rolled lip, then down the inside to below the coals
revolve([(0.0, B), (0.1, B + 0.005), (0.18, B + 0.03), (0.25, B + 0.08), (0.298, B + 0.138), (0.312, B + 0.15),
          (0.316, B + 0.163), (0.336, B + 0.215), (0.35, B + 0.258), (0.374, B + 0.27), (0.386, B + 0.288),
          (0.373, B + 0.305), (0.347, B + 0.302), (0.332, B + 0.285), (0.316, B + 0.235), (0.285, B + 0.165)], 14, "iron")
# a turned knob under it
revolve([(0.0, B - 0.14), (0.022, B - 0.11), (0.04, B - 0.06), (0.032, B - 0.025), (0.075, B + 0.002)], 8, "iron")

# three legs: scrolled feet, a splayed rise, along the bowl's flank and over its lip into a curl
LEG = [(0.505, 0.062), (0.532, 0.058), (0.543, 0.034), (0.522, 0.014), (0.485, 0.014), (0.452, 0.04), (0.415, 0.11),
       (0.372, 0.23), (0.31, 0.45), (0.255, 0.65), (0.218, 0.79), (0.202, 0.87), (0.206, B + 0.035), (0.272, B + 0.085),
       (0.321, B + 0.15), (0.356, B + 0.218), (0.372, B + 0.262), (0.404, B + 0.3), (0.416, B + 0.345),
       (0.44, B + 0.395), (0.474, B + 0.41), (0.496, B + 0.388), (0.488, B + 0.36), (0.462, B + 0.358)]
for k in range(3):
    a = math.radians(90 + 120 * k)
    out = Vector((math.cos(a), math.sin(a), 0))
    m.tube([out * rad + Z * z for rad, z in LEG], 0.018, 5, "iron", metres=0.6, hint=Z)
# the brace: a ring through the legs
RING_Z, RING_R = 0.42, 0.318
m.tube([Vector((math.cos(2 * math.pi * i / 18) * RING_R, math.sin(2 * math.pi * i / 18) * RING_R, RING_Z))
        for i in range(19)], 0.012, 4, "iron", metres=0.6, caps=(False, False), hint=Z)

# the coals: a glowing bed under a heap of dark lumps, a few of them still burning bright
revolve([(0.304, B + 0.2), (0.25, B + 0.24), (0.17, B + 0.268), (0.085, B + 0.284), (0.0, COALS)], 16, "glow_fire")
GOLDEN = math.pi * (3 - math.sqrt(5))
for k in range(42):   # spread evenly over the bed, so it glows only in the cracks between them
    s = r.uniform(0.055, 0.095)
    rad = min(0.296 - s * 0.55, 0.284 * math.sqrt((k + 0.5) / 42) + r.uniform(-0.015, 0.015))   # inside the wall
    a = k * GOLDEN + r.uniform(-0.2, 0.2)
    bed = B + 0.2 + 0.09 * (1 - (rad / 0.304) ** 2)
    m.rock((math.cos(a) * rad, math.sin(a) * rad, bed + s * 0.2), (s, s * r.uniform(0.7, 1.0), s * r.uniform(0.5, 0.75)),
           "glow_fire" if k % 7 == 3 else "charred", metres=0.5)
finish("brazier", [m], fx=[("fx_fire_1", (0, 0, COALS))])
