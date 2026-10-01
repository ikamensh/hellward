#!/bin/sh
# Build one model: tools/model.sh barrel  ->  runs tools/blender/barrel.py in Blender, writes game/assets/models/barrel.glb
set -e
cd "$(dirname "$0")/.."
for name in "$@"; do
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python-exit-code 1 -P "tools/blender/$name.py" 2>&1 \
    | grep -v -E "^(Blender quit|Read prefs|Warning: Unable to)" | tail -20
done
