# Hellward — design criteria

How each item in [game-design.md](../game-design.md) is judged, fixed before it is built. Every criterion names a
**judge**: a test (`tests/`), the scorecard (`tools/scorecard.py`, which prints every measurable criterion as
pass/fail with its number), a bot experiment, or Ilya. Targets are first guesses and live in the tuning file
(`hellward/sim/tuning.toml`) or here; tuning moves them, the criterion itself stays.

The scorecard says which criteria are met; the iterations at the end say which are built.

## Decisions the design leaves open

These follow from the design's own words; Ilya can overturn any of them.

- **D1. Runs.** The design speaks of runs, relics that shape a run, and choices a player can level into badly.
  A **run** is one walk through the campaign's twelve locations. Within a run: hero level and XP, sigils, learned
  skills (no free respec), relics, and gold all carry from location to location. Each location starts with a full
  sanctuary (20 lives). Losing a location ends the run. Across runs: the meta currency, the shop's purchases, and
  which locations and story pages have been seen.
- **D2. Gold carries.** Point 3 asks for advantage that accumulates across levels; gold left at a location's end
  is carried to the next (a share set in tuning). Scarce real estate is the brake: a rich player cannot just
  build more, only rank up, which buys less per gold.
- **D3. The meta currency is salvage**, the existing drop. The Forge becomes the shop: tower AI modes and forged
  patterns. Breach trophies become relics.
- **D4. Damage over time ignores armor** (poison, burning floor); every hit is reduced. A tuning switch.
- **D5. Skip is per wave**, offered during the break before it, from a simulation of that wave with no player
  input from the current state, the real leaders included. Skipping applies exactly that outcome.
- **D6. Curses are answered by where towers stand, not by clicks.** Cleanse goes, as the design asks; so does
  breaking a chant with a spell (Smite and Frozen Orb no longer interrupt), which is the same urgent clicking, and
  with it the resolute leader that only existed to answer interrupts.

## The three pillars

### G1. No grind: skip what is already won

| ID | Criterion | Judge | Target |
|---|---|---|---|
| G1.1 | Skip is offered exactly when the simulated wave loses no life and no tower. | test | always |
| G1.2 | Skipping applies the simulated outcome (gold, XP, drops, verb counters, relic counters) plus a small bonus. Playing the wave with no input gives the same digest. | test | bonus 10% of the wave's gold |
| G1.3 | The prediction is ready during the break: computed in a worker, compiled. | scorecard (bench) | p95 ≤ 3 s per wave |
| G1.4 | A skipped wave hands the client a vision: its deaths (time, place, cause), curses and leaks, small enough to replay in a few seconds. | protocol test, then the client | ≤ 20 KB, replay ≤ 6 s |
| G1.5 | Skip removes grind without trivialising: in a strong bot's run a good share of waves are skippable. | scorecard (run bots) | 25–60% of waves |

### G2. Not bullet hell, not numbers without end

| ID | Criterion | Judge | Target |
|---|---|---|---|
| G2.1 | Few monsters: bodies per wave, and alive at once. | scorecard (content, bot runs) | ≤ 30 per wave; p99 alive ≤ 25 |
| G2.2 | Few towers: a strong bot's defence. | scorecard (bot runs) | median ≤ 10, max ≤ 14 per location |
| G2.3 | Few levels: three ranks per tower. | test | 3 |
| G2.4 | Small numbers that grow slowly. | scorecard (content) | first monster life 8–12; first hit 1–2; last location's ordinary median life 60–120, none over 200; bosses ≤ 1000; no hit over 30 |
| G2.5 | Progression is options, not stats: everything a run can stack on one tower's hit. | scorecard (perk and relic tables) | ≤ ×2 its rank's base |
| G2.6 | Tower AI modes make towers more efficient. | bot A/B | ≥ 10% more damage per tower, or margin +10% |

### G3. Hard, but a great player snowballs

| ID | Criterion | Judge | Target |
|---|---|---|---|
| G3.1 | Hard: a middling player rarely wins a run; the strongest bot usually does. | run bots | middling ≤ 30%, strongest ≥ 70% |
| G3.2 | Advantage accumulates: by each act's last location the strongest bot holds far more than the middling one. | run bots | ≥ 3× carried gold, ≥ +3 levels |
| G3.3 | Bonus waves the player controls (when, and how big a stake) can make a player fabulously rich, and are risky. | run bots A/B | best bot ≥ 5× the gold of one that never takes them; the middling bot taking all of them wins fewer runs |

## Meta-progression

| ID | Criterion | Judge | Target |
|---|---|---|---|
| M1 | A meta currency every run earns, win or lose, spent in a shop on things to collect (tower AI modes, patterns); all of it can be bought eventually. | test; scorecard | whole shop ≈ 15–30 runs' median income |
| M2 | Diablo's XP bar: kills and clears give XP; level-ups are frequent early and celebrated (an event). | test; scorecard (run bots) | first level-up in Tristram; level 15–25 at the run's end |
| M3 | Skill points = level + sigils. Sigils: 3 for lives kept, 3 for the location's own goals about how it was won. | test; scorecard | every location has 3 distinct goals; each goal met by some bot and missed by another |
| M4 | A tech tree too expensive to open: many tower kinds, paid in skill points; choices stick within a run. | scorecard | ≥ 12 tower kinds; whole tree ≥ 2.5× a perfect run's points; no free respec |
| M5 | Different runs combine different towers. | run bots | ≥ 6 distinct tower sets over 10 seeds of the strongest bot |
| M6 | Half the tower kinds are mechanics towers: no direct damage, each produces or consumes one verb. | test (content lint) | ≥ 50% |
| M7 | Towers can learn charges: a stronger shot held in up to 3 charges that recharge. An AI mode decides when to spend. A bought mode foresees whether the monster dies downstream anyway and holds the charge. | test; bot A/B | max 3, ~15 s; foresight wastes ≥ 20% fewer charges and raises the margin |
| M8 | Slow numbers: see G2.4. Skills add little absolute damage. | scorecard | see G2.4, G2.5 |
| M9 | Absolute armor: each hit loses the target's armor. Somewhere in each act a light-hitting build falls behind. | test; bot A/B | in each act at least one location a light build loses and a heavy build of equal gold wins |
| M10 | The shrine: an ordinary monster that gets through strikes it and is obliterated; a boss strikes and is sent back to its portal with its life, to walk again. | test | always |

