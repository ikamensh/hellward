# Hellward: hall-network progression redesign

Status: implemented and under final campaign calibration on 2026-09-28. Painted floors with old
road geometry are held back by a layout fingerprint; image-generated terrain materials and the
current ground renderer draw the bounded monster halls.
The opening baseline was measured on 2026-09-28 from `3d2911c` with the compiled simulation.
The current rules are also described in [design.md](design.md) and [campaign.md](campaign.md).

## The intended loop

1. Before a defence, choose learned skills and equip at most one forged pattern for each tower
   family. A pattern changes every tower of that family built in this defence. Rank unlocks remain
   skills; towers and their upgrades still cost battle gold.
2. Build a few cheap, single-target towers beside the monster halls. Ordinary enemies may take
   one of several visibly different trails from multiple entrances; a runner heads directly for
   the sanctuary. Position, range and approach direction matter more than a folded corridor's
   triple coverage.
3. Kills immediately pay gold and sometimes drop salvage. During a break, sell held salvage for
   gold now or carry it toward a future pattern. The sale cannot be undone within that defence.
4. On specified breaks, a sealed side entrance offers a **breach**: decline, take a gold cache, or
   seek a trophy. Opening it adds an announced, harder pack and a named elite to the next wave.
   The chosen reward is earned only if every side enemy dies. A leaked side enemy voids it.
   Battle cash pays as soon as the pack is clear; a trophy is banked only on victory.
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

Use one frozen balance profile to generate the common scale. These are the current
profile values, not twelve hand-tuned life factors:

| Knob | Current value | What it controls |
| --- | ---: | --- |
| `base_hp` | 6 | HP of the opening common enemy |
| `location_growth` | 1.055 | HP and gold unit growth per location |
| `wave_growth` | 1.05 | HP growth within a location |
| `arrow_hit` | 2 | Rank-I Arrow damage; ranks add 1 each |
| `base_gold_unit` | 12 | Rank-I Arrow price and the unit for other prices/rewards |
| `starting_units` | 3 | Starting gold in Arrow-equivalent towers |
| `starting_units_growth` | 0.5 | Extra opening Arrow units per location to cover more approaches |
| `wave_density_decay` | 0.5 | How quickly old area-attack swarm counts shrink |
| `minimum_wave_density` | 0.4 | The late-campaign floor on that shrinkage |
| `wave_income_units` | 1 | Kill gold plus clear reward in the first ordinary wave |
| `wave_income_growth_units` | 0.5 | Extra local gold units in each later wave |
| `salvage_budget` | 3 | Maximum ordinary salvage drops in one defence |
| `breach_pack_income_units` | 0.5 | Extra kill gold shared by a side pack |
| `breach_cache_units` | 0.8 | Immediate cash reward for clearing a side pack |

`HP = round(base_hp × role_hp × location_growth^location_index ×
wave_growth^wave_index × encounter_factor)`. The first Fallen is 6 HP and the first
Shaman, with `role_hp` near 2, is about 12–15 HP even in Tristram's late waves. The
same common enemy is about 15 HP in the last location's final wave. A basic Arrow goes
from three hits to eight; invested ranks and overlapping coverage close that gap. The
curve raises pressure without inflating every tower automatically. Bosses and named
breach elites have authored role factors and abilities, but their HP still derives from
the profile. Door HP, spell damage, rank prices and wave gold budgets derive from the
same opening units, with small authored role ratios rather than unrelated large tables.

The opening has three Arrow-equivalents, adding half a local Arrow unit per later
location to cover more entrances. The first wave pays one local Arrow-equivalent
if everything dies, and each later wave adds half a unit. Gold is allocated across
each wave's enemies and clear reward, so adding swarm bodies does not silently
multiply income. Leaks forfeit their kill gold. A breach pack shares an extra half
unit of kill gold, but the cash cache is paid only when its whole pack is killed.
A player who sells salvage receives useful same-run gold and gives up that salvage
for forging.

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
| 9 Jungle | small Fire Ball and Shatter bursts can be learned without trophies | first reliable access |
| 10 Drowned City | fifth breach; chain recipe | additional costly choice |
| 11 Travincal | high single-target damage recipe | additional costly choice |
| 12 Temple | sixth breach; final test of the chosen build | no automatic grant |

