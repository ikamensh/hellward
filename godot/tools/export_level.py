"""Export a Hellward location (map, routes, waves) and the content the demo uses, from the 2D game's rules.

    HELLWARD_INTERPRETED=1 uv run --project ../hellward python tools/export_level.py tristram

Writes game/data/<location>.json. The 3D demo reads the same battlefield as the 2D game; its own
light simulation (game/scripts/world.gd) plays it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from hellward.sim.campaign import LOCATIONS
from hellward.sim.content import MONSTERS, TOWERS

OUT = Path(__file__).resolve().parent.parent / "game" / "data"
DEMO_MONSTERS = ("fallen", "zombie", "shaman", "skeleton")
DEMO_TOWERS = ("arrow", "pyre", "frost", "storm")


def export(key: str) -> dict:
    location = LOCATIONS[key]
    level = location.level
    return {
        "key": location.key,
        "name": location.name,
        "blurb": location.blurb,
        "width": level.width,
        "height": level.height,
        "grid": ["".join(level.tile(x, y).value for x in range(level.width)) for y in range(level.height)],
        "routes": [{"key": r.key, "points": [list(p) for p in r.waypoints]} for r in level.routes],
        "start_gold": location.start_gold,
        "waves": [{"name": name, "clear_bonus": wave.bonus, "life": wave.hp,
                   "groups": [{"kind": g.kind, "count": g.count, "interval": g.interval, "start": g.start}
                              for g in wave.groups]}
                  for name, wave in zip(location.wave_names, location.waves)],
        "monsters": {k: {"name": m.name, "hp": m.hp, "speed": m.speed, "bounty": m.bounty, "lives": m.lives,
                         "size": m.size, "resist": {e.value: v for e, v in m.resist.items()}}
                     for k, m in MONSTERS.items() if k in DEMO_MONSTERS},
        "towers": {k: {"name": t.name, "element": t.element.value, "attack": t.attack, "blurb": t.blurb,
                       "bolt_speed": t.bolt_speed,
                       "levels": [{"cost": lv.cost, "damage": lv.damage, "rate": lv.rate, "range": lv.range,
                                   "chill": lv.chill, "chill_time": lv.chill_time, "chains": lv.chains}
                                  for lv in t.levels]}
                   for k, t in TOWERS.items() if k in DEMO_TOWERS},
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for key in sys.argv[1:] or ["tristram"]:
        path = OUT / f"{key}.json"
        path.write_text(json.dumps(export(key), indent=1))
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