## Global spells

| ID | Criterion | Judge | Target |
|---|---|---|---|
| S1 | No curse dispel. | test | Cleanse is gone; no spell lifts or prevents a curse |
| S2 | Spells are a little direct action: mostly killing one or two strays the towers' targeting let through. | scorecard (bot runs) | a strong bot casts ≥ 1 spell in most waves; spells make ≤ 15% of its kills; a stray-killing spell can finish a monster at half its life |
| S3 | Some spells boost a tower a lot, and the boost is fragile: the leaders' curses go for the boosted tower. | test; bot runs | boost ≥ ×1.5 for its duration; the leaders curse a boosted tower clearly more often than the same tower unboosted |

## Verbs, relics and predictability

| ID | Criterion | Judge | Target |
|---|---|---|---|
| V1 | About five verbs, each an event in the player's own engine, counted per wave: corpse, charge, curse taken, overkill, banish. | test; scorecard (bot runs) | each 3–40 times a wave in a build that leans into it |
| V2 | The player sets a verb's frequency through build and placement. | bot A/B | leaning in ≥ 2× the count of a build that does not |
| V3 | Leaning into a verb costs something, and some relic turns that cost into payoff. | content lint (per verb, a relic) | every verb |
| V4 | Each mechanics tower produces or consumes one verb. | content lint | all |
| V5 | Most relics read one verb and write another. | content lint | ≥ 60% |
| V6 | Consuming a debuff can be a verb. | content | at least one |
| V7 | Relics add no new mechanic; they combine existing ones. Some unlock tech the player could not otherwise use; many carry a downside. | content lint | ≥ 30 relics; ≥ 5 enablers; ≥ 30% with a downside |
| V8 | No chance procs: a relic fires on a count or a predictable condition, and its counter is visible. | content lint; test | no relic touches the random stream; every counter in the client state |

## Real estate

| ID | Criterion | Judge | Target |
|---|---|---|---|
| R1 | Good cells are scarce by map design; many cells start occupied (rock, water, graves, trees). | scorecard (maps) | occupied ≥ 40% of the ground beside the halls; ≤ 12 prime cells per map |
| R2 | A cell is worth what it reaches of the routes, and the player can see that worth. | test; protocol | per-cell coverage in the level facts |
| R3 | Upgrading buys less per gold than another tower, but more per cell. | scorecard (tower tables) | every attacking kind: rank II and III marginal damage per gold < rank I's; per cell > rank I's |
| R4 | Scarcity keeps the tower count low without a cap. | scorecard (bot runs) | see G2.2, no build limit in the rules |
| R5 | The best cells sit together, and area curses punish that. | scorecard (maps; bot runs) | top prime cells within 2 tiles of another; strong bots' landed curses catch ≥ 1.5 towers on average |
| R6 | Monsters take cells: some kinds block a cell for later building, visibly before it lands. | test; bot runs | telegraph ≥ 1.5 s; 1–5 blocked cells per location that has them |
| R7 | A changed cell shows its change and how long it lasts. | test; protocol | state carries cell status and seconds left |

## Tuning and judging

| ID | Criterion | Judge | Target |
|---|---|---|---|
| T1 | Every gameplay number lives in one tuning file, with a comment; an override file swaps any of them for a run of the tools. | test | `hellward/sim/tuning.toml`; `HELLWARD_TUNING` overrides, seen by worker processes |
| T2 | Bots play whole runs through a person's hands, using every system (skills, relics, modes, skip, bonus waves), so the targets above can be measured. | tests; scorecard | a middling bot and a strong bot |
| T3 | One command reports every measurable criterion. | `tools/scorecard.py` | prints each ID with its number and pass/fail |

## Iterations

Each iteration ends with the suite green, the scorecard run, and the statuses here updated.

1. **Foundations:** the tuning file, the scorecard's static checks, the client's list of rules (`docs/rules-for-client.md`).
2. **Numbers, armor, the shrine, spells:** the 10 → 100 life scale, per-hit armor, a heavy-hitting tower, the shrine
   strike and the boss's return; Cleanse and chant-breaking go, spells become stray-killers and fragile tower boosts
   (G2.4, M8, M9, M10, S1–S3).
3. **Real estate:** terrain on the build ground, scarce maps, cell worth, rank prices, monsters that block cells (R1–R7).
4. **Charges and tower AI modes** (M7, G2.6).
5. **Verbs and mechanics towers:** corpses, overkill, banish, curses taken; Moon Well, Ossuary, Effigy, Tolling Bell
   (V1–V7, M6).
6. **Relics** (V3, V5, V8, V9, M5).
7. **Runs and meta:** XP and levels, sigils with goals, the tree of many towers, carried gold, the shop (D1–D3,
   M1–M4).
8. **Skip and bonus waves** (G1, G3.3).
9. **Bots and tuning:** run bots, the scorecard's run measurements, tuning until the targets hold (G1.5, G2, G3, T2).
10. **Smarter, faster monsters** late in the campaign: route choice against the towers, then a final tuning pass.
