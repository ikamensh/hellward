"""Image-to-3D on the GPU box: each concept in IN becomes textured sculpts in OUT/<name>/s<seed>/.

Runs inside the `trellis2` container (tools/gen3d/README.md): python trellis_gen.py IN OUT [--seeds 1 2 3]
[--type 1536_cascade] [--only NAME ...]. Per seed it writes sculpt.glb (up to a million triangles, 4096² PBR
textures: the source the Blender step bakes normals and occlusion from), game.glb (decimated to --game vertices,
2048² textures baked from the same attribute volume) and views.png (eight turntable views: shaded, base colour,
normal) to judge it by.

The export simplifies the generated surface as it is (remesh=False): TRELLIS's remeshing contours a narrow band
of the surface's unsigned distance and so wraps every part in two layers a voxel apart, which wastes half the
triangles and folds the layers together when decimated.
"""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
sys.path.insert(0, "/work/TRELLIS.2")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

import o_voxel  # noqa: E402
from trellis2.pipelines import Trellis2ImageTo3DPipeline  # noqa: E402
from trellis2.renderers import EnvMap  # noqa: E402
from trellis2.utils import render_utils  # noqa: E402

WEIGHTS = Path("/hf/trellis2-4b")
# the published config names gated repos; these hold the same weights without the gate
SWAP = {"facebook/dinov3-vitl16-pretrain-lvd1689m": "camenduru/dinov3-vitl16-pretrain-lvd1689m",
        "briaai/RMBG-2.0": "ZhengPeng7/BiRefNet"}


def load() -> Trellis2ImageTo3DPipeline:
    cfg_path = WEIGHTS / "pipeline.json"
    cfg = json.loads(cfg_path.read_text())
    for key in ("image_cond_model", "rembg_model"):
        name = cfg["args"][key]["args"]["model_name"]
        cfg["args"][key]["args"]["model_name"] = SWAP.get(name, name)
    cfg_path.write_text(json.dumps(cfg, indent=1))
    pipe = Trellis2ImageTo3DPipeline.from_pretrained(str(WEIGHTS))
    pipe.cuda()
    return pipe


def views(mesh, envmap, out: Path) -> None:
    yaws = [np.pi / 2 + i * np.pi / 4 for i in range(8)]
    extr, intr = render_utils.yaw_pitch_r_fov_to_extrinsics_intrinsics(yaws, [0.15] * 8, 2, 40)
    res = render_utils.render_frames(mesh, extr, intr, {"resolution": 512, "bg_color": (0.5, 0.5, 0.5)},
                                     envmap=envmap, verbose=False)
    rows = []
    for key in ("shaded", "base_color", "normal"):
        if key in res:
            rows.append(np.concatenate([np.asarray(f) for f in res[key]], axis=1))
    Image.fromarray(np.concatenate(rows, axis=0)).save(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inp", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--type", default="1536_cascade")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--faces", type=int, default=1000000)
    ap.add_argument("--game", type=int, default=16000, help="vertices of the game mesh")
    args = ap.parse_args()
    pipe = load()
    # an even grey sky: the views judge shape and colour, not lighting (this OpenCV reads no EXR)
    envmap = EnvMap(torch.full((256, 512, 3), 0.9, dtype=torch.float32, device="cuda"))
    for png in sorted(args.inp.glob("*.png")):
        if args.only and png.stem not in args.only:
            continue
        image = Image.open(png)
        for seed in args.seeds:
            dest = args.out / png.stem / f"s{seed}"
            if (dest / "sculpt.glb").exists():
                continue
            dest.mkdir(parents=True, exist_ok=True)
            mesh = pipe.run(image, seed=seed, pipeline_type=args.type)[0]
            mesh.simplify(16777216)
            views(mesh, envmap, dest / "views.png")
            for name, target, size in (("sculpt", args.faces, 4096), ("game", args.game, 2048)):
                glb = o_voxel.postprocess.to_glb(
                    vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs, coords=mesh.coords,
                    attr_layout=mesh.layout, voxel_size=mesh.voxel_size, aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
                    decimation_target=target, texture_size=size, remesh=False)
                glb.export(str(dest / f"{name}.glb"))
            print(f"done {png.stem} seed {seed}", flush=True)
            del mesh
            torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
