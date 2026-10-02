"""Compact text views of a defence for an LLM player.

Budgets (see ``docs/llm.md``): the briefing is sent once and must stay under ~6000
characters; ``status`` under ~1600; a wave digest under ~1200. Coordinates are tile
``(x, y)`` with x right and y down, matching the map's rulers.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from hellward.sim.balance import BALANCE
from hellward.sim.content import CURSES, MONSTERS, SPELLS, TOWERS, felt_hit
from hellward.sim.model import SIM_DT, Monster, Tower, World

if TYPE_CHECKING:
    from hellward.server.campaign import Campaign

RULES = (
    "RULES: build on '.' tiles as `build <kind> <x> <y>`; towers shoot by distance. "
    "Waves start themselves when the break ends; `call` starts the next early for bonus gold. "
    "Curses cannot be lifted: space towers ~2 tiles apart. "
    "Smite is holy (ignores armor and tags); leaks cost lives."
)


def wave_hp(world: World, wave: int) -> float:
    """The life multiplier of a wave's monsters: its ramp times the location and hardness."""
    return world.waves[wave].hp * world.location.life * world.hardness


def monster_hp(world: World, kind: str, wave: int) -> float:
    return MONSTERS[kind].hp * wave_hp(world, wave)


def _tags(kind: str) -> str:
    m = MONSTERS[kind]
    prot = "".join(e.value[0].upper() for e in m.protected)
    vuln = "".join(e.value[0].upper() for e in m.vulnerable)
    return f"{prot or '-'}/{vuln or '-'}"


