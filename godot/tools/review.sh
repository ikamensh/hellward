#!/bin/sh
# One sheet reviewing a monster: tools/review.sh MODEL OUT.png [yaw=200] [pitch=15] [views=6] [anims="idle walk attack die"]
# Each row is one animation sampled `views` times across its length, from the front three-quarters, under game
# light (game/scripts/preview.gd). MODEL is a name in game/assets/models or a path to a .glb.
set -e
cd "$(dirname "$0")/.."
model=$1; out=$2; shift 2
case "$model" in *.glb) ;; *) model="game/assets/models/$model.glb" ;; esac
model=$(cd "$(dirname "$model")" && pwd)/$(basename "$model")
yaw=200; pitch=15; views=6; anims="idle walk attack die cast"
for a in "$@"; do case "$a" in yaw=*) yaw=${a#yaw=} ;; pitch=*) pitch=${a#pitch=} ;; views=*) views=${a#views=} ;;
  anims=*) anims=${a#anims=} ;; esac; done
tmp=$(mktemp -d /tmp/hw3d-review.XXXXXX)
rows=""
for anim in $anims; do
  mkdir -p "$tmp/$anim"
  log=$(tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/preview.tscn \
    res=640x640 "model=$model" "out=$tmp/$anim" anim=$anim views=$views yaw=$yaw pitch=$pitch 2>&1)
  if ls "$tmp/$anim"/f*.png >/dev/null 2>&1; then rows="$rows $anim"; fi
  echo "$log" | grep -E "SCRIPT ERROR|^ERROR" | head -3 || true
done
uv run --quiet python - "$tmp" "$out" $rows <<'EOF'
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
tmp, out, rows = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
frames = [[Image.open(p) for p in sorted((tmp / r).glob("f*.png"))] for r in rows]
w, h = frames[0][0].size
cols = max(len(f) for f in frames)
sheet = Image.new("RGB", (w * cols, h * len(rows)))
font = ImageFont.load_default(size=28)
for y, (name, fs) in enumerate(zip(rows, frames)):
    for x, im in enumerate(fs):
        sheet.paste(im, (x * w, y * h))
    ImageDraw.Draw(sheet).text((10, y * h + 8), name, fill=(255, 255, 0), font=font)
sheet.save(out)
EOF
rm -rf "$tmp"
echo "$out"
