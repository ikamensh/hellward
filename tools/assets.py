"""What the Godot client can show of the rules' content: a model per monster and tower kind, the clips and effect
anchors each model needs, its maps; the rest are stand-ins (docs/godot-client.md, step 4).

    uv run python tools/assets.py          # a table: every kind, its model or stand-in, triangles, clips, problems

The GLB files are read directly (their JSON chunk): no Godot, no Blender. tests/test_client_assets.py holds every
model to `problems` being empty, so a model that loses a clip or an anchor fails the suite.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hellward.sim.content import MONSTERS, TOWERS  # noqa: E402

GAME = ROOT / "godot" / "game"
MODELS = GAME / "assets" / "models"
TEXTURES = GAME / "assets" / "textures"

CLIPS = ("idle", "walk", "attack", "die", "die2")   # what monster.gd plays
LEADER_CLIPS = ("cast",)
ANCHORS = ("fx_head",)
LEADER_ANCHORS = ("fx_cast",)
MAPS = ("albedo.webp", "normal.webp", "orm.webp")


def glb(path: Path) -> dict:
    """The JSON chunk of a binary glTF."""
    data = path.read_bytes()
    magic, _version, _length = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF", f"{path} is not a binary glTF"
    size, kind = struct.unpack_from("<I4s", data, 12)
    assert kind == b"JSON"
    return json.loads(data[20:20 + size])


def summary(path: Path) -> dict:
    """Clip names, node names, material names and triangle count of a model."""
    j = glb(path)
    tris = 0
    for mesh in j.get("meshes", []):
        for prim in mesh["primitives"]:
            if "indices" in prim:
                tris += j["accessors"][prim["indices"]]["count"] // 3
    return {"clips": {a.get("name", "") for a in j.get("animations", [])},
            "nodes": {n.get("name", "") for n in j.get("nodes", [])},
            "materials": {m.get("name", "") for m in j.get("materials", [])}, "tris": tris}


def stand_ins(script: str) -> dict[str, str]:
    """A client script's STAND_INS: kind -> the model it borrows."""
    block = re.search(r"const STAND_INS := \{(.*?)\}\s*\n", script, re.S)
    return dict(re.findall(r'"([a-z_]+)": \["([a-z_]+)"', block.group(1))) if block else {}


def keys(script: str, name: str) -> set[str]:
    """The kinds a client script's `const NAME := {...}` table lists."""
    block = re.search(rf"const {name} := \{{(.*?)\}}\s*\n", script, re.S)
    return set(re.findall(r'"([a-z_]+)":', block.group(1))) if block else set()


def monster(kind: str) -> dict:
    """One monster kind's state in the client: its model (or the one it borrows) and what is wrong with it."""
    path = MODELS / f"mon_{kind}.glb"
    script = (GAME / "scripts" / "monster.gd").read_text()
    borrowed = stand_ins(script).get(kind)
    if not path.is_file():
        problems = [] if borrowed else ["no model and no stand-in"]
        if borrowed and MONSTERS[kind].leader is not None and "cast" not in summary(MODELS / f"mon_{borrowed}.glb")["clips"]:
            problems.append(f"a leader standing in as {borrowed}, which has no cast clip")
        return {"kind": kind, "model": None, "stand_in": borrowed, "problems": problems}
    info = summary(path)
    leader = MONSTERS[kind].leader is not None
    problems = [f"no {c} clip" for c in CLIPS + (LEADER_CLIPS if leader else ()) if c not in info["clips"]]
    problems += [f"no {a} node" for a in ANCHORS + (LEADER_ANCHORS if leader else ()) if a not in info["nodes"]]
    for mat in sorted(m.split(".")[0] for m in info["materials"] if m.startswith("mon_")):
        problems += [f"{mat} has no {f}" for f in MAPS if not (TEXTURES / mat / f).is_file()]
    if borrowed:
        problems.append(f"has a model but still wears {borrowed} as a stand-in")
    # monster.gd shows a kind's own model only once it knows its height; its rim and (a walker's) pace go with it
    tables = ("HEIGHTS", "RIM") + (() if MONSTERS[kind].flying else ("WALK",))
    problems += [f"monster.gd {t} has no entry" for t in tables if kind not in keys(script, t)]
    return {"kind": kind, "model": path.name, "stand_in": None, "tris": info["tris"],
            "clips": sorted(info["clips"]), "problems": problems}


def tower(kind: str) -> dict:
    """One tower kind: its models (one per rank, or one for all) or its stand-in."""
    ranked = [MODELS / f"tower_{kind}_{r}.glb" for r in (1, 2, 3)]
    single = MODELS / f"tower_{kind}.glb"
    borrowed = stand_ins((GAME / "scripts" / "tower.gd").read_text()).get(kind)
    have = [p.name for p in ranked if p.is_file()] or ([single.name] if single.is_file() else [])
    problems = [] if have or borrowed else ["no model and no stand-in"]
    if have and borrowed:
        problems.append(f"has a model but still wears {borrowed} as a stand-in")
    return {"kind": kind, "models": have, "ranks": len([p for p in ranked if p.is_file()]), "stand_in": borrowed,
            "problems": problems}


def main() -> int:
    print(f"{'monster':12s} {'model':22s} {'tris':>6s}  clips / problems")
    bad = 0
    for kind in MONSTERS:
        m = monster(kind)
        what = m["model"] or f"stand-in: {m['stand_in']}"
        detail = "; ".join(m["problems"]) or " ".join(m.get("clips", []))
        print(f"{kind:12s} {what:22s} {m.get('tris', 0):6d}  {detail}")
        bad += bool(m["problems"])
    print(f"\n{'tower':12s} {'models':40s} problems")
    for kind in TOWERS:
        t = tower(kind)
        what = ", ".join(t["models"]) or f"stand-in: {t['stand_in']}"
        print(f"{kind:12s} {what:40s} {'; '.join(t['problems'])}")
        bad += bool(t["problems"])
    own = sum(1 for k in MONSTERS if (MODELS / f"mon_{k}.glb").is_file())
    ranked = sum(1 for k in TOWERS if tower(k)["ranks"] == 3)
    print(f"\n{own} of {len(MONSTERS)} monster kinds have their own model; {ranked} of {len(TOWERS)} tower kinds "
          f"one per rank")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
