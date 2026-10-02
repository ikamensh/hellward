"""Skin weights for a generated body by geodesic distance through its voxelised solid (sculpted.skin runs this).

    python tools/skinweights.py IN.npz OUT.npz

IN holds verts (N, 3), faces (M, 3), heads and tails (B, 3) of the deforming bones, optionally allow (N, B: which
bones each vertex may follow), cell (voxel size, metres) and
sigma (how wide a joint's blend is, metres: one value, or one per vertex, small where the body is rigid bone and
large where it is flesh or cloth). OUT holds weights (N, B), at most four per vertex, summing to one.

Generated meshes are not watertight, which defeats Blender's heat weighting. Here the surface is rasterised
into a shell of voxels (thick enough to close small holes), the space the outside cannot reach becomes the
interior, and each bone's distance to every voxel is measured inside that solid: an arm's distance to the
torso goes round through the shoulder, a thigh's to the other thigh through the crotch, so weights never jump
a gap the way plain nearest-bone weights do.
"""
import sys

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree


def shell(verts: np.ndarray, faces: np.ndarray, origin: np.ndarray, cell: float, dims) -> np.ndarray:
    grid = np.zeros(dims, bool)
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    longest = np.max(np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1),
                               np.linalg.norm(a - c, axis=1)]), axis=0)
    steps = np.maximum(1, np.ceil(longest / (cell * 0.5)).astype(int))
    for n in np.unique(steps):
        sel = steps == n
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        keep = i + j <= n
        u, v = (i[keep] / n)[:, None], (j[keep] / n)[:, None]
        pts = (a[sel][:, None] * (1 - u - v).T[..., None] + b[sel][:, None] * u.T[..., None]
               + c[sel][:, None] * v.T[..., None]).reshape(-1, 3)
        idx = np.floor((pts - origin) / cell).astype(int)
        grid[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    return ndimage.binary_dilation(grid, iterations=1)


def solid(sh: np.ndarray) -> np.ndarray:
    labels, _ = ndimage.label(~sh)
    outside = labels == labels[0, 0, 0]
    return ~outside


def graph(mask: np.ndarray, cell: float):
    idx = -np.ones(mask.shape, int)
    cells = np.argwhere(mask)
    idx[tuple(cells.T)] = np.arange(len(cells))
    rows, cols, w = [], [], []
    for d in np.argwhere(np.ones((3, 3, 3))) - 1:
        if not d.any() or tuple(d) < (0, 0, 0):
            continue
        nb = cells + d
        ok = np.all((nb >= 0) & (nb < mask.shape), axis=1)
        src, dst = np.flatnonzero(ok), idx[tuple(nb[ok].T)]
        good = dst >= 0
        rows.append(src[good])
        cols.append(dst[good])
        w.append(np.full(good.sum(), np.linalg.norm(d) * cell))
    r, c, ww = np.concatenate(rows), np.concatenate(cols), np.concatenate(w)
    n = len(cells)
    g = coo_matrix((np.concatenate([ww, ww]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(n, n))
    return cells, g.tocsr()


def weights(verts, faces, heads, tails, cell=0.01, sigma=0.025, smooth=6, allow=None) -> np.ndarray:
    """`allow` (N, B), when given, says which bones each vertex may follow (a cloth bone only its cloth)."""
    sigma = np.asarray(sigma, float)
    pad = 4 * cell
    origin = verts.min(0) - pad
    dims = tuple(np.ceil((verts.max(0) + pad - origin) / cell).astype(int) + 1)
    mask = solid(shell(verts, faces, origin, cell, dims))
    cells, g = graph(mask, cell)
    centres = origin + (cells + 0.5) * cell
    tree = cKDTree(centres)
    dist = np.empty((len(verts), len(heads)))
    vd, vi = tree.query(verts)
    for k, (h, t) in enumerate(zip(heads, tails)):
        n = max(2, int(np.linalg.norm(t - h) / (cell / 3)) + 1)
        seeds = np.unique(tree.query(h + np.linspace(0, 1, n)[:, None] * (t - h))[1])
        geo = dijkstra(g, indices=seeds, min_only=True)
        dist[:, k] = geo[vi] + vd
    lost = ~np.isfinite(dist).any(1)   # pieces the solid does not join to any bone: straight-line distance
    if lost.any():
        for k, (h, t) in enumerate(zip(heads, tails)):
            ab = t - h
            u = np.clip(((verts[lost] - h) @ ab) / max(ab @ ab, 1e-12), 0, 1)
            dist[lost, k] = np.linalg.norm(verts[lost] - (h + u[:, None] * ab), axis=1)
        print(f"skin weights: {int(lost.sum())} vertices on pieces apart from the body, weighted by straight distance")
    if allow is not None:
        dist[~allow] = np.inf
    rel = dist - dist.min(1, keepdims=True)
    sig = np.broadcast_to(np.asarray(sigma, float).reshape(-1, 1), (len(verts), 1))
    w = np.exp(-rel / sig)
    w[rel > 4 * sig] = 0
    nb = [[] for _ in verts]
    for f in faces:
        for x in range(3):
            nb[f[x]].append(f[(x + 1) % 3])
            nb[f[x]].append(f[(x + 2) % 3])
    rows = np.repeat(np.arange(len(verts)), [len(x) for x in nb])
    cols = np.concatenate([np.array(x, int) for x in nb])
    adj = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(verts),) * 2).tocsr()
    deg = np.maximum(np.asarray(adj.sum(1)).ravel(), 1)
    soft = (sig / sig.max()).ravel()[:, None] if sig.max() > 0 else 1.0   # rigid parts keep their edges
    for _ in range(smooth):
        w = w + 0.5 * soft * ((adj @ w) / deg[:, None] - w)
        if allow is not None:
            w[~allow] = 0.0
    top = np.argsort(-w, axis=1)[:, 4:]
    np.put_along_axis(w, top, 0.0, axis=1)
    w /= w.sum(1, keepdims=True)
    print(f"skin weights: {len(verts)} vertices, {len(heads)} bones, {mask.sum()} solid voxels of {cell * 100:.1f} cm")
    return w.astype(np.float32)


if __name__ == "__main__":
    d = np.load(sys.argv[1])
    w = weights(d["verts"], d["faces"], d["heads"], d["tails"], float(d["cell"]), d["sigma"],
                allow=d["allow"] if "allow" in d.files else None)
    np.savez(sys.argv[2], weights=w)
