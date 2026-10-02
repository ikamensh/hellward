# Image-to-3D on a GPU box (TRELLIS.2)

`trellis_gen.py` turns concept paintings (`art/concept/*.png`) into textured sculpts. It runs on a rented GPU:
a Scaleway `L40S-1-48G` in `fr-par-2` (about €1.4 an hour; stop it when idle, delete it when done). Credentials
and which API key may create volumes: the Secrets index in `~/.config/agents/registry.md` (the `saga2d-deploy`
key; the personal admin key never goes onto a VM).

## Once per VM

Ubuntu with the NVIDIA driver and Docker (Scaleway's GPU image has both; `sudo usermod -aG docker ubuntu`).
Keep the work and the weights on the root disk: the scratch disk is wiped when the VM stops.

```bash
# the image: TRELLIS.2 built inside PyTorch 2.6 / CUDA 12.4, kept as "trellis2"
git clone -b main https://github.com/microsoft/TRELLIS.2.git --recursive ~/work/TRELLIS.2
docker run --name t2build --gpus all --shm-size=16g -v ~/work:/work -e TORCH_CUDA_ARCH_LIST=8.9 -e MAX_JOBS=8 \
  pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel bash -lc '
    apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y sudo git libgl1 libglib2.0-0 libjpeg-dev \
      ninja-build build-essential wget libeigen3-dev
    cd /work/TRELLIS.2 && . ./setup.sh --basic --flash-attn --nvdiffrast --nvdiffrec --cumesh --o-voxel --flexgemm
    pip install transformers==4.57.1'
docker commit t2build trellis2
# BiRefNet loads in half precision and fails: make it float
sed -i "s/        self.model.eval()/        self.model.float().eval()/" ~/work/TRELLIS.2/trellis2/pipelines/rembg/BiRefNet.py
# the weights (the published config names gated repos; trellis_gen.py swaps in these ungated copies)
python3 -m venv ~/hfenv && ~/hfenv/bin/pip install -q huggingface_hub
~/hfenv/bin/hf download microsoft/TRELLIS.2-4B --local-dir ~/hf/trellis2-4b
~/hfenv/bin/hf download microsoft/TRELLIS-image-large --include "ckpts/ss_dec_conv3d_16l8_fp16*" "pipeline.json"
~/hfenv/bin/hf download camenduru/dinov3-vitl16-pretrain-lvd1689m
~/hfenv/bin/hf download ZhengPeng7/BiRefNet
```

## A run

```bash
scp art/concept/skull.png ubuntu@VM:~/work/in/ && scp tools/gen3d/trellis_gen.py ubuntu@VM:~/work/
ssh ubuntu@VM 'cd ~/work && docker run --rm --gpus all --shm-size=16g -v ~/work:/work -v ~/hf:/hf \
  -v ~/hf:/root/.cache/huggingface -w /work trellis2 python /work/trellis_gen.py /work/in /work/out \
  --seeds 1 2 3 --only skull --game 6000'
scp -r 'ubuntu@VM:~/work/out/skull/s1' art/gen/skull/       # look at views.png per seed first
blender -b --factory-startup -P tools/blender/intake.py -- skull 1 --faces 200000
```

The first seed takes a few minutes (loading the models); each further seed about two. `views.png` shows each
seed's shading, base colour and normals: pick by those, then take the seed in with `intake.py` (the seed folders
are git-ignored; `art/gen/<kind>/game.glb` and the decimated `sculpt.glb` are committed).
