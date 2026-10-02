# Stage 3 — One run

The third readiness stage ([design-choices.md](../design-choices.md) sections 1–3, 14, 17, 20): the campaign becomes a
**run** through all twelve locations, with Diablo's XP bar, sigils for how a location was won, an open tree paid in
skill points, reskill points, a run-wide sanctuary, carried gold and player-controlled bonus waves. Relics are stage
4's; the meta shop is stage 5's. It ships as a release Ilya plays, after stage 2.

## The run (D1, Ilya)

**The run layer** is pure rules with no I/O, in `hellward/run/` (outside `sim/`, which stays one defence):

| Function | What it does |
|---|---|
| `Run` | a frozen dataclass of the run's state |
| `start(seed)` | begins a run |
| `kit(run)` | the next defence's Kit |
| `finish(run, world)` | folds a decided defence into the run: XP, levels, sigils, gold, life and salvage |
| `learn`, `unlearn` | spend skill or reskill points |
| `summon(world, stake)` | delegates to the simulation's bonus wave |

**What `Run` holds:**
- the seed, and the index of the next location;
- the sanctuary life pool, and gold;
- XP, level, and unspent skill and reskill points;
- the learned skills;
- sigils per location, salvage banked this run;
- the carried counters slot (empty until stage 4's relics);
- the story pages due.

**Carried and kept:**
- **Carried** from location to location: everything in `Run`.
- **Kept across runs** (the profile): story pages seen, best results, salvage (spent in stage 5), and runs won and
  lost.

**One save per profile:**
- the Run, plus the current defence's Kit, order log and pickled World tagged with the compiled build's key;
- overwritten at every camp and at every wave's start;
- quitting mid-wave resumes where the order log ends; a stale key replays the log instead.

**A loss** (the pool reaches 0) ends the run.
- The profile keeps the salvage the run earned; the run's own save is removed.
- The run summary shows how far it got.

## Sanctuary life (Ilya: one pool)

- 30 at the run's start (`run.life`).
- A leak costs the monster's lives from the pool.
- A camp restores half the missing life (`run.camp_heal = 0.5`).
- A leak during a bonus wave costs pool life but not the location's lives sigils.

## Gold

- Gold carries in full.
- At a location's end every tower is dismantled for the sell refund (one rate for both, `battle.sell_refund = 0.5`).
- A floor (`run.gold_floor`, in income units) tops up the gold carried out of a location, before anything is spent
  at the camp.

## XP and levels (M2)

**Earning XP.**
- A kill gives XP equal to the monster's life ÷ `run.xp_life`; a cleared wave gives `run.xp_clear` × its number.
- The simulation counts XP in the World (`World.xp`), so scripted players and the server see it alike.
- The run layer turns it into levels.

**The curve.**
- `run.xp_curve` sets XP to the next level.
- Tuned so the first level-up comes in Tristram's second wave, about four levels come per early location, and about
  forty arrive by the Temple.

**A level-up mid-defence** is an event (`level_up`, the new level).
- The client celebrates it: a short beat each time, the full celebration every fifth level.
- Its points are spent at the camp, since perks are baked when a defence begins.

**Points.** Each level gives 1 skill point, and every third level 1 reskill point.

## Sigils and goals (M3)

**Lives sigils** count lives lost at the location: none lost gives 3, two or fewer give 2, five or fewer give 1.

**Goal sigils** (3 per location):
- Each location names three goals from a shared pool of goal types, with its own parameters.
- A goal is a predicate over the decided World and its record (`hellward/run/goals.py`), checked at the location's
  end.
- The client shows the location's goals at the briefing and ticks them off live where it can.
- First goal types:
  - **let none through:** no monster of the named kind reaches the shrine;
  - **the leaders die first:** every leader of the named kind dies before its first curse lands;
  - **a lean defence:** at most N towers stand at the end;
  - **the gate holds:** a built gate never falls;
  - **no spells:** none cast;
  - **one family:** every tower is of one element;
  - **the bonus:** at least one bonus wave summoned and cleared.

Each sigil is worth 1 skill point.

## The tree (M4, Ilya: open tree, reskill points)

- **Columns:** each tower kind and the Sorcery and Warding columns.
- **Tower kinds are unlocked here**, not by a location's arsenal:
  - the Arrow is free;
  - every other kind costs points to unlock, then its ranks (rank II about 3, rank III about 4);
  - the Ballista, Hook and Knife Post unlock in their own columns;
  - Steel's rank skills stay shared by the physical kinds that are unlocked.
- **Spells are unlocked in Sorcery:** Smite is free; Hymn, Frozen Orb and Meteor cost points.
- **Gates** come from Warding; the first arch is free.
- **Arsenals** become a location's *possible* arsenal: what it has room for (gates where it has arches). The player's
  unlocks decide what is used.
- **Not all locations at once:** a skill's `first_location` keeps the early locations readable. At the Graveyard not
  all kinds can be learned yet.
- **Unlearning:** a reskill point unlearns the bottom skill of a column and refunds its points. Nothing else unlearns.
- **The whole tree** costs at least 2.5× a perfect run's points (M4), so a run opens four to six kinds properly.

## Bonus waves (G3.3)

**Summoning.** During a break, `summon(stake)` with a stake of 1, 2 or 3 starts a bonus wave now.

**The pack** is drawn from the location's own roster:
- it is sized by the location, never by the current wave;
- each further bonus wave at the location grows its pack ×1.3 (life and elites past 30 bodies) and pays ×0.6 the one
  before;
- summoning before the location's middle wave pays a premium (`bonus.early_premium`).

**Rewards** by stake, in income units, with salvage capped per location:

| Stake | Reward |
|---|---|
| 1 | gold |
| 2 | more gold and salvage |
| 3 | much gold, more salvage, and from stage 4 a relic |

**Limits.** Bonus waves are never predicted or skipped. The current breaches become authored stake-2 bonus waves at
their locations.

## The camp (client screen)

**Between locations:**
- the run's state: life, gold, level and XP bar, sigils won, skill and reskill points;
- the tree to spend them;
- the next location's briefing with its three goals;
- Continue.

**Story pages** play as today: the first arrival and the first victory, and the act endings.

**The map screen** shows the run's path.

## Run bots (T2)

- **`hellward/sim/players/runner.py`** drives a whole run: a defence policy (an existing scripted player), a tree
  policy (what to learn at each camp, from what it has and the location ahead), and a bonus-wave policy (whether and
  at what stake).
- **The middling bot:** the veteran, with a simple tree policy and no bonus waves beyond stake 1.
- **The strong bot:** the better of the planned and warden players per location, a searched tree policy, and a
  bonus-wave policy that summons while its margin allows.
- **`tools/runs.py`** plays N runs per bot through slot.py and writes per-location tables:
  - life, gold, level and points;
  - sigils, goals met, bonus waves summoned;
  - wins and losses.

  The scorecard reads it for G3.1, G3.2, G3.3, M2 and M3.

## The server and the wire

- **`hellward/server/campaign.py`** and **`progress.py`** are rewritten around the profile and its Run.
  - The 0.2 campaign save upgrades by keeping its story pages and best results. Its sigils, skills and forge state go:
    a run starts fresh.
- **Requests:**
  - `run` (state), `start_run`, `camp`, `learn`, `unlearn`;
  - `briefing` (with goals), `defend` (the next location), `summon`.
- **Events:** `level_up`, `xp`, `goal` (met, failed), `bonus` (summoned, cleared).
- **The client's screens** (`screens/*.gd`) change for the camp, the run on the map, and the goals at the briefing.
  The Godot session is told the files before any edit.

## Exit criteria

**Scorecard (run bots over at least 10 seeds each):**
- G3.1: middling ≤ 30% of runs won, strongest ≥ 70%.
- G3.2: by each act's last location, ≥ 3× gold and ≥ +3 levels.
- G3.3: bonus waves pay ≥ 5× by act end, the strong bot summons ≤ 3 per location, and the middling bot summoning
  every break wins fewer runs.
- M2: the first level-up in Tristram's second wave, ~40 levels.
- M3: every goal met by some bot and missed by another.
- M4: the tree's price.

**Tests:**
- a run's round-trip through its save, mid-wave included;
- the Kit chain (each location's Kit from the run's state);
- level-up events;
- goals as predicates;
- bonus-wave pricing and growth;
- the server and the client through a whole two-location run.

**Ilya plays** a run in the client.
