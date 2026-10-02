"""Fit a biped's joints to a generated body standing in an A-pose (tools/blender/biped.py runs this).

    python tools/fit_skeleton.py IN.npz OUT.json

IN holds verts (N, 3) of a body in the model contract: Z up, facing +Y, its soles on z = 0, arms held away from the
body. Joints are read off horizontal slices of the body:

- the armpit is the highest slice in which a gap separates the arm from the torso; the shoulder joint sits above it
  in the root of the arm, the hand is the body's most lateral point at arm height, elbow and wrist on the way;
- the crotch is the lowest slice that has body across the middle; a floor-length robe has body across the middle
  almost to the floor, and its legs are then placed by proportion inside it; a hip sits above the middle of each
  leg's slice under the crotch, the ankle above the foot, the knee between;
- the neck is the narrowest slice between the shoulders and the crown.

OUT is {"joints": {name: [x, y, z]}, "robe": bool, "height": h}; the right side (+X) is named .R, the left .L.
"""
import json
import sys

import numpy as np


def slab(verts: np.ndarray, z: float, h: float) -> np.ndarray:
    return verts[np.abs(verts[:, 2] - z) < 0.008 * h]


def intervals(xs: np.ndarray, gap: float) -> list[tuple[float, float]]:
    """Sorted values split where consecutive ones are more than `gap` apart, as (low, high) intervals."""
    if len(xs) == 0:
        return []
    cut = np.flatnonzero(np.diff(xs) > gap)
    starts = np.concatenate([[0], cut + 1])
    ends = np.concatenate([cut, [len(xs) - 1]])
    return [(xs[a], xs[b]) for a, b in zip(starts, ends)]


def armpit(verts: np.ndarray, h: float, s: int, hand: np.ndarray):
    """(z, the arm's inner edge) where the arm, followed up from the hand slice by slice, joins the torso on side
    s: the last slice in which its interval of |x| is still parted from the one nearest the middle."""
    arm = (s * hand[0] - 0.04 * h, s * hand[0])
    last = (hand[2], arm[0])
    for z in np.arange(hand[2] + 0.02 * h, 0.95 * h, 0.005 * h):
        q = slab(verts, z, h)
        ivs = intervals(np.sort(s * q[q[:, 0] * s > 0][:, 0]), 0.012 * h)
        hit = [iv for iv in ivs if iv[1] >= arm[0] - 0.02 * h and iv[0] <= arm[1] + 0.02 * h]
        if not hit:
            break
        iv = (min(i[0] for i in hit), max(i[1] for i in hit))
        if iv[0] < 0.03 * h or len(ivs) == 1:   # the arm has run into the torso: the armpit was the last slice
            break
        arm, last = iv, (z, iv[0])
    return last


