# Stage 1 — Armor and the pirate arsenal

The first readiness stage ([design-choices.md](../design-choices.md) section 20): the damage model with armor, three
physical towers (Ballista, Hook Tower, Knife Post), the shrine strike and the boss's return, no Cleanse and no
interrupts, and Battle Hymn. Today's number scale, maps and campaign stay. It ships as a release Ilya plays.

This spec is the contract the parallel builders share: the rules (simulation), the wire (server protocol) and the
client build against the same names.

## Rules

### Damage

Every **hit** (a tower's attack, a bolt's impact, a chain's leap, a splash's lesser blow, Meteor, Frozen Orb) resolves:

1. **Factors** multiply:
   - the element: ×0.75 if the monster is *protected* against it, ×1.25 if *vulnerable*;
   - the Bone Altar's amplification (×(1 + amplify));
   - the Druid Grove's aura (×(1 + bonus));
   - the Knife Post's ×2 on a standing small monster;
   - a chain's leap decay (×keeps^i);
   - a splash's lesser blow (×0.6).

   The product is capped at ×2.
2. **Round** to a whole number: up when the capped product is above 1, down when below, half up when it is 1.
3. Subtract the monster's **armor**.
4. The hit does **at least 1**.

The other damage sources:
- **Damage over time** (poison, the burning floor) takes the element and amplification factors, with no armor and
  no rounding.
- **Holy damage** (Smite), Thorns and the death bursts (Shatter, Corpse Explosion) take no factor and no armor.

One function in the simulation computes a hit's felt damage. The planner's estimate uses the same function, and the
server uses it for the hover table.

Monsters:
- `resist` becomes two lists, `protected` and `vulnerable`, with at most two tags between them. Bosses may have more.
  Every immunity becomes *protected*.
- `armor` is a whole number:
  - Overlord 2, Zealot 2, Hulk 3;
  - Azazel 2, the Bone Priest 3;
  - everyone else 0.
- An armored kind keeps one vulnerability, so an elemental tower has a way in:
  - Overlord: vulnerable to lightning;
  - Zealot: vulnerable to fire;
  - Hulk: vulnerable to fire.
- The Plague Totem's venom seeks the strongest monster in reach. Nothing is immune any longer.

### Towers

| Key | Name | Element | Attack | Hit by rank | Rate by rank | Reach by rank | Price | First offered |
|---|---|---|---|---|---|---|---|---|
| `ballista` | Ballista | physical | bolt | 7 / 10 / 14 | 0.4 / 0.42 / 0.45 | 3.2 / 3.4 / 3.6 | 1.5 | the Catacombs |
| `hook` | Hook Tower | physical | hook | 3 / 4 / 5 | 1/6, 1/5, 1/4 | 2.8 / 3.0 / 3.2 | 1.5 | Kurast Docks |
| `knife` | Knife Post | physical | bolt (standing first) | 2 / 3 / 4 | 0.8 / 0.85 / 0.9 | 2.6 / 2.8 / 3.0 | 1.0 | Kurast Docks |

**Ballista:**
- a plain bolt at 14 tiles a second, aimed at the monster nearest the shrine;
- its blurb names armor.

**Hook Tower:**
- **Its spot:** on each route, the point nearest the tower.
- **Its target:** at each attack, the foremost **small monster** in reach that is at least 1 tile past its route's spot.
  - A small monster is one whose kind costs 1 life, is not a boss and is not a leader.
  - The target must not be at a gate (`door < 0`) and must not have been hooked before.
- **The pull:**
  - 2 tiles toward the spot, never past it;
  - under Weaken, the pull is multiplied by Weaken's damage share;
  - a pull that would end between a built gate's queue stop and its crossing ends at the stop.
- **Its hit** goes through the damage pipeline.
- **No target:** it does not attack, and its timer waits.
- **Flyers** can be hooked.
- **Record:** each mover kind sets its own bit in `Monster.moved` (an int bitmask). The Hook is bit 1; later movers
  take further bits. A monster is never moved back twice by the same kind.
- **After a pull,** the monster list is re-sorted, nearest the shrine first.

**Knife Post:**
- **Target:** it throws at a *standing* small monster in reach if there is one (at a gate, `door >= 0`, or held,
  `frozen > 0`), and otherwise at the foremost.
- **At impact,** a knife on a standing small monster carries the ×2 factor.

**Skill tree:**
- Physical towers share the Arrow column's rank skills, renamed **Adept of Steel** and **Master of Steel**: rank II
  and rank III of every physical tower.
- The column is named **Steel**.

### The shrine

- **An ordinary monster** reaching the end of its route costs its lives and is removed. The `leak` event stays as it
  is, and the client draws the strike and the obliteration.
- **A boss** (`boss = true` in monsters.toml: Azazel, the Bone Priest) costs `battle.boss_strike_lives` (5) instead.
  - It is sent back to `s = 0` on its route. It keeps its life and its afflictions, stops battering any gate, and its
    strike count rises by 1.
  - It walks again.
  - Event: `returned`.

### Spells

- **Removed:**
  - Cleanse (the spell, `World.cleanse`, wards, the Salvation skill);
  - spells breaking a chant: Smite and Frozen Orb no longer break anything;
  - the resolute leader;
  - `chants_broken`.
