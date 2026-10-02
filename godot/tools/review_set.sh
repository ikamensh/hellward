#!/bin/sh
# The monster review set (docs/monsters.md, L3 blind review): tools/review_set.sh OUT_DIR
# Turntables, clip sheets, close portraits, lineups at 12 m and 48 m with silhouettes, two battles in play, and the
# design references, all as PNGs in OUT_DIR for critics who only look at pictures.
set -e
cd "$(dirname "$0")/.."
out=$(mkdir -p "$1" && cd "$1" && pwd)
tmp=$(mktemp -d /tmp/hw-review.XXXXXX)
for k in fallen shaman zombie skeleton; do
  tools/preview.sh "mon_$k" "$out/turntable_$k.png" views=8 pitch=12 >/dev/null
done
# clips from three-quarters side, as the battle camera sees monsters cross the road (from the front a stride
# foreshortens away and a walk reads as standing still)
tools/review.sh mon_fallen "$out/clips_fallen.png" "anims=walk attack die die2" yaw=240 >/dev/null
tools/review.sh mon_shaman "$out/clips_shaman.png" "anims=walk attack cast die die2" yaw=240 >/dev/null
tools/review.sh mon_zombie "$out/clips_zombie.png" "anims=walk attack die die2" yaw=240 >/dev/null
tools/review.sh mon_skeleton "$out/clips_skeleton.png" "anims=walk attack die die2" yaw=240 >/dev/null
for v in fallen:0.7:1.9 shaman:1.05:3.0 zombie:1.25:3.0 skeleton:1.2:3.0; do
  k=${v%%:*}; rest=${v#*:}; f=${rest%%:*}; d=${rest#*:}
  mkdir -p "$tmp/$k"
  tools/godot-capture.sh --path game --fixed-fps 30 res://scenes/capture.tscn -- scene=res://scenes/preview.tscn \
    res=700x900 "model=$PWD/game/assets/models/mon_$k.glb" "out=$tmp/$k" anim=idle views=1 yaw=205 pitch=8 \
    "focus=$f" "dist=$d" >/dev/null 2>&1
done
tools/lineup.sh "$tmp/l12.png" dist=12 >/dev/null
tools/lineup.sh "$tmp/l48.png" >/dev/null
tools/lineup.sh "$tmp/sil.png" silhouette >/dev/null
tools/lineup.sh "$tmp/sil_side.png" silhouette turn=90 >/dev/null
tools/gallery.sh "$out/battle_graveyard.png" overview,lane,close,entry 1300 demo location=graveyard >/dev/null
for f in 5280 6240 7800 8010; do
  tools/shot.sh close "$tmp/b$f.png" $f demo >/dev/null
done
uv run --quiet python - "$tmp" "$out" <<'EOF'
import sys
from pathlib import Path
from PIL import Image
tmp, out = Path(sys.argv[1]), Path(sys.argv[2])
s = Image.new("RGB", (2800, 900))
for i, k in enumerate(["fallen", "shaman", "zombie", "skeleton"]):
    s.paste(Image.open(tmp / k / "f00.png"), (i * 700, 0))
s.save(out / "portraits_closeup.png")
Image.open(tmp / "l12.png").crop((300, 250, 1620, 780)).save(out / "lineup_12m.png")
s = Image.new("RGB", (1040, 1440))
for i, n in enumerate(["l48", "sil", "sil_side"]):
    s.paste(Image.open(tmp / f"{n}.png").crop((700, 420, 1220, 660)).resize((1040, 480)), (0, i * 480))
s.save(out / "lineup_48m_and_silhouettes.png")
s = Image.new("RGB", (2400, 1350))
for i, f in enumerate([5280, 6240, 7800, 8010]):
    s.paste(Image.open(tmp / f"b{f}.png").resize((1200, 675)), ((i % 2) * 1200, (i // 2) * 675))
s.save(out / "battle_tristram.png")
EOF
cp art/concept/fallen.png "$out/concept_fallen.png"; cp art/concept/shaman.png "$out/concept_shaman.png"
cp art/concept/zombie.png "$out/concept_zombie.png"; cp art/concept/skeleton.png "$out/concept_skeleton.png"
cp art/concept/ref/fallen_ref.png "$out/2d_fallen_reference.png"; cp art/concept/ref/shaman_ref.png "$out/2d_shaman_reference.png"
rm -rf "$tmp"
echo "$out"
