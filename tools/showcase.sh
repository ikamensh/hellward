#!/bin/sh
# The demo's showcase: beauty stills and the filmed defence with its soundtrack, into OUT (default the stack's
# evidence folder). Everything renders invisibly (tools/godot-capture.sh); the film takes ~1x real time.
#   tools/showcase.sh [OUT]
set -e
cd "$(dirname "$0")/.."
out=${1:-$HOME/saga/evidence/hellward3d/showcase}
mkdir -p "$out"
commit=$(git rev-parse --short HEAD)
tools/test.sh
# stills: the opening's wide view, the gate, a lane fight, the cathedral, the battle camera
tools/gallery.sh "$out/stills-wave1.png" opening,portal,lane,overview 1500 demo
tools/gallery.sh "$out/stills-wave3.png" close,entry,cathedral,overview 5200 demo
# the film: the opening flight, the whole defence directed by events, the pull-back
tools/record.sh "$out/hellward3d-demo.mp4" "${FRAMES:-9000}" 1 demo film
cat > "$out/README.md" <<EOF
# Hellward 3D showcase

Source: ~/saga/hellward3d at $commit. Reproduce: \`tools/showcase.sh\` (FRAMES=$((${FRAMES:-9000})) for the film).

- hellward3d-demo.mp4: the scripted defence of Tristram filmed by the event director (opening flight, cuts to
  the Shaman's chants, tower close-ups, the ending), 1080p30 with the game's music and cues mixed in.
- stills-wave1.png / stills-wave3.png: named views (game/scripts/shots.gd) 50 s and 173 s into the defence.
EOF
echo "$out"