- **Removed events:** `cleansed`, `ward_holds`, `broken`.
- **The Inquisitor's mark** stays: a longer, different telegraph.
- **Battle Hymn** (`hymn`):
  - aimed at a tower;
  - 40 mana, 15 s recharge;
  - the tower attacks twice as fast for 6 s (`Tower.hymn`, seconds left, part of `rate_mult`);
  - event `hymn`.
- **Arsenal:**
  - Tristram: Smite;
  - from the Graveyard: Smite and Hymn;
  - Frozen Orb and Meteor where they open today.

### The planner

- Its estimate uses the felt-damage function (armor and factors).
- It sees Hymn through `rate_mult`.
- It has a term for the Hook (the extra time its pulls keep monsters under the towers covering that stretch) and for
  the Knife Post's ×2 at a gate.
- Every ward and resolute branch is gone.
- `tools/curse_quality.py` confirms the estimate still shortlists well (share of best ≥ 0.85).

## Names both sides build against

| Thing | Name |
|---|---|
| a hit's felt damage | `hellward.sim.content.felt_hit(hit: float, element: Element \| None, kind: MonsterKind, factor: float = 1.0) -> int` (element None: physical-free holy, no factor, no armor) |
| monster kind fields | `MonsterKind.armor: int`, `.protected: tuple[Element, ...]`, `.vulnerable: tuple[Element, ...]`, `.boss: bool` |
| monster fields | `Monster.moved: int` (bitmask, Hook = 1), `Monster.strikes: int` |
| tower field | `Tower.hymn: float` (seconds left) |
| the spell | `World.hymn(tower_id: int) -> None`, spell key `"hymn"` |
| tower kinds | `"ballista"`, `"hook"` (attack `"hook"`), `"knife"` |
| events | `("hook", tower_id, monster_id, from_s, to_s)`, `("returned", monster_id, kind_key, lives, strikes)`, `("hymn", tower_id)` |
| tuning | `battle.boss_strike_lives`, `battle.factor_cap`, `battle.hook_pull`, `battle.knife_standing`, `battle.splash_share` |

## The wire (server protocol; `PROTOCOL` +1, with `Net.PROTOCOL`)

**Events** (plain lists):

| Event | Fields |
|---|---|
| `hook` | tower id, monster id, from s, to s |
| `returned` | monster id, kind, lives lost, strikes so far |
| `hymn` | tower id |
| `leak` | unchanged |

**State changes:**
- **Monster snapshot:** the RESOLUTE flag bit goes; the `moved` bitmask is appended as a last element.
- **Tower snapshot:** the `ward` slot carries `hymn` seconds left.

**The battle's start:**
- the monster table gains `armor`, `protected`, `vulnerable` and `boss`, and loses `resist`;
- it also gains `hits`: for each tower kind in the arsenal, its felt hit per rank on this kind (factor 1), from the
  simulation's function;
- the spells table gains `hymn`.

**Orders:**
- `cleanse` goes;
- `hymn` comes, taking a `tower`.

## The client (Godot)

- **Removed:** Cleanse's button, key, pillar, cue and every `cleansed`, `broken` and `ward_holds` branch.
- **Hymn:**
  - a spell on the bar (key R), aimed at a tower like Cleanse was;
  - a golden aura on the tower while it lasts.
- **Models,** one Blender script per kind that builds all three ranks, as `godot/tools/blender/tower_plague.py` does:
  `tower_ballista_1..3`, `tower_hook_1..3`, `tower_knife_1..3`. Each rank carries `fx_muzzle` where its shots leave,
  and a `turret` node if it aims. There are no stand-ins: the client tests check every kind's body and ranks.
- **Ballista:** a heavy bolt projectile.
- **Hook Tower:** on `hook`, a chain flies to the monster and drags it from the old place to the new over about 0.3 s;
  then the monster walks on.
- **Knife Post:** a spinning knife projectile.
- **The shrine:**
  - on `leak`, the monster strikes the shrine gate, a holy flash, then it is gone;
  - on `returned`, the boss is struck back in a flash and reappears at its portal;
  - a strike counter on the boss.
- **Hover on a monster:** its armor, its protected and vulnerable tags, and the hit each of the player's tower kinds
  deals it (the `hits` table).

## Exit criteria

**Tests:**
- the damage pipeline's properties: whole numbers, at least 1, the factor cap, the rounding direction, DoT and holy
  exceptions;
- the Hook's rules: small only, once per kind, the gate clamp, flyers, Weaken;
- the Knife Post's ×2 at a gate;
- the shrine's obliterate and the boss's return;
- Hymn doubling the rate;
- no Cleanse and no interrupt (S1);
- a leader choosing a hymned tower over the same tower unhymned (S3);
- clone fidelity for the new fields (`moved`, `hymn`, strikes);
- the compiled simulation equals the source;
- the server equals `hands.defend`;
- the campaign through the server;
- client assets, and `godot/tools/test.sh`.

**Scorecard:**
- **S1, M10** met.
- **R3** for every attacking kind at the location's armor mix.
- **M9:** at the Catacombs and at one Act II location, an Arrow-only build of a given gold loses where a build with a
  Ballista of the same gold wins.

**Tuning:**
- Each location's life factor is re-tuned with `tools/margin.py`, so the strongest bot still wins every location and
  the veteran wins Act I.
- `tools/balance.py` and `tools/curse_quality.py`, before and after, are quoted in the commit.

**Ilya sees:** rendered frames of the Ballista, the Hook dragging a Flayer, the Knife Post at a gate, Hymn's aura, the
shrine strike and the boss's return. Then the release.