This is an unlock order, not a promise that every player receives every power. Early
Pyre ranks remain single-target. Storm begins with zero jumps. Frost begins as a
single-target chill attack and gains a small burst only through its late unlock. Fire Ball,
Contagion, Shatter, Corpse Explosion, Meteor and Frozen Orb must be moved or changed so
they cannot grant early area damage. Smite is a modest single-target interrupt, not a
100-damage early nuke. Enemy leader curses may still cover several towers; that is the
game's central threat, with Cleanse as opening counterplay.

The word *slow* applies to power and options, not waiting through longer waves. Tune
path exposure, spawn spacing, and counts to keep individual defences concise. Aim for
roughly three hits on an opening common enemy and four to six hits from an appropriately
invested late tower, with routes and leaders supplying the harder decisions.

## Open fields, routes, and enemies

Each location now uses a 33×18 field fitted above the fixed-size HUD. Monster halls
are authored as walkable tiles, three tiles wide where routes branch and rejoin.
The remaining interior is buildable tower ground, separated visibly by the hall edge.
From Graveyard onward, maps have two ordinary entrances; six also show a sealed
breach entrance. A level validates every route against its hall before play starts.

Each spawned monster receives a committed route from its entrance. **Wanderers** get a
seeded choice between a direct hall and a longer loop from their entrance. **Runners**
take the shortest route and have the speed/HP tradeoff that makes the direct approach
their identity. A choice belongs to the spawn, not a combat-dependent global random
draw; the same seed and spawn ordinal choose the same route in a normal world and a
planner clone. A detour should be no more than about 1.6 times the direct route so
wandering never means an enemy stalls or walks away indefinitely. Route choices can
branch and rejoin inside the monster halls but never cross a buildable tower plot.

Route-local distance is still useful for fast movement and range intervals, but two
monsters' `s` values on different routes are incomparable. Combat uses actual position
for reach and effects and remaining distance/time to the sanctuary for threat order.
The level provides route position, heading, coverage and door crossings through one
small interface. Gate semantics are explicit: a route that crosses a gate stops and
batters it; a route that goes around it bypasses it. A side entrance creates a real
new angle of attack, not a second spawn on the same line.

The curse planner's exact rollout stays the game's own deterministic world. Its cheap
candidate estimate projects route-specific future positions; the quality tool verifies
that it still shortlists good curses. The floor fingerprint includes the walkable mask,
so an old painting cannot silently put monster space under a tower plot. Image-generated
terrain materials and code-drawn hall edges now form the floor. The old corridor
paintings were removed from the working assets because their geometry was obsolete.

## Breaches and loot

Six authored breaches are offered at locations 2, 4, 6, 8, 10 and 12, each on a
specified break. The UI shows the next wave, side entrance, named elite, pack roles,
and the two possible rewards before the decision. The breach command records its
reward mode (`decline`, `cash` or `trophy`) in the replay. The side pack joins the next ordinary
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

A named side elite is marked in the battle, but the trophy or cash cache is
earned only after the full side pack dies. The trophy is banked only if the defence ends
in victory; the cash cache pays immediately after that pack clears. On the first
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
| `server/progress.py` | best salvage, trophy claims, patterns, equipment | atomic result recording and pre-run equip |
| `server/battle.py`, `server/campaign.py`, the Godot client's briefing and HUD | choices and readable threat/reward feedback | world commands and progress operations |
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
2. Land the route interface and one open arena. Verify seeded wander routes,
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

### Measured first redesign before the corridor revision

