# Hellward: open-ground progression redesign

Status: implementation plan. The running game still follows [design.md](design.md) and
[campaign.md](campaign.md) until each stage below lands. The opening baseline was measured on
2026-09-28 from `3d2911c` with the compiled simulation.

## The intended loop

1. Before a defence, choose learned skills and equip at most one forged pattern for each tower
   family. A pattern changes every tower of that family built in this defence. Rank unlocks remain
   skills; towers and their upgrades still cost battle gold.
2. Build a few cheap, single-target towers around an open field. Ordinary enemies may take one of
   several visibly different trails from multiple entrances; a runner heads directly for the
   sanctuary. Position, range and approach direction matter more than a folded corridor's triple
   coverage.
3. Kills immediately pay gold and sometimes drop salvage. During a break, sell held salvage for
   gold now or carry it toward a future pattern. The sale cannot be undone within that defence.
4. On specified breaks, a sealed side entrance offers a **breach**: decline, take a gold cache, or
   seek a trophy. Opening it adds an announced, harder pack and a named elite to the next wave.
   The chosen reward is earned only if every side enemy dies. A leaked side enemy voids it.
5. A victory banks unsold salvage and any trophy earned, then awards the existing best-result
   sigils. The next defence can turn those scarce resources into stronger ranks or a pattern.

Gold is for this fight; salvage and trophies buy persistent patterns; sigils unlock skills and
ranks. A replay can improve a location's best salvage result but cannot farm it indefinitely.
An early flat-damage pattern helps now, while a rank-scaling pattern asks the player to live with
a weaker opening. Cashing drops or a breach cache can save this fight, while saving them moves
the first area attack closer. Neither path should be required to finish the campaign.

## Combat scale and pacing

The opening attack is an **Arrow Tower**, one arrow at one enemy. It is always available. Tristram
offers no damaging area attack; neither an upgrade, skill, spell, nor a crafted pattern bypasses
that rule. All first-location monster HP and individual hit damage are in the 1–20 range.

Use one frozen balance profile to generate the common scale. These are starting calibration
values, not twelve hand-tuned life factors:

| Knob | Initial value | What it controls |
| --- | ---: | --- |
| `base_hp` | 7 | HP of the opening common enemy |
| `location_growth` | 1.08 | HP and gold unit growth per location |
| `wave_growth` | 1.05 | HP growth within a location |
| `arrow_hit` | 2 | Rank-I Arrow damage; ranks add 1 each |
| `base_gold_unit` | 12 | Rank-I Arrow price and the unit for other prices/rewards |
| `starting_units` | 3 | Starting gold in Arrow-equivalent towers |
| `wave_income_units` | about 1 | Kill gold plus clear reward for an ordinary wave |

`HP = round(base_hp × role_hp × location_growth^location_index ×
wave_growth^wave_index × encounter_factor)`. The first Fallen is 7 HP and the first
Shaman, with `role_hp` near 2, is about 14–17 HP even in Tristram's late waves. The
same common enemy is about 23 HP in the last location's final wave. A basic Arrow goes
from four hits to twelve; invested ranks and overlapping coverage close that gap. The
curve raises pressure without inflating every tower automatically. Bosses and named
breach elites have authored role factors and abilities, but their HP still derives from
the profile. Door HP, spell damage, rank prices and wave gold budgets derive from the
same opening units, with small authored role ratios rather than unrelated large tables.

The first pass aims for a three-Arrow opening and approximately one Arrow-equivalent
from the first wave if everything dies. Gold is allocated across that wave's enemies
and clear reward, so adding swarm bodies does not silently multiply income. Leaks
forfeit their kill gold. A breach pack pays its ordinary kill gold, but the cache is
paid only when its whole pack is killed. A player who sells salvage receives useful
same-run gold and gives up that salvage for forging.

The campaign teaches power slowly:

| Location | New player power | Area damage |
| --- | --- | --- |
| 1 Tristram | Arrow; Cleanse | none |
| 2 Graveyard | gate; first breach and salvage decisions | none |
| 3 Cathedral | single-target Pyre | none |
| 4 Catacombs | single-target chill; second breach | none |
| 5 Caves | single-target poison | none |
| 6 Hell's Gate | single-target Storm; third breach | none |
| 7 Docks | possible small Pyre blast if three trophies and salvage were saved | optional, costly |
| 8 Spider Forest | fourth breach; support and rank choices | optional, costly |
| 9 Jungle | Frost nova can be learned and bought without trophies | first reliable access |
| 10 Drowned City | fifth breach; chain recipe | additional costly choice |
| 11 Travincal | high single-target damage recipe | additional costly choice |
| 12 Temple | sixth breach; final test of the chosen build | no automatic grant |

