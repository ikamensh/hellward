# Hellward — mechanics ideas

Brainstorm toward the principles in [game-design.md](../game-design.md): verbs, counter relics and real estate.
Nothing here is decided. Drop an idea that fails a principle; move a decision into the game's docs once it is built.

## Five candidate verbs

| Slay the Spire | Hellward verb | Mechanics structure | Cost of leaning in |
|---|---|---|---|
| Discard + exhaust | **Corpse**: a death leaves a body on the path for ~8 s; things consume it | Ossuary: eats corpses in reach, each one fuels it | Kill zones pinned to where it stands; Fetish Shamans raise from the same bodies |
| Draw / hand | **Charge**: up to 3 charges, one back every ~15 s | Moon Well: gives a charge to the neighbour with the fewest | A well doesn't shoot |
| Status cards (Wound, Dazed) | **Curse taken**: a leader's curse lands on a tower | Effigy: curses landing near it go to it instead | Leaders learn it and curse elsewhere |
| Wasted block | **Overkill**: damage beyond the life a monster has left | None needed; every heavy hitter makes it | Heavy hitters are poor against swarms |
| Card back on the draw pile | **Banish**: a monster thrown back to its entrance | Tolling Bell: sends back the first walker to reach it each wave | Longer wave, no kill gold yet, and it returns |

**Corpses.** The simulation already has four effects that fire the instant a monster dies: Shatter, Corpse
Explosion, Contagion and the Fetish Shaman's raising (`hellward/sim/model.py`, `_died`). A body that stays on the
floor for a few seconds turns them into one pile both sides draw from. Where a monster dies starts to matter, and
tower placement decides that.

**Charges.** Spending a charge is playing a card; recharging is drawing; a recharge at full is a wasted draw. The AI
modes for sale decide when to spend and when to hold. Relics that reward holding, and others that reward spending,
make the mode a build choice rather than a plain upgrade.

**Curses taken.** Slay the Spire's Evolve and Fire Breathing turn the enemy's junk into fuel. Here: a Martyr's Candle
that answers a curse landing on it with a bolt at the caster, or an Effigy as a lightning rod. The rollouts price
them with no new planner code, so leaders may curse around them; that is a side effect, not a goal (Ilya dropped
"prefer verbs that change what leaders decide" on 2026-10-01). With Cleanse gone, a curse taken is a cost the player
plans for rather than clicks away, which makes it a better verb.

**Overkill.** Readable only because the numbers stay small: a hit of 4 into 1 life left shows 3 wasted. Absolute
armor pushes toward heavy hitters, heavy hitters overkill small monsters, and an overkill relic makes that build hold
against swarms.

**Banish.** The boss rule (a boss that reaches the shrine goes back to the portal) already teaches "sent back".

## Converter relics

Each reads one verb and writes another:

- **Bone Battery:** a consumed corpse gives the nearest tower a charge.
- **Spite:** a tower whose curse ends gains a charge.
- **Spillway:** overkill passes to the next monster on the path.
- **Siphon:** overkill becomes mana.
- **Martyr's Bell:** when the shrine is struck, every tower gains a charge. Lives decide sigils, so this is Slay the
  Spire's Offering: health for power.
- **Hoarder's Seal:** a tower with full charges gets +1 reach.

Counter relics, shown as pips on the towers they affect:

- Arrow towers deal double damage once every 10 attacks.
- Every third spell costs no mana.

## Global spells

Spells kill one or two strays, or lend a tower a strong, short boost that the leaders' curses will likely go for.

- **Smite:** holy damage to one monster, no resistance; enough to finish a stray at half life.
- **Frozen Orb, Meteor:** stop or burn a small knot that slipped through.
- **Battle Hymn:** one tower strikes twice as fast for 6 s. The planner's rollouts see a tower dealing more damage,
  so the next curse is likely to land on it: a boost is worth most where leaders cannot reach.
- **Consecrate:** a tower ignores armor for 8 s.

## A first set

Corpses, charges and curses taken: three verbs, three structures (Ossuary, Moon Well, Effigy) and about a dozen
converters. Overkill needs no structure and can arrive as relics only. Banish comes with the boss rule.

## Real estate

Today almost all floor is buildable: each map has 5–6 pillars and 0–3 pools (`hellward/sim/campaign.py`). Scarcity
is new map work.

Arrow ranks already cost more per hit than a new tower. In Tristram, rank I gives 2 damage a second for 12 gold;
rank II adds 1.15 for 8 more; rank III adds 1.25 for 12 more (`rank_cost_units` in `hellward/sim/balance.py`). Reach
also grows with rank, which on a prime cell is worth more than the damage.

- **Terrain that hosts structures.** Cells the ordinary towers can't use may suit a mechanics structure: a Moon Well
  on water, an Ossuary over an open grave. Occupied ground then shapes which engines a map favours.
- **Clearing.** Rock can be cleared for gold, or over a wave break, to open a cell.
- **Monsters taking cells.**
  - A spider webs a cell next to its hall; fire burns the web away.
  - A dying hulk leaves rubble on the cells beside it, cleared at the next break.
  - The Drowned flood a cell beside a canal for a few waves.
  - A leader desecrates an empty cell.
- **Who chooses the blocked cell.** A leader's rollout covers a curse and a short aftermath, too short to value
  denying a cell to a tower not yet built. Blocking needs either authored rules (which cells, when) or a
  longer-horizon value for the planner.
- **Showing a cell's worth.** While placing, show how much of each route the tower would reach. The reach intervals
  along `s` already exist in `hellward/sim/level.py`.
