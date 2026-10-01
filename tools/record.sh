#!/bin/sh
# Record the game: tools/record.sh OUT FRAMES EVERY [user args...]
#   OUT ending in .mp4: every frame at 30 fps into a video with its soundtrack (EVERY is ignored): the music
#   and every cue the game played, mixed from the game's log (tools/mixdown.py).
#   OUT a directory: every EVERY-th frame as numbered JPEGs, e.g. to make a contact sheet of a whole demo.
# Typical: tools/record.sh /tmp/demo.mp4 5400 1 demo film     (three minutes of the scripted defence, filmed)
set -e
cd "$(dirname "$0")/.."
out=$1; frames=$2; every=$3; shift 3
case "$out" in
  *.mp4) dir=$(mktemp -d /tmp/hw3d-record.XXXXXX); every=1 ;;
  *) mkdir -p "$out"; dir=$(cd "$out" && pwd) ;;
esac
tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/main.tscn \
  "record=$dir" "frames=$frames" "every=$every" timeout=7200 "$@" 2>&1 | grep -E "ERROR|SCRIPT ERROR|at: " | head -20 || true
case "$out" in
  *.mp4)
    uv run --quiet python tools/mixdown.py "$dir" "$frames" "$dir/sound.wav" >/dev/null
    ffmpeg -loglevel error -y -framerate 30 -i "$dir/%05d.jpg" -i "$dir/sound.wav" -c:v libx264 -preset slow -crf 18 \
      -pix_fmt yuv420p -c:a aac -b:a 192k -shortest "$out"
    rm -rf "$dir" ;;
esac
echo "$out"