This is an unlock order, not a promise that every player receives every power. Early
Pyre ranks remain single-target. Storm begins with zero jumps. Frost begins as a
single-target chill attack and becomes a nova only through its late unlock. Fire Ball,
Contagion, Shatter, Corpse Explosion, Meteor and Frozen Orb must be moved or changed so
they cannot grant early area damage. Smite is a modest single-target interrupt, not a
100-damage early nuke. Enemy leader curses may still cover several towers; that is the
game's central threat, with Cleanse as opening counterplay.

The word *slow* applies to power and options, not waiting through longer waves. Tune
path exposure, spawn spacing, and counts to keep individual defences concise. Aim for
roughly four hits on an opening common enemy and four to six hits from an appropriately
invested late tower, with routes and leaders supplying the harder decisions.

## Open fields, routes, and enemies

Keep the 25×14 viewport. Author open, traversable fields with sparse obstacles,
several build areas, two ordinary entrances from the second location onward, and a
visibly sealed breach entrance where offered. A level has a sanctuary, entrance
positions and a bounded set of route variants through the field. Route intersections
are allowed. Route geometry is immutable and validated when the level loads.

Each spawned monster receives a committed route from its entrance. **Wanderers** get a
seeded choice among at least three spatially distinct, bounded detours. **Runners**
take the shortest route and have the speed/HP tradeoff that makes the direct approach
their identity. A choice belongs to the spawn, not a combat-dependent global random
draw; the same seed and spawn ordinal choose the same route in a normal world and a
planner clone. A detour should be no more than about 1.6 times the direct route so
wandering never means an enemy stalls or walks away indefinitely. Route choices can
cross the open field but never cross an obstacle or a build pad.

Route-local distance is still useful for fast movement and range intervals, but two
monsters' `s` values on different routes are incomparable. Combat uses actual position
for reach and effects and remaining distance/time to the sanctuary for threat order.
The level provides route position, heading, coverage and door crossings through one
small interface. Gate semantics are explicit: a route that crosses a gate stops and
batters it; a route that goes around it bypasses it. A side entrance creates a real
new angle of attack, not a second spawn on the same line.

Start with one Tristram or Graveyard pilot arena. Migrate movement, tower targeting,
the planner estimate, scripted players, view interpolation, gate checks and replay
serialization against it before migrating all twelve locations. The curse planner's
exact rollout stays the game's own deterministic world. Its cheap candidate estimate
must project route-specific future positions; the quality tool verifies that it still
shortlists good curses. Painted grounds are invalidated by a geometry fingerprint and
repainted after the open layouts are final, so an old corridor painting never silently
covers a new route.

## Breaches and loot

Six authored breaches are offered at locations 2, 4, 6, 8, 10 and 12, each on a
specified break. The UI shows the next wave, side entrance, named elite, pack roles,
and the two possible rewards before the decision. The breach command records its
reward mode (`cash` or `trophy`) in the replay. The side pack joins the next ordinary
wave, carries an encounter ID, and can contain enemies otherwise absent from that
location. These named elites need distinct behavior, not just a larger HP number;
start with direct runners, gate bypassers or leader support and show their role in the
intro. Breach status and reward counters are copied into every planner clone.

Ordinary enemies drop gold immediately. A small, fixed salvage budget per location is
assigned to specific spawns by a seed separate from combat randomness. A kill emits
the item drop; a leak loses it. The player may sell held salvage during breaks at a
profile-defined exchange rate. Unsold salvage is banked only on victory. Progress
records the best banked salvage per location and credits only the improvement on a
replay. That gives items to ordinary monsters without a repeatable grind.

A named side elite visibly drops its trophy on death, but the trophy or cash cache is
earned only after the full side pack dies and the defence ends in victory. On the first
successful clear, choosing cash forfeits that breach's one permanent trophy. Later
replays may still earn the run-only cash cache. A failed defence commits neither the
trophy nor its forfeiture. Cash is about 0.8 of a rank-I tower price at that stage;
the first-pass number must be tuned against the extra lives the breach costs.

Patterns are authored recipes, not random affixes or per-tower crafting. Forging
spends banked salvage and, for powerful patterns, trophies. A family equips one owned
pattern between defences; equipment is fixed throughout a fight and baked into its
tower ranks before the world starts. Skills can still be freely reset. Candidate
recipes to tune:

