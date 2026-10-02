# Hellward — design choices

[game-design.md](../game-design.md) sets the direction; this document fills in what it leaves open, as concrete
choices. [design-criteria.md](design-criteria.md) is how each will be judged once built.

**How this was reached.** A first draft (2026-10-01) was critiqued by four reviewers (player experience, systems and
economy, fidelity to game-design.md, feasibility in this codebase). Ilya then settled eight forks on 2026-10-02:
a run is the whole campaign; sanctuary life is a run-wide pool; chant interrupts go with Cleanse; next-level attacks
come both as charges and as separate towers; relics drop without choice plus a merchant; build variety comes from
relics, with reskill points to unlearn slowly; elements are protected or vulnerable by 25% before armor; Skip is
offered after the player commits to the wave. Choices marked *(Ilya)* are his.

Today's game, for reference ([campaign.md](campaign.md), [design.md](design.md)): twelve locations in two acts as a
persistent campaign; sigils by lives kept buy a free-respec tree; seven tower families in three ranks; four curses
chosen by a planner that simulates the fight; Cleanse, Smite, Frozen Orb, Meteor on mana; gates in arches; salvage,
breaches, trophies, patterns. Life starts at 6.

## 1. A run *(Ilya)*

- A **run** walks all twelve locations in order, about an hour. Locations shorten to about five waves.
- It starts with one random relic. Between locations is a **camp**: spend skill and reskill points, take the
  location's relic drop, visit the merchant.
- **Carried within a run:** sanctuary life, hero level and XP, skill and reskill points, learned skills, relics,
  gold.
- **Kept across runs:** the meta currency and its purchases, story pages seen, best results.
- One save, overwritten at every camp and at every wave's start: a lost bonus wave cannot be reloaded.
- Everything a defence starts from is one immutable **Kit** (skills, relics and their counters, bought modes, tower
  dials, gold, life, patterns, seed). A replay is a Kit plus the order log; the run layer lives outside `sim/`.

## 2. Sanctuary life: one pool for the run *(Ilya)*

- 30 life for the whole run. A leak costs the monster's lives; at 0 the run ends.
- A camp restores **half the missing life**. That is a comeback, and leaking at full life is never free.
- **Lives sigils** at each location count lives lost there: none lost gives 3, two or fewer 2, five or fewer 1.
- A leak during a bonus wave costs pool life but not the location's lives sigils. The pool is greed's price.

## 3. Gold

- **Prices do not grow with depth:** a rank-I Arrow costs 12 everywhere.
- **Income grows** about ×1.12 per location (and per wave within one). That closes the power budget against monster
  life (section 4). The scorecard prints a per-location power table: the last wave's life on the field per second
  against a reference board's damage per second.
- **Location end:** gold carries in full. Towers are dismantled and refund the same share as selling one, 50%.
- **Rubber band:** each location starts with at least a floor of gold. It never helps the rich.
- **Sinks for riches:** the merchant's relic (rising prices), clearing rock (rising prices, a few cells per map), and
  bonus-wave stakes. No interest.

## 4. Numbers

- **Life:** a role-1 monster (the Fallen) has 10 life at Tristram's first wave. Life grows ×1.16 per location and
  ×1.05 per wave.
  - Role factors are compressed so that ordinary monsters at the Temple sit around 60–120, none above 200.
  - Bosses: Azazel ~400, the Bone Priest ~800.
- **Hits are whole numbers:** Arrow 2/3/4, the Ballista 7/10/14, elemental towers 3–6. No hit above 30 with every
  bonus a run can stack.
- **"Faster, smarter" late monsters** come from new kinds and rosters, not a global speed factor.
- **Counts:** at most 30 monsters a wave, at most 25 alive at once.

## 5. Damage *(elements: Ilya)*

A hit resolves in four steps:

1. Its **element**: a monster *protected* against it takes ×0.75; one *vulnerable* takes ×1.25.
2. Round to a whole number.
3. Subtract **armor**.
4. The hit does at least 1.

- Each kind carries at most two element tags.
- **Bypasses:** damage over time (poison, burning floor) ignores armor. Holy damage (Smite) ignores armor and
  element.
- **Armor** starts at the Catacombs (an Overlord has 2). Act II brings Zealots at 2, Hulks at 3; Azazel has 2, the
  Bone Priest 3.

The upgrade rule (section 9) is judged against each location's real armor mix.

## 6. The shrine and bosses

A monster that reaches the end of its route **strikes the shrine** and costs its lives.

- An **ordinary monster** is obliterated: a strike, a holy flash, then gone.
- A **boss** (Azazel, the Bone Priest) is **sent back to its portal** with the life it has. Its strikes cost 5, then
  8, then 12, and a counter on the boss shows how many it has made.

## 7. Global spells *(Ilya)*

No Cleanse, and no spell breaks a chant: the resolute leader goes.

