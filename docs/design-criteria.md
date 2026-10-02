# Hellward — design criteria

How each item in [game-design.md](../game-design.md) and [design-choices.md](design-choices.md) is judged, fixed
before it is built. Every criterion names a **judge**:
- a test (`tests/`);
- the scorecard (`tools/scorecard.py`, which prints every measurable criterion as met or missed, with its number);
- a bot experiment;
- or Ilya.

Targets are first guesses and live here or in the tuning data (`hellward/sim/data/*.toml`). Tuning moves the
targets; the criterion itself stays. The scorecard says which criteria are met; the readiness stages in
design-choices.md (section 20) say which are built when.

## The three pillars

### G1. No grind: skip what is already won

| ID | Criterion | Judge | Target |
|---|---|---|---|
| G1.1 | When the player calls a wave, Skip is offered exactly when that wave, played from now with no input and the real leaders, loses no life. Bonus waves are never predicted. | test | always |
| G1.2 | Skipping adopts the predicted world, plus the purse difference since the prediction began, plus a small bonus. Playing the wave with no input reaches the same world. | test | bonus 10% of the wave's gold |
| G1.3 | The prediction runs in its own process, compiled, and is ready in time. | scorecard (bench) | p95 ≤ 3 s per wave |
| G1.4 | A skipped wave hands the client a vision: its deaths (time, place, cause), curses and leaks, replayed in a few seconds. A click ends it. | protocol test, then the client | ≤ 20 KB, replay 3–6 s |
| G1.5 | Skip removes grind without trivialising. | scorecard (run bots, inline prediction) | 25–60% of waves skippable for a strong bot |
| G1.6 | A person's call usually finds the prediction ready. | scorecard (latency model) | ≥ 80% of calls |

### G2. Not bullet hell, not numbers without end

| ID | Criterion | Judge | Target |
|---|---|---|---|
| G2.1 | Few monsters. | scorecard (content, bot runs) | ≤ 30 bodies a wave; p99 alive at once ≤ 25 |
| G2.2 | Few towers in a strong bot's defence. | scorecard (bot runs) | median ≤ 10 a location, max ≤ 14 |
| G2.3 | Few levels: at most three ranks a tower. | test | ≤ 3 |
| G2.4 | Small numbers that grow slowly, as whole numbers. | scorecard (content) | see below |
| G2.5 | Progression is options, not stats. | scorecard (perk and relic tables) | see below |
| G2.6 | Tower AI modes make towers more efficient. | bot A/B | ≥ 10% more damage per tower, or margin +10% |

G2.4's targets:
- the first monster's life is 8–12, and the first hit 1–2;
- the last location's ordinary monsters have a median life of 60–120, none over 200;
- bosses ≤ 1000;
- no hit over 30;
- every hit is a whole number.

G2.5's targets: the factors a run can stack on one hit multiply to at most ×2. Every verb loop gains less than 1.

### G3. Hard, but a great player snowballs

| ID | Criterion | Judge | Target |
|---|---|---|---|
| G3.1 | Hard: a middling player rarely wins a run; the strongest bot usually does. | run bots | middling ≤ 30%, strongest ≥ 70% |
| G3.2 | Advantage accumulates. | run bots | by each act's last location, the strongest bot holds ≥ 3× the middling bot's gold and ≥ +3 levels |
| G3.3 | Bonus waves the player controls can make a player rich, and are risky. | run bots A/B | see below |
| G3.4 | The power budget closes. | scorecard (power table) | at every location, the reference board's damage per second covers the last wave's life on the field per second, without relics or charges |

G3.3's targets:
- by each act's end the strong bot holds ≥ 5× the gold of a bot that never summons;
- the strong bot summons ≤ 3 a location;
- the middling bot summoning every break wins fewer runs.

## Meta-progression

| ID | Criterion | Judge | Target |
|---|---|---|---|
| M1 | A meta currency every run earns, win or lose, spent on things to collect. Everything can be bought eventually. | test; scorecard | whole shop ≈ 20 runs' median income |
| M2 | Diablo's XP bar: kills and clears give XP, and level-ups come often and are celebrated. | test; scorecard (run bots) | first level-up in Tristram's second wave; ~40 levels by the Temple |
| M3 | Skill points = levels + sigils. Sigils: 3 for lives lost at the location, 3 for its goals about how it was won. | test; scorecard | see below |
| M4 | A tech tree too expensive to open, paid in skill points, with reskill points as the only way back. | scorecard | ≥ 14 tower kinds; whole tree ≥ 2.5× a perfect run's points |
| M5 | Different runs end in different builds, pushed by their relics. | run bots | ≥ 6 distinct tower sets over 10 seeds of the strongest bot |
| M6 | About half the tower kinds are mechanics towers: no direct damage, each produces or consumes one verb. | test (content lint) | ≥ 40% |
| M7 | Charges and a bought Foresight mode. | test; bot A/B | see below |
| M9 | Absolute armor: each hit loses the target's armor (at least 1 is dealt). A light build falls behind somewhere. | test; bot A/B | in each act from the Catacombs on, a location a light build loses and a heavy build of equal gold wins |
| M10 | The shrine: an ordinary monster strikes and is obliterated; a boss strikes (5 life) and is sent back to its portal with its life. | test | always |