With the `1.055` location-growth profile, `tools/balance.py --location tristram
--policies none,random,smart --defenders 4 --jobs 2` reports 4/4 wins under
each policy. Mean lives lost are 3.8 without curses, 8.8 with random leaders,
and 8.8 with smart leaders. `tools/curse_quality.py --location tristram
--moments 8 --jobs 2` gives the smart planner 1.000 share of the best curse
across five useful sampled decisions, at 15 ms on average (29 ms maximum).
These are small, seeded checks of the new opening, not general win-rate claims.
A separate 16-moment Cathedral check retained 0.958 of the best curse across
eleven useful decisions.

An eight-seed earned-sigil campaign (`tools/campaign_balance.py --players
veteran,adaptive --seeds 1000-1007 --margin --leaders --jobs 4`) found the
adaptive defender winning all eight defences at all twelve locations without
forged patterns. The apprentice also won 8/8 in each of the first two locations.
The strong defender's median HP difficulty margin was 1.10 in Tristram, 1.20
at Hell's Gate, 2.15 at the Act II opening in the Docks, and 1.14 at the Temple.
That measures a gentler middle Act II and a tight final battle; a less capable
veteran defender still lost every sampled Spider Forest, Hell's Gate and Temple
defence. The former uniform margin targets are not met on every location.
Future tuning can narrow the Act II middle without moving area attacks earlier.

### Corridor revision and opening adjustment

The 33×18 corridor maps initially made Tristram too hard at `base_hp=7`: the same
four-defender check lost 8.5 lives without curses, 23.0 with random curses, and
22.5 with smart curses. The eight-moment curse-quality
check retained 0.924 of the best available choice across six useful decisions.

Changing the one shared `base_hp` knob to 6 restored 4/4 wins under each policy.
Mean lives lost are 0.2 without curses, 7.0 with random curses, and 8.0 with smart
curses. Curse quality is 1.000 across six useful decisions (9 ms mean, 15 ms max).
The new geometry's Act I and Act II planned builds and Warden builds were retrained.
The final opening check still gives 4/4 wins for each leader policy with mean lives
lost of 0.2/7.0/8.0 (none/random/smart), and an eight-moment curse-quality check
still gives smart 1.000 of the best choice across six useful decisions.

### Earned-sigil campaign on the corridor maps

An eight-seed campaign across all twelve locations and seven scripted defenders
(`tools/campaign_balance.py --seeds 1000-1007 --jobs 5`) gave each site the sigils
earned by the better of Adaptive and Warden in the earlier sites. That budget grows
from 0 in Tristram to only 24 at the Temple. Planned, the searched-build ceiling,
won 8/8 at each of the first eleven locations and 7/8 at the Temple on that same
budget, without forged patterns. Ordinary won 8/8 in Tristram but lost all sampled
Hell's Gate, Jungle, Travincal and Temple defences. Those contrasts show the slow
curve now asks for better builds as the campaign advances.

The Temple is tight: Adaptive won 3/8 and Warden 0/8 at 24 sigils. Every Adaptive
defeat leaked the 20-life Bone Priest; the Priest's remaining HP varied too much
for a small boss-HP cut to solve the underlying build choices. A four-seed HP
margin sample gave Planned median 0.99 and Adaptive 0.90 at that earned budget.
This is a measured limit of the scripted defenders, not a claim about human win
rates. The old Corner build now places towers beside hall bends, but it remains
weak against the new openings; the first two locations are instead teachable to
the Ordinary and Apprentice defenders.

The planner stays accurate in the opening, but its late Spider Forest decision
time is above the 100 ms target. A one-job run found 351 ms at the 95th percentile
for one seed, while the five-job campaign table's 2064 ms figure also includes
worker contention. Later rollout performance needs profiling before making a
quality-for-speed trade. The full campaign table and reproduction commands are
retained in the stack's `evidence/hellward/corridor-campaign` folder.