| Pattern | Price idea | Immediate/future role |
| --- | --- | --- |
| Honed String (Arrow) | 3 salvage | +1 hit at every rank; strong immediately, flat return |
| Laminated Limbs (Arrow) | 6 salvage | +0/+1/+2 by rank; weak now, stronger once ranks are learned and bought |
| Blast Chamber (Pyre) | 8 salvage + 3 trophies | a small late blast; earliest use in location 7 if every early trophy was saved |
| Forked Coil (Storm) | 9 salvage + 2 trophies | one jump; trades scarce trophies against Blast Chamber |
| Execution Bow (Arrow) | 10 salvage + 2 trophies | large single-target hit against leaders; a boss answer instead of area damage |

The numbers are first calibration values. With six trophies total, the player cannot
forge every high-end option. A player who chooses early cash still has the late Frost
nova route and single-target solutions; the campaign must never require a trophy.

## Implementation seams and invariants

| Module | New responsibility | Interface callers should learn |
| --- | --- | --- |
| `sim/balance.py` | profile, stage scale, role HP, tower/economy budgets | effective stats for a location and wave |
| `sim/level.py` | validated entrances, routes, coverage, gate crossings | position/heading/remaining/coverage by route |
| `sim/model.py` | deterministic movement, drops, breaches, run receipt | existing commands plus open breach and sell salvage |
| `sim/skills.py` | bake ranks and an equipped pattern together | immutable run loadout |
| `ui/progress.py` | best salvage, trophy claims, patterns, equipment | atomic result recording and pre-run equip |
| `ui/battle.py`, `ui/briefing.py`, `ui/hud.py` | choices and readable threat/reward feedback | world commands and progress operations |
| players, planner, replay, art | follow world/level interface | no direct assumption of one global `s` |

All movement and drops must be deterministic across source, mypyc, clone, pickle and
replay. No simulation module imports Saga2D. A replay version records the run loadout,
breach choices and salvage sales; old replays must report their incompatible rules
version clearly. A victory applies sigils, best salvage and trophy claims in one save
at the existing outcome boundary. An opened but uncleared breach cannot pay. Every
route reaches the sanctuary, and every elite either dies or leaks before victory.

## Delivery and verification

1. Land this design and the current baseline. Build the central curve, Arrow Tower and
   early single-target unlocks as one playable vertical slice. Verify opening HP/hit
   ranges, a real battle, source/mypyc parity, and a screenshot of the new tower.
2. Land the route interface and one open arena. Verify three seeded wander variants,
   a shortest runner, gate crossing/bypass, actual-range targeting on two routes,
   clone/replay determinism and the planner's decision time.
3. Land one breach and its HUD/replay command, then generalize to six authored
   encounters. Verify that leaks and defeats give no permanent reward, and that a
   successful optional pack does not pay twice.
4. Land salvage, the atomic result receipt, forging and briefing loadout. Exercise a
   full UI flow from drop to sale or bank to forge to the next defence.
5. Migrate the twelve maps and unlock order, regenerate/fingerprint floor art, refresh
   stored player plans and tune waves. Run `tools/balance.py`, `tools/curse_quality.py`,
   `tools/campaign_balance.py`, `tools/margin.py` and `tools/sim_bench.py` through the
   shared heavy-job slot. After each rules unit, record before/after balance and curse
   quality in its commit. Run the full suite and mypy, then inspect real screenshots
   and a showcase clip. Keep only the final useful evidence in the shared evidence
   folder.

Acceptance targets: opening attacks are single-target and use 1–20 HP/hit numbers;
no normal player has damaging area attacks before the costly location-7 route, and
there is a trophy-free path by location 9. The first two locations stay teachable;
later strong scripted players have a narrow but positive margin, and an AOE-free
loadout can still win. Smart curses retain at least 0.85 of the best available curse
at the campaign's key locations and late decisions stay within the current 100 ms
target. Source and compiled simulations produce the same events and outcome for the
same seed, including a breach and a forged pattern.

### Baseline before changes

`python3 ~/saga/tools/slot.py -- uv run python tools/balance.py --location tristram
--policies none,random,smart --defenders 4 --jobs 2`: lives lost mean 10.2 without
curses, 18.2 with random leaders, 23.8 with smart leaders; smart won 2/4.
`python3 ~/saga/tools/slot.py -- uv run python tools/curse_quality.py --location
tristram --moments 8 --jobs 2`: smart share of best 0.962 across eight useful
decisions (small sample). Today the first Fallen is `48 × 1.49 = 71.5` HP and the
opening Frost Shrine already attacks an area.
