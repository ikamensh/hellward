# Hellward — design choices

[game-design.md](../game-design.md) sets the direction; this document fills in what it leaves open, as concrete
choices. [design-criteria.md](design-criteria.md) is how each will be judged once built.

**How this was reached.** A first draft (2026-10-01) was critiqued by four reviewers (player experience, systems and
economy, fidelity to game-design.md, feasibility in this codebase). Ilya then settled eight forks on 2026-10-02:
a run is the whole campaign; sanctuary life is a run-wide pool; chant interrupts go with Cleanse; next-level attacks
come both as charges and as separate towers; relics drop without choice plus a merchant; build variety comes from
relics, with reskill points to unlearn slowly; elements are protected or vulnerable by 25% before armor; Skip is
offered after the player commits to the wave. A second round of the same four reviews (v2) found the remaining
problems listed under "Round 2" at the end, folded in here (v3). Choices marked *(Ilya)* are his.

Today's game, for reference ([campaign.md](campaign.md), [design.md](design.md)): twelve locations in two acts as a
persistent campaign; sigils by lives kept buy a free-respec tree; seven tower families in three ranks; four curses
chosen by a planner that simulates the fight; Cleanse, Smite, Frozen Orb, Meteor on mana; gates in arches; salvage,
breaches, trophies, patterns. Life starts at 6.

## 1. A run *(Ilya)*

- A **run** walks all twelve locations in order, about an hour. Locations shorten to four to six waves (about five),
  in the first rules pass, so the bots' searched plans are redone once.
- It starts with one random relic. Between locations is a **camp**: spend skill and reskill points, take the
  location's relic drop, visit the merchant.
- **Carried within a run:** sanctuary life, hero level and XP, skill and reskill points, learned skills, relics,
  gold.
- **Kept across runs:** the meta currency and its purchases, story pages seen, best results.
- One save, overwritten at every camp and at every wave's start: a lost bonus wave cannot be reloaded. A save is the
  Kit, the order log so far and the World, tagged with the compiled build's key; when the key no longer matches, the
  order log is replayed instead. Quitting mid-wave resumes where the log ends.
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
- **Location end:** gold carries in full. Towers are dismantled for a share of their price (about 30%, its own tuning
  value), tuned so a middling player carries about one location's stipend.
- **Rubber band:** gold carried out of a location below a floor is topped up to it, before the merchant, so spending
  at the merchant never earns a top-up. It never helps the rich.
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

1. Multiply its **factors**: the element (a monster *protected* against it takes ×0.75, one *vulnerable* ×1.25), the
   Bone Altar's amplification and the Druid Grove's aura. Their product never exceeds ×2.
2. Round to a whole number: up when the product is above 1, down when below, so a tag always moves a hit by at least
   one (a 2 against a protected monster is 1, against a vulnerable one 3).
3. Subtract **armor**.
4. The hit does at least 1.

The hover on a monster shows the hit each tower would actually deal it.

- Each kind carries at most two element tags.
- **Bypasses:** damage over time (poison, burning floor) ignores armor. Holy damage (Smite) ignores armor and
  element.
- **Armor** starts at the Catacombs (an Overlord has 2). Act II brings Zealots at 2, Hulks at 3; Azazel has 2, the
  Bone Priest 3.

The upgrade rule (section 9) is judged against each location's real armor mix.

## 6. The shrine and bosses

A monster that reaches the end of its route **strikes the shrine** and costs its lives.

- An **ordinary monster** is obliterated: a strike, a holy flash, then gone.
- A **boss** (Azazel, the Bone Priest) is **sent back to its portal** with the life it has, as the design says; each
  strike costs 5 life, and a counter on the boss shows how many it has made.

## 7. Global spells *(Ilya)*

No Cleanse, and no spell breaks a chant: the resolute leader goes.

| Spell | Effect |
|---|---|
| Smite | Holy damage to one monster: about 60% of an ordinary monster's life here, so it finishes a stray. Known from the start. |
| Frozen Orb | Holds a small knot of walkers for 2.5 s. |
| Meteor | Fire on a spot, then burning floor. |
| Battle Hymn | One tower attacks twice as fast for 6 s. The leaders' planner sees the stronger tower, so the boost is fragile. |