def map_ascii(world: World) -> str:
    """The map as one character per tile, with x/y rulers: E entrances, S the shrine,
    = route floor, - other hall floor, D a gate socket, . buildable, T a tower."""
    level = world.level
    routes = level.routes
    on_route: set[tuple[int, int]] = set()
    for route in routes:
        on_route |= set(route.tiles)
    entrances = {route.entrance for route in routes}
    shrine = routes[0].exit
    towers = {t.tile for t in world.towers.values()}
    tens = "    " + "".join(str(x // 10) if x % 10 == 0 else " " for x in range(level.width))
    ones = "    " + "".join(str(x % 10) for x in range(level.width))
    rows = [tens, ones]
    for y in range(level.height):
        cells = []
        for x in range(level.width):
            tile = (x, y)
            if tile in towers:
                cells.append("T")
            elif tile == shrine:
                cells.append("S")
            elif tile in entrances:
                cells.append("E")
            elif tile in level.doors:
                cells.append("D")
            elif tile in on_route:
                cells.append("=")
            elif level.walkable(x, y):
                cells.append("-")
            elif level.buildable(x, y):
                cells.append(".")
            else:
                tile_char = level.tile(x, y).value
                cells.append(tile_char if tile_char != "P" else "-")
        rows.append(f"{y:2d}  " + "".join(cells))
    return "\n".join(rows)


def briefing(world: World, *, seed: int, skills: frozenset[str]) -> str:
    """Everything that never changes, sent once: arsenal, foes, waves, map."""
    location = world.location
    lines = [f"{location.name} (act {location.act}) — seed {seed} | "
             f"gold {world.gold} lives {world.lives} mana {world.mana:.0f}/{world.mana_max:.0f}"]
    lines.append(location.blurb + " Lesson: " + location.lesson)
    lines.append(RULES)
    lines.append("TOWERS (cost | rank stats as dmg x rate / range):")
    for key in location.arsenal.towers:
        tower = TOWERS[key]
        ranks = " | ".join(
            f"r{i + 1} {world._price(lv.cost)}g {lv.damage:g}x{lv.rate:g}/{lv.range:g}"
            for i, lv in enumerate(world.tower_levels[key]))
        extra = {"amplify": "marks foes to take more", "aura": "lends nearby towers damage",
                 "hook": "drags small foes back"}.get(tower.attack, "")
        lines.append(f"  {key} ({tower.element.value} {tower.attack}): {ranks}"
                     + (f" — {extra}" if extra else ""))
    if location.arsenal.gates:
        lines.append(f"GATES: {world.door_cost}g each, {world.gate_life:.0f} life; "
                     "flyers pass over, walkers queue and batter")
    lines.append("SPELLS: " + "; ".join(_spell_line(world, key) for key in location.arsenal.spells))
    growth = (BALANCE.wave_growth - 1.0) * 100
    lines.append(f"FOES (wave-1 life x speed, armor, protected/vulnerable, leaders' curses; "
                 f"life +{growth:.0f}%/wave):")
    for key in location.monsters:
        m = MONSTERS[key]
        hp = monster_hp(world, key, 0)
        leader = ""
        if m.leader is not None:
            leader = " L:" + ",".join(CURSES[c].name for c in m.leader.curses)
        fly = " fly" if m.flying else ""
        lives = f" {m.lives}lives" if m.lives > 1 or m.boss else ""
        lines.append(f"  {key}: {hp:.0f}hp x{m.speed:g}{fly} arm{m.armor} {_tags(key)}{lives}{leader}")
    lines.append(f"WAVES ({len(world.waves)}):")
    for i, wave in enumerate(world.waves):
        groups = " ".join(f"{g.kind}x{g.count}" + (f"@{g.route}" if g.route != "main" else "")
                          for g in wave.groups)
        lines.append(f"  w{i + 1} '{location.wave_names[i]}' (x{wave.hp:.2f}, +{wave.bonus}g): {groups}")
    if skills:
        lines.append("SKILLS: " + ", ".join(sorted(skills)))
    lines.append(f"MAP ({level_size(world)}; y down; T towers as built):")
    lines.append(map_ascii(world))
    return "\n".join(lines)


def level_size(world: World) -> str:
    return f"{world.level.width}x{world.level.height}"


def _spell_line(world: World, key: str) -> str:
    spec = SPELLS[key]
    cost = world.spell_cost(key)
    power = world.power()
    if key == "smite":
        holy = felt_hit(spec.damage * power, None, MONSTERS["fallen"])
        return f"smite {cost:.0f}m: holy {holy} to one foe (recharge {spec.recharge:.0f}s)"
    if key == "hymn":
        return (f"hymn {cost:.0f}m: one tower x{spec.rate:g} rate {spec.lasting:.0f}s "
                f"(draws curses! recharge {spec.recharge:.0f}s)")
    if key == "meteor":
        damage = spec.damage * power
        return (f"meteor {cost:.0f}m: {damage:.0f} fire r{spec.radius:g} +burn, "
                f"lands {spec.delay:.1f}s late (recharge {spec.recharge:.0f}s)")
    if key == "orb":
        damage = spec.damage * power
        return (f"orb {cost:.0f}m: {damage:.0f} cold +freeze {spec.lasting:.1f}s r{spec.radius:g} "
                f"(recharge {spec.recharge:.0f}s)")
    return f"{key} {cost:.0f}m"


def purse(world: World) -> str:
    wave = f"{world.wave + 1}/{len(world.waves)}" if world.wave >= 0 else f"-/{len(world.waves)}"
    if world.break_left is not None:
        phase = f"BREAK {world.break_left:.1f}s"
    elif world.outcome is not None:
        phase = world.outcome.upper()
    else:
        phase = "FIGHTING"
    return (f"t={world.time:.1f} {phase} wave {wave} | gold {world.gold} lives {world.lives} "
            f"mana {world.mana:.0f}/{world.mana_max:.0f}")


def tower_line(tower: Tower) -> str:
    curses = ",".join(f"{c.value[:4]}:{left:.0f}s" for c, left in sorted(
        tower.curses.items(), key=lambda kv: kv[0].value)) or "-"
    hymn = f" hymn:{tower.hymn:.0f}s" if tower.hymn > 0 else ""
    return (f"#{tower.id} {tower.kind.key}{tower.level + 1} ({tower.tile[0]},{tower.tile[1]}) "
            f"r{tower.reach:.1f} {curses}{hymn}")


def towers_brief(world: World) -> str:
    """Counts by kind, plus only the towers that need attention (cursed, hymned, ranked)."""
    if not world.towers:
        return "towers: -"
    kinds: Counter = Counter(t.kind.key for t in world.towers.values())
    out = "towers (%d): %s" % (len(world.towers), " ".join(f"{k}×{n}" for k, n in sorted(kinds.items())))
    loud = [t for t in world.towers.values() if t.curses or t.hymn > 0 or t.level > 0]
    if loud:
        out += " | " + "; ".join(tower_line(t) for t in sorted(loud, key=lambda t: t.id))
    return out


def towers_full(world: World) -> str:
    if not world.towers:
        return "towers: -"
    return "towers: " + "; ".join(tower_line(t) for t in sorted(world.towers.values(), key=lambda t: t.id))


def status(world: World, *, full: bool = False) -> str:
    """The purse, towers, gates, spells, breach offer and the next wave."""
    lines = [purse(world)]
    lines.append(towers_full(world) if full else towers_brief(world))
    if world.location.arsenal.gates:
        rows = []
        for d in world.doors:
            state = "rubble" if d.rubble else ("gate" if d.built else "empty")
            hp = f" {d.hp:.0f}/{world.gate_life:.0f}" if d.built else ""
            rows.append(f"d{d.index}{hp} {state}")
        lines.append("doors: " + "; ".join(rows))
    spells = []
    for key in world.location.arsenal.spells:
        left = world.recharge.get(key, 0.0)
        spells.append(f"{key} {'READY' if left < 0.05 else f'{left:.0f}s'}")
    lines.append("spells: " + " ".join(spells))
    if world.salvage_held:
        lines.append(f"salvage: held {world.salvage_held} (`salvage` sells one for battle gold)")
    if world.breach_offered and world.breach_spec is not None:
        spec = world.breach_spec
        lines.append(f"BREACH OFFER: {spec.name} ({spec.elite_name} + pack) joins the next wave — "
                     "`breach cash|trophy|decline`")
    if world.can_call_wave:
        nxt = world.wave + 1
        groups = " ".join(f"{g.kind}x{g.count}" for g in world.waves[nxt].groups)
        lines.append(f"next: w{nxt + 1} '{world.location.wave_names[nxt]}': {groups} "
                     f"(+{world.early_call_bonus}g to `call` now)")
    if world.monsters:
        lines.append("field: " + field(world))
    return "\n".join(lines)


def threat_seconds(world: World, m: Monster) -> float:
    """Seconds before a monster reaches the shrine at its unslowed pace."""
    pace = m.kind.speed * m.speed_factor
    return world.remaining(m) / pace if pace > 0 else float("inf")


def field(world: World) -> str:
    """Every foe on the map, bucketed by route progress: entrance/mid/shrine thirds."""
    buckets: dict[str, Counter] = {"gate": Counter(), "near": Counter(), "mid": Counter(), "far": Counter()}
    hp: dict[str, float] = {"gate": 0.0, "near": 0.0, "mid": 0.0, "far": 0.0}
    leaders: list[str] = []
    for m in world.monsters:
        length = world.level.route(m.route).length
        share = m.s / length if length > 0 else 1.0
        bucket = "gate" if m.door >= 0 else ("near" if share >= 2 / 3 else ("mid" if share >= 1 / 3 else "far"))
        buckets[bucket][m.kind.key] += 1
        hp[bucket] += max(m.hp, 0.0)
        if m.kind.leader is not None:
            mark = "!"
            if m.chant_curse is not None:
                mark = f" chanting {m.chant_curse.value}"
            elif m.marking:
                mark = " marking"
            elif m.asking is not None:
                mark = " pondering"
            leaders.append(f"#{m.id} {m.kind.key} {m.hp:.0f}hp{mark}")
    parts = []
    total = sum(hp.values())
    for name in ("far", "mid", "near", "gate"):
        counts = buckets[name]
        if counts:
            kinds = " ".join(f"{k}x{n}" for k, n in sorted(counts.items()))
            parts.append(f"{name} {kinds} ({hp[name]:.0f}hp)")
    out = f"{len(world.monsters)} foes {total:.0f}hp: " + ("; ".join(parts) if parts else "-")
    if leaders:
        out += " | leaders: " + "; ".join(leaders)
    return out


def threats(world: World, *, smite_damage: float) -> str:
    """Smite targets with their ids: chanting leaders first, then foes a Smite kills near the shrine."""
    foes = sorted(world.monsters, key=lambda m: threat_seconds(world, m))
    rows = []
    seen: set[int] = set()
    for m in foes:
        if m.kind.leader is not None and (m.chant_curse is not None or m.marking):
            rows.append(f"#{m.id} {m.kind.key} {m.hp:.0f}hp CHANT — smite{' KILLS' if m.hp <= smite_damage else ''}")
            seen.add(m.id)
    for m in foes:
        if m.hp <= smite_damage and m.id not in seen:
            rows.append(f"#{m.id} {m.kind.key} {m.hp:.0f}hp, {threat_seconds(world, m):.1f}s out")
    if not rows:
        return f"no smite target worth it (smite hits for {smite_damage:.0f})"
    return f"smite hits for {smite_damage:.0f}: " + "; ".join(rows[:8])


def tower_hits(world: World, tower_key: str, rank: int, foe: str) -> int:
    """The felt hit of one rank of a tower against one foe kind (no auras)."""
    tower = TOWERS[tower_key]
    level = world.tower_levels[tower_key][rank]
    if tower.attack in ("amplify", "aura", "hook"):
        return 0
    return felt_hit(level.damage, tower.element, MONSTERS[foe])


def step_seconds(steps: int) -> float:
    return steps * SIM_DT


def campaign_text(campaign: Campaign) -> str:
    """The profile's purse and map: sigils, per-act locations with best/open/closed, materials."""
    data = campaign.campaign()
    lines = [f"profile {data['profile']} — {data['free']} free of {data['sigils']} sigils | "
             f"salvage {data['salvage']} trophies {data['trophies']} (lantern at {data['at']})"]
    for act in data["acts"]:
        rows = []
        for place in act["places"]:
            if place["best"]:
                state = str(place["best"])
            elif place["opened"]:
                state = "open"
            else:
                state = "-"
            rows.append(f"{'>' if place['next'] else ''}{place['key']}:{state}")
        lines.append(f"act {act['act']}: " + " ".join(rows))
    return "\n".join(lines)


def skills_text(campaign: Campaign, location: str | None = None) -> str:
    """The tree, one line per column: *learned, learnable[cost], the rest bare."""
    data = campaign.skills(location)
    lines = [data["heading"]]
    by_column: dict[str, list[str]] = {}
    for node in data["nodes"]:
        if node["learned"]:
            mark = f"*{node['key']}"
        elif node["learnable"]:
            mark = f"{node['key']}[{node['cost']}]"
        else:
            mark = node["key"]
        by_column.setdefault(node["column"], []).append(mark)
    names = {column["key"]: column["name"] for column in data["columns"]}
    for key, marks in by_column.items():
        lines.append(f"{names.get(key, key)}: " + " ".join(marks))
    return "\n".join(lines)


def forge_text(forge: dict) -> str:
    """The forge's purse and one line per pattern: owned/equipped, price, what its button does."""
    lines = [forge["line"]]
    for card in forge["cards"]:
        if card["owned"]:
            state = "equipped" if card["equipped"] else f"owned ({card['label']})"
        else:
            state = card["label"]
        blurb = card["blurb"]
        if len(blurb) > 90:
            blurb = blurb[:87] + "..."
        lines.append(f"{card['key']}: {card['name']} [{card['family']}] {card['price']} — {state}. {blurb}")
    return "\n".join(lines)
