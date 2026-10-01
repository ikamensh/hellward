#!/bin/sh
# The monsters side by side as the battle shows them (game/scripts/lineup.gd): tools/lineup.sh OUT.png [args]
# args: kinds=fallen,shaman,.. anim=walk at=0.4 dist=48 pitch=52 yaw=0 gap=2.6 silhouette res=1920x1080
set -e
cd "$(dirname "$0")/.."
out=$(cd "$(dirname "$1")" && pwd)/$(basename "$1"); shift
res=1920x1080
for a in "$@"; do case "$a" in res=*) res=${a#res=} ;; esac; done
tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/lineup.tscn \
  "res=$res" "out=$out" timeout=120 "$@" 2>&1 | grep -E "SCRIPT ERROR|^ERROR" | head -10 || true
test -f "$out"
echo "$out"