Mana is tuned for about two casts a wave, so killing a stray and boosting a tower do not compete. Spells other than
Smite are learned in the Sorcery column.

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
- **Proportions and room** *(Ilya, 2026-10-02)*: a tower's reach must look generous beside its body. Towers and
  monsters may be drawn smaller, and maps may be larger, with more ground to build on, part of it potential ground
  the player unlocks (cleared boulders, opened plots). Scarcity is about the *prime* cells, not the total ground.
  Stage 2 fixes the scale (section 20).

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
| Druid Grove | corpse | each corpse in reach feeds it a stack (max 3, fading): towers in its aura hit ×1.15 per stack |
| Effigy | curse taken | cursed like any tower in the circle; each curse it takes gives a neighbour a charge |
| Soul Jar | overkill | overkill from towers within 2 tiles fills it; full, it pays gold (the fill grows with the location, so its yield keeps pace with income) |
| Tolling Bell | banish | every 12 s sends the foremost walker in reach 3 tiles back; that monster comes on 25% faster for 4 s |
| Bone Altar | debuff | amplified monsters take hits ×1.25 for 2 s; an amplified death consumes the debuff |

Fourteen kinds, six of them mechanics towers.

## 11. Charges and tower AI modes

**Charges.**
- An attack tower with its charged ability holds up to **3 charges** and gains one every 15 s.
- The charged attack has its own **cooldown** of at least 4 s, so extra charges bank rather than speed it up.
- Every verb loop must gain less than 1 at reference rates, gold counted as a node; a content lint checks it.
- Charges and every other clock that decides a fight tick only while a wave runs. A break changes nothing the
  prediction (section 16) depends on except what the player does.

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
  charge, holy damage at the spot, a corpse, a stat change on a tower kind), and sometimes a downside.
- A relic the player did not choose never carries a downside: **pacts** come only from choices (the boss's 1 of 2,
  the merchant, a stake-3 wave).
- No relic adds a rule or uses chance. Counters show on the towers.

**Where relics come from.**
- One at the run's start and one after each location, drawn from the pool with no choice.
- A boss offers 1 of 2.
- A stake-3 bonus wave gives one, at most once per act.
- The camp **merchant** sells one relic, at prices that rise with each purchase.
- A rich run gathers about 18–20.

**The pool.** At least 40 at first, growing to 60 or more through the shop; at least a quarter are enablers, since
relics are the run's variety. Each relic's counter shows on the selected tower and in a relic bar. It holds:
- **placement relics** *(Ilya)*: a bonus for a pattern of towers on the map, checked when the pattern stands
  (for example, an Arrow Tower beside two different magic towers hits ×1.25). They reward where towers stand, and
  they pull against area curses;
- **converters** (verb → verb);
- **counters** ("every 10th Arrow attack deals double");
- **enablers** (use a kind you have not learned, or a charged ability without its skill);
- **pacts** (strong, with a downside).

The relics a run happens to draw push it toward a build: that is the run's variety.

## 14. Levels, sigils and the tree *(Ilya: reskill points)*

**XP and levels.**
- XP comes from kills and wave clears.
- Level-ups come often: the first in Tristram's second wave, then about one a wave, about fifty-five by the Temple.
- Each level gives 1 **skill point**, and every fourth level 1 **reskill point**. A level-up refills the mana orb.
- A level-up is an event the client celebrates: a short beat for most, the full celebration every fifth level.

**Sigils.**
- Each location gives up to 3 for lives (section 2) and 3 for its **goals**, each worth 1 skill point.
- Goals are drawn from a pool of goal types about *how* it was won: kill every Witch before she curses, let no Fallen
  through, hold with ≤ 6 towers, skip two waves, never let the gate fall.

**Totals.** A perfect run earns about 55 levels plus 72 sigils, roughly 125 points; a good one about 80.

**The tree.**
- It stays open. Each tower kind has a column:
  - base attack kinds: unlock 4 (Arrow free), rank II 3, rank III 4, charged ability 5, capstone 6;
  - great towers: unlock 10, then ranks;
  - mechanics towers: unlock 3–4.
- Sorcery (the spells, about 25 points) and Warding (the gates, about 15) are priced like tower columns.
- The whole tree costs at least 2.5 times a perfect run's points (about 280 or more); the physical family's later
  kinds (section 21) add to it. Charged abilities cost about 6 and capstones about 8.
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
- If the prediction is not ready, the call waits up to about 2 s behind the red dimming.
- If the wave is predicted clean (no life lost), the game pauses and the player chooses **Skip**, with a 10% gold
  bonus and the vision, or **Fight**. A wave that starts because its break ran out counts as a call.
- If it is still not ready, the wave simply starts.

**Applying it.** Skipping adopts the predicted world, so every counter carries over, plus the difference in purse
(gold, mana) since the prediction began. Bots and tests predict inline; how often a person's call finds the
prediction ready is measured separately, with a latency model.

**The vision.** The level dims to the dark god's red, and the wave's deaths play fast at their places, for 3–6 s.
A click ends it.

**Limits.** Bonus waves are never predicted or skipped. There is no "skip all".

## 17. Bonus waves

