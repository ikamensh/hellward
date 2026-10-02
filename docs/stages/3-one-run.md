# Stage 3 — One run

The third readiness stage ([design-choices.md](../design-choices.md) sections 1–3, 14, 17, 20): the campaign becomes a
**run** through all twelve locations, with Diablo's XP bar, sigils for how a location was won, an open tree paid in
skill points, reskill points, a run-wide sanctuary, carried gold and bonus waves the player wagers on. Relics are stage
4's; the full meta shop is stage 5's, and until then the existing Forge is salvage's shop. It ships as a release Ilya
plays, after stage 2. One critique round (systems, feasibility, player experience, fidelity) is folded in.

## The run (D1, Ilya)

**The run layer** (`hellward/run/`) is pure rules with no I/O. `sim/` stays one defence.

**`Run`** is a frozen dataclass. It holds:
- the seed and the next location's index;
- the life pool;
- gold;
- XP and level;
- unspent skill and reskill points, and the learned skills;
- per location: its sigils and the goals it drew;
- salvage earned;
- the equipped patterns;
- a carried counters slot for stage 4.

**Carried and kept:**
- **Carried** from location to location: everything in `Run`.
- **Kept across runs** (the profile): story pages seen, every location ever held, banked salvage, forged patterns,
  and runs won and lost.

**Saving.** One save per profile: the Run, the current defence's Kit, and its **log**.
- The log holds every accepted order, every leader's decision, and a step mark at least once a second.
- A resume replays the Kit and the log through a planner that returns the logged decisions: no live planner, fast,
  independent of the compiled build. It then steps on to the last mark, so quitting never rewinds more than a second.
- The save is written at every camp and at every wave's start.

**Losing and leaving.**
- A loss (the pool reaches 0) ends the run, and the profile keeps the salvage the run earned.
- A run can be abandoned at a camp, keeping its salvage.
- **The run summary** is a post-mortem:
  - the life pool across the run, by location and wave;
  - the kinds that leaked most;
  - the goals missed;
  - the build;
  - a comparison with the profile's best run.

## Sanctuary life (Ilya: one pool)

- 30 at the start (`run.life`). A leak costs the monster's lives.
- A camp restores half the missing life (`run.camp_heal`), shown as its own moment.
- The briefing shows the location's worst case against the pool (its roster's lives, and a boss's strikes at 5).
- A boss shows "N more strikes end the run".

## Gold

- **Start gold** at a location is the gold carried in, topped up to a floor (`run.gold_floor`, about 0.8 of stage 2's
  stipend). The stipend itself goes.
- **At a location's end** every tower is dismantled for `run.dismantle_refund` (about 0.3, apart from the sell rate).
  It is tuned so the middling bot carries about stage 2's stipend into each location.
- **The per-location tools** (`balance.py`, `margin.py`) take their Kits from the middling bot's run corpus.

## XP and levels (M2; Ilya: "level up jolly")

**Earning XP.**
- The simulation counts XP: a kill gives its monster's life ÷ `run.xp_life`, and a cleared wave gives
  `run.xp_clear × its number`.
- The Kit carries the current XP and the XP to the next level, so the World knows the curve.

**A level-up** (`level_up`, the new level) refills the mana orb, as a Diablo level-up refills mana.
- The base mana is lowered to match, and the predictor sees it, since it is deterministic.
- The HUD shows "N points for the camp".
- A short beat plays each time. The full celebration every fifth level plays at the wave's end, never over a live
  field.

**The curve** (`run.xp_curve`): the first level-up comes in Tristram's second wave, then about one level per wave,
reaching about 55 by the Temple. The XP bar is the larger source of points.

**Points:** each level gives 1 skill point, and every fourth level 1 reskill point.

## Sigils and goals (M3)

**Lives sigils** count lives lost at the location: none lost gives 3, two or fewer give 2, five or fewer give 1.

**Goal sigils.** Each location has a list of eligible goal types with its parameters, and a run draws three of them
by its seed, so repeated runs differ. They show at the camp before points are spent, so they can steer the tree.

**Goals are judged over the whole defence**, as a fold over events (`start`, `observe`, `verdict`) that the bots'
record and the server share:
- each is a live state (open, met or failed), sent as `goal` events;
- the client warns before an order that would fail one;
- bonus-wave monsters count only toward the bonus goal.