| Spell | Effect |
|---|---|
| Smite | Holy damage to one monster: about 60% of an ordinary monster's life here, so it finishes a stray. Known from the start. |
| Frozen Orb | Holds a small knot of walkers for 2.5 s. |
| Meteor | Fire on a spot, then burning floor. |
| Battle Hymn | One tower attacks twice as fast for 6 s. The leaders' planner sees the stronger tower, so the boost is fragile. |

Mana is tuned for about one cast a wave. Spells other than Smite are learned in the Sorcery column.

## 8. Curses and leaders

- Leaders and the four curses stay, at 8 s.
- With no dispel and no interrupt, the answers are spacing, killing the leader (a free **Leaders** targeting mode),
  and the Effigy.

## 9. Real estate

- **Terrain:**
  - *Rock:* no building. A few cells per map can be cleared for gold, at rising prices.
  - *Water:* only a Moon Well.
  - At least 40% of the ground beside the halls starts occupied.
- **Prime cells** are few (≤ 12 a map) and sit together near chokes, so area curses threaten them.
- **Cell worth** shows while placing: how much of each route a tower there would reach.
- **Blight** is the one way monsters take cells. One kind per act blights the best empty cell near it after a
  1.5 s telegraph, and the cell stays unbuildable for 2 waves, its countdown shown on it.
  - Act I: the Bone Acolyte, on a fixed timer, not chosen by the planner.
  - Act II: the Spider.
  - Only empty cells are blighted, so building early protects a prime cell.
- **Upgrades:** ranks II and III buy less damage per gold than another rank-I tower, but more per cell.

## 10. Towers *(Ilya: both charges and separate towers)*

**Base attack towers (six).** Each can learn a charged ability in the tree:

| Tower | Role | Charged ability |
|---|---|---|
| Arrow | light, fast, physical; known from the start | Volley: three targets |
| Ballista | heavy, slow, physical: the armor answer | Piercing Bolt |
| Pyre | fire | Fireball (splash) |
| Frost Shrine | weak cold hits that chill | Frost Nova (the nova attack) |
| Storm Obelisk | lightning | Chain Lightning (the chain attack) |
| Plague Totem | poison over time | Plague Cloud (a poisoned floor) |

**Great towers (two).** Expensive in skill points and gold, and each does one big thing:

- **Firewall Pillar:** lays a burning wall across the hall it watches, every 10 s.
- **Tempest Spire:** strikes everything in reach every 6 s.

**Mechanics towers (six).**
- None deals direct damage; each produces or consumes one verb (section 12).
- Each has a single rank and costs 3–4 skill points; its real price is the cell it occupies.

| Mechanics | Verb | What it does |
|---|---|---|
| Moon Well (water only) | charge | gives a charge to the neighbour with fewest, every 8 s |
| Druid Grove | corpse | each corpse in reach feeds it: +1 hit damage to towers in its aura per stack (max 3), stacks fade |
| Effigy | curse taken | cursed like any tower in the circle; each curse it takes gives a neighbour a charge |
| Soul Jar | overkill | overkill from towers within 2 tiles fills it; full, it pays gold |
| Tolling Bell | banish | every 12 s sends the foremost walker in reach 3 tiles back; that monster comes on 25% faster for 4 s |
| Bone Altar | debuff | amplified monsters take +1 (rank I) or +2 per hit for 2 s; an amplified death consumes the debuff |

Fourteen kinds, six of them mechanics towers.

## 11. Charges and tower AI modes

**Charges.**
- An attack tower with its charged ability holds up to **3 charges** and gains one every 15 s.
- The charged attack has its own **cooldown** of at least 4 s, so extra charges bank rather than speed it up.
- Every verb loop must gain less than 1 at reference rates; a content lint checks it.

**AI dials.** Each tower has two, and a new tower takes its kind's last setting:

| Dial | Free | Bought in the meta shop |
|---|---|---|
| Target | First, Leaders | Strongest, Finisher |
| Charges | Eager | Packs (≥ 3 in the area), Foresight |

- **Foresight** holds a charge unless the target would survive the towers further down its path. It is the cheapest
  to buy.
- A "holding" glyph shows when a tower is holding a charge, and the chronicle says when a held charge was followed by
  a leak.

## 12. Verbs

Six verbs, each a counted event resolved in one relic phase per step, in relic order, with no re-triggering within a
step:

- **Charge:** a tower spends a charge. Relics may name gaining or wasting one instead.
- **Corpse:** a death on walkable floor. The body lies 6 s and is eaten by the Grove, Corpse Explosion, or a Fetish
  Shaman's raising.