def fit(verts: np.ndarray, hands_below: float = 0.85, hands_within: float = 1.0) -> dict:
    h = verts[:, 2].max()
    x, y, z = verts[:, 0], verts[:, 1], verts[:, 2]
    joints = {}
    hands, pits = {}, {}
    for s in (1, -1):
        # under a winged body's wings, and no further out than an arm reaches
        band = (z > 0.25 * h) & (z < hands_below * h) & (s * x > 0) & (s * x < hands_within * h)
        hands[s] = verts[band][np.argmax(s * x[band])]
        za, xa = armpit(verts, h, s, hands[s])
        if 0.6 * h < za < 0.9 * h and 0.04 * h < xa < 0.25 * h:   # a plausible armpit
            pits[s] = (za, xa)
    # a hand resting on a thigh merges with the body at once: that side takes the other's armpit (generated
    # bodies are near symmetric), and with neither, proportion
    for s in (1, -1):
        if s not in pits:
            pits[s] = pits.get(-s, (0.74 * h, 0.12 * h))
    shoulders = []
    for s, side in ((1, "R"), (-1, "L")):
        za, xa = pits[s]
        hand = hands[s]
        root = slab(verts, za + 0.03 * h, h)
        root = root[s * root[:, 0] > xa - 0.01 * h]
        shoulder = np.array([s * min(max(xa + 0.01 * h, 0.09 * h), 0.17 * h),
                             root[:, 1].mean() if len(root) else 0.0, min(max(za + 0.05 * h, 0.72 * h), 0.84 * h)])
        joints[f"shoulder.{side}"] = shoulder
        joints[f"elbow.{side}"] = shoulder + (hand - shoulder) * 0.47
        joints[f"wrist.{side}"] = shoulder + (hand - shoulder) * 0.84
        joints[f"fingers.{side}"] = hand
        shoulders.append(shoulder)
    # the crotch: the lowest slice with body across the middle
    crotch = None
    for zc in np.arange(0.05 * h, 0.7 * h, 0.005 * h):
        q = slab(verts, zc, h)
        if (np.abs(q[:, 0]) < 0.012 * h).sum() >= 3:
            crotch = zc
            break
    crotch = 0.45 * h if crotch is None else crotch
    robe = crotch < 0.22 * h
    for s, side in ((1, "R"), (-1, "L")):
        feet = verts[(z < 0.04 * h) & (s * x > 0.01 * h)]
        foot = feet.mean(0) if len(feet) > 5 else np.array([s * 0.08 * h, 0.0, 0.0])
        if robe:
            hip = np.array([s * 0.07 * h, foot[1], 0.5 * h])
        else:
            # a skirt, a loincloth or mail hides the true crotch: the hip joint is at least half the height up,
            # and in from the middle of the leg's slice (legs splay in an A-pose)
            leg = slab(verts, crotch - 0.05 * h, h)
            leg = leg[s * leg[:, 0] > 0]
            mid = leg.mean(0) if len(leg) else np.array([s * 0.08 * h, 0, 0])
            hip = np.array([s * min(max(0.6 * abs(mid[0]), 0.05 * h), 0.09 * h), mid[1],
                            min(max(crotch + 0.04 * h, 0.5 * h), 0.58 * h)])
        back, front = (feet[:, 1].min(), feet[:, 1].max()) if len(feet) > 5 else (foot[1] - 0.05 * h, foot[1] + 0.07 * h)
        ankle = np.array([foot[0], back + 0.25 * (front - back), 0.055 * h])   # over the back quarter of the sole
        knee = (hip + ankle) / 2 + np.array([0, 0.012 * h, 0])
        toe = np.array([foot[0], front - 0.01 * h, 0.01 * h])
        joints[f"heel.{side}"] = np.array([foot[0], back, 0.0])
        joints[f"hip.{side}"] = hip
        joints[f"knee.{side}"] = knee
        joints[f"ankle.{side}"] = ankle
        joints[f"toe.{side}"] = toe
    sz = (shoulders[0][2] + shoulders[1][2]) / 2
    # the neck: the narrowest slice between the shoulders and the crown
    best, neck_z = None, None
    for zc in np.arange(sz, h - 0.06 * h, 0.005 * h):
        q = slab(verts, zc, h)
        if len(q) < 8:
            continue
        w = np.ptp(q[:, 0])
        if best is None or w < best:
            best, neck_z = w, zc
    neck_z = sz + 0.08 * h if neck_z is None else neck_z
    centre_y = lambda zc: slab(verts, zc, h)[:, 1].mean()   # noqa: E731
    hips_z = (joints["hip.R"][2] + joints["hip.L"][2]) / 2 + 0.02 * h
    top = sz - 0.02 * h
    joints["hips"] = np.array([0.0, centre_y(hips_z), hips_z])
    joints["spine"] = np.array([0.0, centre_y(hips_z + 0.35 * (top - hips_z)), hips_z + 0.35 * (top - hips_z)])
    joints["chest"] = np.array([0.0, centre_y(hips_z + 0.68 * (top - hips_z)), hips_z + 0.68 * (top - hips_z)])
    joints["neck"] = np.array([0.0, centre_y(top), top])
    joints["skull"] = np.array([0.0, centre_y(neck_z), neck_z])
    joints["crown"] = np.array([0.0, verts[np.argmax(z)][1], h])
    return {"joints": {k: [float(c) for c in v] for k, v in joints.items()}, "robe": bool(robe), "height": float(h)}


if __name__ == "__main__":
    d = np.load(sys.argv[1])
    out = fit(d["verts"], float(d["hands_below"]), float(d["hands_within"]))
    print("fit_skeleton:", "robe" if out["robe"] else "legs", f"height {out['height']:.2f}")
    with open(sys.argv[2], "w") as f:
        json.dump(out, f, indent=1)