M3's targets:
- every location has 3 distinct goals;
- each goal is met by some bot and missed by another.

M7's targets:
- an attack tower with its ability holds up to 3 charges, one per ~15 s, with a charged-attack cooldown;
- Foresight wastes ≥ 20% fewer charges and raises the margin.

## Global spells

| ID | Criterion | Judge | Target |
|---|---|---|---|
| S1 | No curse dispel, no chant interrupt. | test | no spell lifts, prevents or breaks a curse |
| S2 | Spells are a little direct action: mostly finishing strays the towers let through. | scorecard (bot runs) | see below |
| S3 | Battle Hymn boosts a tower a lot, and the leaders' curses go for the boosted tower. | test; bot runs | ×2 attack rate for 6 s; leaders curse a hymned tower clearly more often than the same tower unhymned |

S2's targets:
- a strong bot casts about two spells a wave;
- spells make ≤ 15% of its kills;
- Smite finishes an ordinary monster at 60% life.

## Verbs, relics and predictability

| ID | Criterion | Judge | Target |
|---|---|---|---|
| V1 | Six verbs, each an event in the player's own engine, counted per wave: charge, corpse, curse taken, overkill, banish, debuff consumed. | test; scorecard (bot runs) | each 3–40 a wave in a build that leans into it |
| V2 | The player sets a verb's frequency through build and placement. | bot A/B | leaning in ≥ 2× the count of a build that does not |
| V3 | Leaning into a verb costs something, and some relic turns that cost into payoff. | content lint | every verb |
| V4 | Each mechanics tower produces or consumes one verb. | content lint | all |
| V5 | Most relics read one verb and write another. | content lint | ≥ 60% |
| V6 | Consuming a debuff can be a verb. | content | debuff consumed is one |
| V7 | Relics add no new rule; some unlock tech the player could not otherwise use; downsides come only with a choice. | content lint | see below |
| V8 | No chance procs: a relic fires on a count or a predictable condition, and its counter is visible. | content lint; test | no relic touches the random stream; every counter in the client state |

V7's targets:
- the pool starts at ≥ 40 relics;
- ≥ 25% of the pool are enablers;
- pacts come only from choices.

## Real estate

| ID | Criterion | Judge | Target |
|---|---|---|---|
| R1 | Good cells are scarce by map design; many cells start occupied (rock, water). | scorecard (maps) | occupied ≥ 40% of the ground beside the halls; ≤ 12 prime cells a map |
| R2 | A cell is worth what it reaches of the routes, and the player sees that worth. | test; protocol | per-cell coverage in the level facts |
| R3 | Upgrading buys less per gold than another tower, but more per cell, against the location's real armor mix. | scorecard (tower tables) | for every attacking kind, rank II and III: marginal damage per gold below rank I's; damage per cell above |
| R4 | Scarcity keeps the tower count low without a cap. | scorecard (bot runs) | see G2.2; no build limit in the rules |
| R5 | The best cells sit together, and area curses punish that. | scorecard (maps; bot runs) | top prime cells within 2 tiles of another; strong bots' landed curses catch ≥ 1.5 towers on average |
| R6 | Blight: one kind per act takes empty cells from later building, visibly before it lands, for a stated time. | test; bot runs | telegraph ≥ 1.5 s; 2 waves; 1–5 blighted cells a location that has it |
| R7 | A changed cell shows its change and how long it lasts. | test; protocol | the state carries each cell's status and waves left |

## Tuning and judging

| ID | Criterion | Judge | Target |
|---|---|---|---|
| T1 | Every gameplay number lives in the tuning data, with a comment. An override file swaps any of them for a run of the tools. | test | `hellward/sim/data/*.toml`; `HELLWARD_TUNING`, seen by worker processes |
| T2 | Bots play whole runs through a person's hands, using every system, so the targets above can be measured. | tests; scorecard | see below |
| T3 | One command reports every measurable criterion. | `tools/scorecard.py` | prints each ID with its number and met or missed |
| T4 | Planner decisions stay cheap as rules grow. | `tools/sim_bench.py` | p95 decision time no worse than before each stage |

T2's targets:
- a middling bot and a strong bot;
- the strong bot has a tree policy that reads its relics;
- a Kit corpus feeds the per-location tools.