- **Curse taken:** a curse lands on a tower.
- **Overkill:** a killing hit's whole damage beyond the life left.
- **Banish:** a monster moved back along its route (the Bell, relics, a boss's return).
- **Debuff consumed:** an amplified, chilled or poisoned monster dies.

## 13. Relics *(Ilya: drops plus a merchant)*

**What a relic is.**
- Data: a trigger (a verb with a count or a predictable condition), an effect from a fixed list (gold, mana, a
  charge, holy damage at the spot, a corpse, a stat change on a tower kind), and often a downside.
- No relic adds a rule or uses chance. Counters show on the towers.

**Where relics come from.**
- One at the run's start and one after each location, drawn from the pool with no choice.
- A boss offers 1 of 2.
- A stake-3 bonus wave gives one, at most once per act.
- The camp **merchant** sells one relic, at prices that rise with each purchase.
- A run gathers about 12–15.

**The pool.** 30 at first, growing to 50 or more. It holds:
- **converters** (verb → verb);
- **counters** ("every 10th Arrow attack deals double");
- **enablers** (use a kind you have not learned, or a charged ability without its skill);
- **pacts** (strong, with a downside).

The relics a run happens to draw push it toward a build: that is the run's variety.

## 14. Levels, sigils and the tree *(Ilya: reskill points)*

**XP and levels.**
- XP comes from kills and wave clears.
- Level-ups come often: the first in Tristram's second wave, about forty by the Temple.
- Each level gives 1 **skill point**, and every third level 1 **reskill point**.
- A level-up is an event the client celebrates.

**Sigils.**
- Each location gives up to 3 for lives (section 2) and 3 for its **goals**, each worth 1 skill point.
- Goals are drawn from a pool of goal types about *how* it was won: kill every Witch before she curses, let no Fallen
  through, hold with ≤ 6 towers, skip two waves, never let the gate fall.

**Totals.** A perfect run earns about 40 levels plus 72 sigils, roughly 110 points; a good one about 80.

**The tree.**
- It stays open. Each tower kind has a column:
  - base attack kinds: unlock 4 (Arrow free), rank II 3, rank III 4, charged ability 5, capstone 6;
  - great towers: unlock 10, then ranks;
  - mechanics towers: unlock 3–4.
- Sorcery and Warding columns cover the spells and the gates.
- The whole tree costs about 300.
- No respec. A **reskill point** unlearns one skill from the bottom of its column and refunds its points, so a
  player slowly leaves what their relics did not favour.

## 15. The meta shop

**Salvage** is the meta currency: a few drops per location, more for goals and bonus waves, kept win or lose. The
shop sells:
- tower AI settings;
- **patterns:** side-grades for a tower kind, one equipped per kind at a run's start;
- relics added to the pool.

Everything costs about twenty runs' median income. Breach trophies become relics.

## 16. Skip *(Ilya: after commit)*

**Prediction.** It runs in a dedicated predictor process, never in the leaders' worker pool. It plays the coming wave
from the current state, with no player input and the real leaders.

**Timing.** It starts quietly once the player has been idle for 1 s during the break, and the newest request wins.
Its result shows only when the player **calls the wave**:
- If the wave is predicted clean (no life lost) and the prediction is ready, the player chooses **Skip**, with a
  10% gold bonus and the vision, or **Fight**.
- If the prediction is not ready, the wave simply starts.

**Applying it.** Skipping adopts the predicted world, so every counter carries over.

**The vision.** The level dims to the dark god's red, and the wave's deaths play fast at their places, for 3–6 s.
A click ends it.

**Limits.** Bonus waves are never predicted or skipped. There is no "skip all".

## 17. Bonus waves

**How.** At a wave break the player may summon a bonus wave at stake 1, 2 or 3. It is sized and priced by the
location, not the current wave, and summoning earlier pays a premium.

**Rewards** differ in kind by stake:

| Stake | Reward |
|---:|---|
| 1 | gold |
| 2 | more gold and salvage |
| 3 | a relic (at most once per act) and much gold |

**Risk.** There is no hard cap, but each further bonus wave at a location grows its pack. Leaks cost pool life, and
the wave can never be skipped. The current breaches become authored bonus waves.

## 18. Smarter monsters

- In Act II, each pack chooses its route when the wave is called, by the least tower coverage without curses. Banners
  at the forks show the choice during the break.
- Flayers sprint when hit.

## 19. Difficulty

One difficulty, hard. Later, an ascension ladder for players who win.

## 20. Order of building

0. **Guards:**
   - the Kit;
   - clone-fidelity scenarios for every new field;
   - a p95 planner-decision gate (`sim_bench`);
   - the scorecard's static checks.
1. **Rules pass:**
   - numbers and the damage model;
   - armor and the Ballista;
   - the shrine and the boss's return;
   - spells (no Cleanse, no interrupts, Battle Hymn).

   Bots and plans are updated to match.
2. **Skip,** on the current campaign.
3. **A thin Act I run:**
   - run life, carried gold, XP and levels, lives sigils;
   - a camp with relic drops: about eight counter relics on overkill and banish;
   - the Tolling Bell and the Soul Jar.

   It is playable in the Godot client and shown to Ilya before more content.
4. **Charges, AI modes, the meta shop.**
5. **The remaining verbs,** one at a time, each with its tower and three relics.
6. **Then:**
   - the tree rewrite with reskill points;
   - goals;
   - bonus waves;
   - the merchant;
   - the great towers.
7. **Last:**
   - terrain on every map;
   - blight;
   - Act II's routes and kinds;
   - the final tuning.