**First goal types:**

| Goal | Met when |
|---|---|
| A lean defence | at most N towers stand at any moment |
| The gate holds | a gate is built by wave 2 and never falls |
| One family | every tower built is of the named element, or none is physical |
| The leaders die first | every leader of the named kind dies before its first curse lands |
| A fragile hymn | Battle Hymn is cast N times without the hymned tower being cursed during it |
| The bonus | a bonus wave is cleared at stake 2 or more |

Each goal's N is set from the run bots' measured distributions.

Each sigil is worth 1 skill point.

## The tree (Ilya: open tree, reskill points)

**Columns:**
- one per tower kind;
- Sorcery (Hymn, Frozen Orb and Meteor cost points; Smite is free);
- Warding (gates; the first arch is free).

**Tower kinds are unlocked here.** The Arrow is free; every other kind costs points to unlock, then its ranks.
- Each physical kind has **its own rank nodes**. The shared Steel ranks go, so physical kinds are no cheap shortcut.
- A location's arsenal becomes what it *could* hold; `Kit.arsenal` is that intersected with what is unlocked.
- `first_location` keeps the early locations readable.

**Prices,** first guesses in `skills.toml`:

| Node | Points |
|---|---:|
| Unlock an elemental kind | 4 |
| Unlock a physical kind (Ballista, Hook, Knife) | 5 |
| Rank II | 3 |
| Rank III | 4 |
| Today's specials (Fire Ball, Blaze, Static Field, Chain Lightning, Glacial Spike, Shatter, Lower Resist, Contagion, Life Tap, Corpse Explosion, Hurricane, Twister) | 4–6 |
| Sorcery: Hymn | 3 |
| Sorcery: Frozen Orb | 4 |
| Sorcery: Meteor | 5 |
| Sorcery: mana | 3 per step |
| Warding (Holy Shield, Thorns) | 3–4 |

**Unlearning.** A reskill point unlearns the bottom skill of a column and refunds its points. Nothing else unlearns.

**The stage-3 target:** a good run (about 80 points) opens at most about 60% of the tree, and the strong bot opens at
most half of the ten kinds past rank I by the Temple. M4's 2.5× arrives with stage 5's nodes.

## Bonus waves (G3.3; Ilya: "fabulously rich, even if very hard")

**The stake is a wager on a harder pack.**

| Stake | The pack | Wager |
|---:|---|---:|
| 1 | the location's middle-wave pack | 1 income unit |
| 2 | ×1.5 life, plus an elite | 2 income units |
| 3 | the last wave's pack ×1.5, with a leader | 3 income units |

