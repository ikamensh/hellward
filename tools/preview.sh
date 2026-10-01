#!/bin/sh
# Review a model under game lighting: tools/preview.sh MODEL OUT.png [anim=walk] [views=8] [yaw=35] [pitch=25] [dist=N]
# MODEL is a name in game/assets/models or a path to a .glb. Writes a contact sheet of the frames to OUT.png.
set -e
cd "$(dirname "$0")/.."
model=$1; out=$2; shift 2
case "$model" in *.glb) ;; *) model="game/assets/models/$model.glb" ;; esac
model=$(cd "$(dirname "$model")" && pwd)/$(basename "$model")
views=8
for a in "$@"; do case "$a" in views=*) views=${a#views=} ;; esac; done
tmp=$(mktemp -d /tmp/hw3d-preview.XXXXXX)
caffeinate -u -t 2 true
/Applications/Godot.app/Contents/MacOS/Godot --path game --resolution 960x720 --fixed-fps 30 \
  --write-movie "$tmp/f.png" --quit-after $((views + 3)) res://scenes/preview.tscn -- "model=$model" "$@" \
  2>&1 | grep -E "^(animations|bounds|ERROR|SCRIPT ERROR)|error" | head -20 || true
frames=$(ls "$tmp"/f*.png | tail -n "$views")
uv run --quiet python tools/sheet.py "$out" $frames --cols 4 >/dev/null
rm -rf "$tmp"
echo "$out"
