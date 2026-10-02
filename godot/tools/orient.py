"""Which faces of a generated mesh point into its own body (sculpted.outward runs this).

    python tools/orient.py IN.npz OUT.npz

IN holds verts (N, 3), faces (M, 3) and normals (M, 3); OUT holds inward (M,), true for a face whose normal points
into the solid. The surface is voxelised (tools/skinweights.py's shell and solid), and a face points inward when
the points a little in front of it along its normal lie inside the solid and those behind it outside. A sheet open
on both sides (a cloth strip, an ear's edge) has outside on both sides and is never flagged.
"""
import sys

import numpy as np

from skinweights import shell, solid


def inward(verts: np.ndarray, faces: np.ndarray, normals: np.ndarray, cell: float = 0.004) -> np.ndarray:
    pad = 4 * cell
    origin = verts.min(0) - pad
    dims = tuple(np.ceil((verts.max(0) + pad - origin) / cell).astype(int) + 1)
    inside = solid(shell(verts, faces, origin, cell, dims))
    centre = verts[faces].mean(1)

    def at(p):
        idx = np.clip(np.floor((p - origin) / cell).astype(int), 0, np.array(dims) - 1)
        return inside[idx[:, 0], idx[:, 1], idx[:, 2]]
    flagged = np.ones(len(faces), bool)
    for d in (2.5, 4.0):   # in voxels: past the dilated shell, short of a finger's far side
        # inward: the solid in front of the face and the open air behind it (a face pressed against another
        # part, an arm against the ribs, has the solid on both sides and stays as it is)
        flagged &= at(centre + normals * d * cell) & ~at(centre - normals * d * cell)
    return flagged


if __name__ == "__main__":
    d = np.load(sys.argv[1])
    flags = inward(d["verts"], d["faces"], d["normals"])
    print(f"orient: {int(flags.sum())} of {len(flags)} faces point into the body")
    np.savez(sys.argv[2], inward=flags)