- **The payout** is paid only if no monster of the pack leaks: the wager back plus a profit that grows faster than the
  stake (`bonus.profit`, about ×2, ×5, ×10 the wager's unit). The XP scales the same way.
- **Bonus kills** pay no ordinary bounty and give no clear XP.
- **Repeats:** each further bonus wave at a location pays and gives XP at ×0.6 of the one before.

**When.**
- From wave 2's break on, through `summon(stake)`.
- Each stake's exact pack is drawn from the run's seed when the break opens, and the panel previews it: its kinds,
  counts, the lives at stake against the pool, and the reward.
- The break clock stops while a bonus pack lives, and no regular wave can be called until it is cleared.
- Bonus waves are never predicted or skipped; the Skip predictor refuses during one.

Today's breaches become authored stake-2 bonus waves at their locations, and their trophies stay forge inputs.

## The forge, until stage 5

The Forge stays: salvage forges patterns, and patterns equip at a run's start. The 0.2 save upgrade keeps every
held location (the story's `due()` needs them), the banked salvage and the patterns, and drops sigils and skills.

## The client

**The run map** labels every location with its threats: armor, flyers, protections, curses, a boss.

**The camp:**
- the run's state;
- the tree;
- the next location's briefing, with its goals and an **answers** line computed from the hits table and the kinds
  learned (for example "Overlords, armor 2: your Arrows deal 1. Answers: Ballista, Storm (vulnerable).");
- on a profile's first run, a mark on what the middling bot's policy would learn next;
- Continue, and Abandon.

**In the fight:**
- the goals tracker;
- the bonus-wave panel with its preview;
- level-up beats.

**Location lessons** are rewritten about threats, not tower kinds.

## Run bots (T2)

**Tree policies are authored, not searched:**
- **The middling bot** uses the warden's skill priority, filtered by the next location's threats (armor, flyers).
- **The strong bot** follows one of at most four authored archetype orders, chosen by a 10-seed comparison.

**Defence:** the warden drafting from the Kit, which works for any unlock set. The planned player is used only where a
plan exists for the Kit (plans carry the unlocked set in their fingerprint).

**Bonus policy:** a rule on what a person sees (no leak last wave, pool at least X, stake by margin felt). Any oracle
lives in `hellward/run/`, never `players/`.

**`tools/runs.py`** caches defences by (Kit, policy, seed) and has two modes:
- **`--immortal`:** the pool cannot end the run, but lost life is counted. This measures G3.2, G3.3, M2 and M3 over
  every location.
- **Real runs** on 30 paired seeds for G3.1. "Fewer" is measured as locations reached and pool left, not as wins.

It writes each bot's Kit at each location as the **corpus**, and the life factors are re-fit on it with `margin.py`.

## Names both sides build against

| Thing | Name |
|---|---|
| the run | `hellward.run.Run`, `start(seed) -> Run`, `kit(run) -> Kit`, `finish(run, world) -> Run`, `learn(run, key)`, `unlearn(run, key)` |
| goals | `hellward.run.goals`: `Goal` (`start(kit)`, `observe(event)`, `verdict() -> "open" \| "met" \| "failed"`) |
| Kit additions | `arsenal`, `xp`, `xp_next`, `patterns` |
| the World | `World.xp`; `World.summon(stake)`; `World.bonus` (the live pack, or None) |
| events | `("level_up", level)`, `("goal", key, state)`, `("bonus", stake, state)` with state summoned, cleared or failed |
| wire requests | `run`, `start_run`, `abandon`, `camp`, `learn`, `unlearn`, `briefing`, `defend`, `summon` |
| tuning | `run.toml` (life, camp_heal, gold_floor, dismantle_refund, xp_life, xp_clear, xp_curve, reskill_every), `bonus.toml` (stakes, profit, repeat, early) |

## Order of work

0. **Stage 2 merged.**
1. **One mechanical commit, behaviour-free:**
   - `Kit.arsenal`, read as `world.arsenal` everywhere;
   - `Player.skills` deleted, so `defend(kit, player, ...)` takes the Kit's skills;
   - the per-location tools take Kits from a reference table that reproduces today's convention;
   - plan fingerprints include the unlocked set.
2. **In parallel, file-disjoint:**
   - **the simulation:** XP, the level-up's mana, bonus waves;
   - **the tree's content:** `skills.py`, `skills.toml`;
   - **the run layer** and goals;
   - **the server and saves;**
   - **the client;**
   - **the run bots** and `runs.py`.
3. **The corpus,** then the factors re-fit, then the 30-seed scorecard. The Skip branch, whichever lands second,
   rebases and refuses predicting bonus waves.

## Exit criteria

**Scorecard:**
- **G3.1:** on 30 paired real runs, the middling bot ≤ 30% won, the strongest ≥ 70%.
- **G3.2:** by each act's end, ≥ 3× gold and ≥ +3 levels, in immortal mode.
- **G3.3:**
  - stake 3 is net-positive for the strong bot;
  - it costs the middling bot locations reached;
  - the strong bot summons ≤ 3 a location.
- **M2:** the first level-up in Tristram's second wave; about 55 levels by the Temple.
- **M3:** each goal met by the strong bot in 30–80% of the runs it pursues it.
- **The tree:** a good run opens ≤ 60%.
- **The losses spread:** no location ends more than half of the lost runs.
- **Length:** a run takes 45–75 minutes at a person's pace.

**Tests:**
- a save's resume replaying the log exactly, mid-wave included;
- the Kit chain;
- level-ups refilling mana;
- goals as folds, including the warnings;
- bonus-wave pricing, preview and pause;
- the server and client through a two-location run.

**Ilya plays** a run in the client.