**How.** From wave 2's break the player may summon a bonus wave at stake 1, 2 or 3. The stake is a **wager**: it
costs gold and brings a harder pack (stake 1: the location's middle-wave pack; stake 2: ×1.5 life and an elite;
stake 3: the last wave's pack ×1.5 with a leader), previewed exactly before the summon. The payout (the wager back
plus a profit growing faster than the stake) comes only if none of the pack leaks. The break clock stops while it
lives; its kills pay no bounty.

**Rewards** differ in kind by stake:

| Stake | Reward |
|---:|---|
| 1 | gold |
| 2 | more gold and salvage |
| 3 | a relic (at most once per act) and much gold |

**Risk.** There is no hard cap, but each further bonus wave at a location pays about ×0.6 the one before while its
pack grows about ×1.3, so the natural stop is two or three. Past 30 bodies a pack grows in life and elites, not
bodies. Salvage from bonus waves is capped per location. Leaks cost pool life, and the wave can never be skipped. The
current breaches become authored bonus waves.

## 18. Smarter monsters

- In Act II, each pack chooses its route by the least tower coverage without curses. Banners at the forks show the
  choice during the break and update as the player builds; calling the wave fixes it.
- Flayers sprint when hit.

## 19. Difficulty

One difficulty, hard. Later, an ascension ladder for players who win.

## 20. Readiness stages *(Ilya: ship in stages; Skip in parallel)*

Each stage ends in a release Ilya plays in the Godot client, with the suite and the client tests green. Before a
stage is built, its own short spec (`docs/stages/N-name.md`) fixes its rules, events and exit criteria; what Ilya
says after playing may reorder what follows. Skip is a parallel track: it is a reusable system but not needed for
the game to be playable, so it joins whichever release is current when it is ready.

| Stage | Delivers | Exit, in short |
|---|---|---|
| 1. Armor and the pirate arsenal | the damage model (whole hits, protected/vulnerable, armor), the Ballista, the Hook Tower, the Knife Post, the shrine strike and the boss's return, no Cleanse or interrupts, Battle Hymn | M9, M10, S1, S3, R3; the strong bot still wins every location; client shows all of it |
| 2. Ten to a hundred, on scarce ground | v3's number scale, four-to-six-wave locations, rock and water, cell worth while placing, the Kit | G2.1–G2.4, G3.4, R1–R3, R5 |
| 3. One run | the run: pool life, carried gold, XP and levels, sigils with goals, the reskill point, bonus waves, the camp; run bots | G3.1–G3.3, M2, M3, T2 |
| 4. Relics and four verbs | relics (drops, the merchant), corpse, overkill, banish, debuff consumed; the Grove, the Soul Jar, the Tolling Bell, the Bone Altar reworked; Ilya's next physical kind | V1–V8, M5, M6 |
| 5. Charges and great towers | charges, AI dials, the meta shop, the Moon Well, the Effigy, the Firewall Pillar, the Tempest Spire | M1, M4, M7, G2.5, G2.6 |
| 6. The map fights back | blight, route choice, Flayer sprint, the final tuning | R6, R7, G3.1 again |
| Parallel: Skip | the predictor process, adopting the predicted world, the vision | G1.1–G1.6 |

## 21. The physical family *(Ilya: pirate hooks, knives; Knife Post; movers once per kind)*

Physical towers decide where and when damage lands as well as how much. They carry no element tags (armor is what
physical fears), and none attacks faster than the Arrow, since every hit deals at least 1.

| Tower | Rule | Hit / rate / reach | Price | Niche | Stage |
|---|---|---|---|---|---|
| Arrow | one arrow at the monster nearest the shrine | 2/3/4, 1.0, 2.8–3.2 | 1.0 | cheapest damage on the move | now |
| Ballista | a heavy bolt, slowly | 7/10/14, 0.4, 3.2–3.6 | 1.5 | the general answer to armor | 1 |
| Hook Tower | every few seconds hooks the foremost small monster past its spot and drags it 2 tiles back | 3/4/5, every 6/5/4 s, 2.8–3.2 | 1.5 | time under fire; the only tower that sends a flyer back | 1 |
| Knife Post | throws at a monster standing at a gate or held, if one is in reach, hitting a small one twice as hard | 2/3/4, 0.8, 2.6–3.0 | 1.0 | turns a gate into a kill zone for chaff | 1 |

- **Movers** move only **small monsters** (worth 1 life): never leaders, heavies or bosses, and never a monster
  standing at a gate. Each mover kind moves a given monster back at most once; different kinds stack. Every backward
  move is a banish.
- Further physical kinds (a swinging anchor, a net thrower, a fan of knives) are candidates Ilya picks after playing
  stage 1.
