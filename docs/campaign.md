# Hellward — the campaign

Two briefs from Ilya, 2026-09-26.

The first, after playing the one-map build: "I kind of like the setting. Now we need more distinct levels that let
each bit of content shine and play a role for the player". It asked for:

1. separate small locations with few monster types;
2. a skill tree;
3. spells that spend mana;
4. an intro screen per level;
5. a visible curse;
6. difficulty tuned by simulation, so that even strong scripted players find the game hard;
7. a drawn world map.

The second came after he played that campaign through. He won all six locations on Normal, on the first try, with
no life lost: "my strategy of putting cold on corners + mixing towers and spending all gold let me pass normal
without a single life lost". He asked for:

- tower upgrades as part of the skill tree;
- area curses, so the player has to spread the towers out;
- other ways to make the game harder;
- a story for every level, for the opening and for the ending;
- a second act in a different setting instead of the Hell difficulty;
- druid or necromancer towers.

This page is the design; [design](design.md) keeps the rules of one defence and how a leader chooses, and
[story](story.md) is the script.

## What the second pass changes, and why

His save shows why Normal was easy. It holds 18 sigils from six first-try victories of about three and a half
minutes each, and nine skills. Normal was tuned against the **apprentice**, a scripted player meant to stand for a
person on a first descent. He plays far better than it does. The strong scripted players won Normal "easily", and
that was the true measure of a good player. Four changes answer it:

1. **Curses strike an area.** A curse lands on a tower and on every tower near it. Towers bunched at a corner, as
   his were, share one curse. Spreading them costs coverage, which is the trade the game needed.
2. **A tower's second and third ranks are learned in the tree.** Gold still pays for a rank in the fight, but only
   the ranks the tree allows can be bought. Sigils become scarce, and a player chooses which two or three towers to
   master.
3. **Tuned against the strong players.** The strong players set every location's difficulty. The first two
   locations stay gentle, and each act's last fight is won on only some of their tries. The apprentice becomes the
   check that the start is gentle, not the target.
4. **Acts, not difficulties.** Hell is gone. Act II is a new place with new monsters, two new towers, new leader
   tricks and its own map. Replaying Act I harder would only have repeated it.

## The shape: two acts

**Act I, The Descent** (six locations) goes down from Tristram under the cathedral to Hell's Gate, as before. **Act
II, The Drowned Temples** (six locations) crosses the sea to Kurast. That is a jungle city of gold and rotting
wood, half sunk into swamp, where the order that built the lamps has its mother church. Act II opens when Hell's
Gate is held.

The descent is linear within an act. Each location opens when the one before it is held, and each one brings
exactly one new thing, so every intro has something to announce. Each act has its own painted world map. The map
screen shows one act at a time, with tabs for **I** and **II** where the difficulty toggle was.

A victory earns one, two or three sigils by the sanctuary's life left: 1, 10 and 18 of 20. A location counts its
best result. Act I holds 18 sigils and Act II 18 more. The tree costs 60, so even a perfect campaign masters only
part of it.

## Curses strike an area

Every curse has a **radius**. It lands on the tower the leader chose and on every tower whose centre lies within
the radius of that tower's centre. Towers stand on whole tiles, so these distances count:

- 1.0 reaches the four towers edge to edge with the target;
- 1.5 also reaches the diagonal ones;
- 2.1 reaches two tiles out in a straight line as well.

| Curse | Leader | Lasts | Radius | Reaches | Does |
|---|---|---|---|---|---|
| Weaken | Fallen Shaman, Blood Witch | 8 s | 1.5 | a 3×3 block | a third of the damage |
| Decrepify | Blood Witch | 8 s | 1.5 | a 3×3 block | 40% attack speed |
| Dim Vision | Bone Priest, Inquisitor | 8 s | 2.1 | a 3×3 block and a tile beyond each side | 55% of the reach |
| Bone Prison | Bone Priest | 4.5 s | 1.0 | a cross of five | caged: no attack |
| **Blight** (Act II) | Inquisitor | 8 s | 1.5 | a 3×3 block | fights one rank lower; a first-rank tower at 60% damage and speed |

A warded tower (Salvation) inside the area is spared; the others are not. **Cleanse still clears one tower.**
Answering a curse that caught four towers takes four casts, or a Smite before it lands. The chant's rune circle is
drawn at the curse's radius, so the player sees which towers it will catch before it lands. On landing, every
caught tower gets the slam and the curse's lasting look.

The planner already rolls out every candidate, so it sees what an area curse catches without new rules. Its quick
estimate adds up the damage every tower in the area would stop dealing, so that bunched towers reach the rollouts.
The candidates stay (curse, target tower) pairs. A chant fizzles if its target tower is sold or out of reach when
it ends. Otherwise the curse falls on the area around the target, whichever towers stand there then.

## The skill tree

Eight columns. The four towers of Act I and the two of Act II each have a column of four skills. Warding and
Sorcery have three each. A skill needs the one above it. Unlearning stays free (Akara's blessing). The tree greys
columns whose tower the location does not offer.

| Column | 1 (1 sigil) | 2 (2 sigils) | 3 (2 sigils) | 4 (3 sigils) |
|---|---|---|---|---|
| **Fire** (Pyre) | Adept of Fire: the second rank | Fire Ball: the first rank bursts too, every blast 0.3 wider | Master of Fire: the third rank | Blaze: fireballs leave the floor burning for 2 s |
| **Lightning** (Storm Obelisk) | Adept of Lightning | Chain Lightning: one more leap at every rank, leaps keep 95% | Master of Lightning | Static Field: strikes leaders first, and leaps to them first |
| **Cold** (Frost Shrine) | Adept of Cold | Glacial Spike: novas reach 0.4 further and hit 50% harder | Master of Cold | Shatter: a monster that dies chilled bursts for a tenth of its life |
| **Poison** (Plague Totem) | Adept of Poison | Contagion: venom leaps to a neighbour when its monster dies | Master of Poison | Lower Resist: a poisoned monster resists everything 25 points less |
| **Bone** (Bone Altar, Act II) | Adept of Bone | Corpse Explosion: a monster that dies amplified bursts for 15% of its life, unresisted | Master of Bone | Life Tap: a monster that dies amplified gives 2 mana (a leader, 10) |
| **Nature** (Druid Grove, Act II) | Adept of Nature | Hurricane: monsters inside a grove's aura are chilled 20% | Master of Nature | Twister: every 4 s the grove throws the monster nearest the sanctuary in its aura 1.5 tiles back |
| **Warding** | Holy Shield: gates 50% stronger, mend fully between waves | Salvation: Cleanse costs 25 and wards for 8 s | Thorns: a gate returns half of each blow | |
| **Sorcery** | Warmth: mana 40% faster, 25 more at most | Soul Harvest: a slain leader gives 10 mana | Spell Mastery: spells cost 25% less and strike 30% harder | |

A tower column costs 8 sigils, Warding and Sorcery 6 each, the whole tree 60. The old +25% masteries are gone; the
ranks carry that power now. A tower whose next rank is not learned shows a padlock on its upgrade button:
"Learn Adept of Fire in the skill tree (K)". The intro's arsenal shows each tower's highest learnable rank as pips,
so the tree can be reshaped before the fight.

Twister and Hurricane leave flyers alone. Twister leaves a boss alone too, and never throws a monster back past
the portal.

## The Act II towers

**Bone Altar** (the necromancer's; element *bone*). It curses the monsters back. Every few seconds it lays
**Amplify Damage** on the thickest knot of monsters in its reach, and those take more damage from everything while
it lasts. It deals no damage of its own. It belongs where the other towers' reaches overlap, not beside them. The
leaders see its worth in their rollouts and curse it first.

| Rank | Gold | Every | Reach | Amplify | Knot radius | Lasts |
|---|---|---|---|---|---|---|
| I | 90 | 3.0 s | 3.0 | +30% | 1.0 | 3.0 s |
| II | 100 | 2.8 s | 3.2 | +45% | 1.2 | 3.5 s |
| III | 160 | 2.5 s | 3.4 | +60% | 1.4 | 4.0 s |

- **Choosing the knot:** the altar centres on the monster, not yet amplified, whose circle holds the most such
  monsters' life. Amplify does not stack, and an immunity stays an immunity.
- **Curses on an altar:**
  - Weaken scales the amplification by its damage factor.
  - Decrepify slows its casting.
  - Dim Vision shrinks its reach.
  - Bone Prison stops it.
  - Blight drops it a rank.

**Druid Grove** (the druid's; element *nature*). It deals no damage. Its **aura** makes every tower within its
radius strike harder:

| Rank | Gold | Aura | Radius |
|---|---|---|---|
| I | 100 | +20% | 1.5 |
| II | 110 | +30% | 1.5 |
| III | 170 | +40% | 2.1 |

- **Stacking:** groves do not stack; a tower takes the best aura on it.
- **Against the curses:** the grove pulls towers together, and the area curses push them apart. It is the one piece
  that makes a bunch worth its risk. The aura's radius equals the commonest curse radius, so a player reads the
  trade at a glance: everything the grove helps, one curse on the grove catches.
- **Curses on a grove:**
  - Weaken scales its bonus.
  - Dim Vision shrinks its radius.
  - Bone Prison switches it off.
  - Blight drops it a rank.
  - Decrepify does nothing to it.

## The Act II monsters and leaders

| Monster | Life | Pace | Gold | Lives | Resists | Its role |
|---|---|---|---|---|---|---|
| Flayer | 60 | 1.45 | 4 | 1 | fire 25 | the swarm; its shaman raises it again |
| Zealot | 190 | 1.0 | 10 | 1 | lightning 40, fire 25 | the fallen church's foot soldiers |
| Spider | 120 | 1.35 | 8 | 1 | immune to poison, cold −25 | fast, and poison is useless |
| Blood Bat | 55 | 1.9 | 5 | 1 | cold 50, poison 25; flies | the flock that ignores gates |
| Thorned Hulk | 760 | 0.55 | 30 | 2 | immune to poison, cold 25, fire −25 | breaks a gate in seconds (70 a second) |
| The Drowned | 320 | 0.7 | 14 | 1 | cold 50, poison 50, lightning −25 | slow, and deaf to cold and venom |

The Act II leaders bring new ways of cursing, not only new curses:

- **Fetish Shaman** (Flayers'): Weaken, chanted as usual. Every 7 s it also **raises** up to three Flayers that
  fell within 3 tiles of it in the last 5 s, at half their life. This is a green burst, and a raised Flayer pays no
  gold again. A Flayer burst by Corpse Explosion or Shatter leaves nothing to raise.
- **Zakarum Inquisitor** (the zealots'): Blight and Dim Vision, **without a chant**. The curse lands the moment it
  has pondered (the half-second dots). Smite during the dots still breaks it, but with a person's reaction time
  that is rare, so the answers are wards (Salvation), Cleanse, spreading out, and killing inquisitors first. Its
  cooldown is 12 s, longer than a chanting leader's.
- **The Bone Priest, unbound**, the last fight's boss. The narrator fights at last.
  - **Numbers:** 6000 life, pace 0.45, resists 25 (poison: immune), 20 lives if he reaches the sanctuary.
  - **Curses:** Bone Prison, Blight, Weaken and Decrepify, chanted, every 6 s, from 6 tiles, each with its radius
    0.6 wider.
  - **Mana:** every curse of his that lands burns 15 of the player's mana.
  - **Look:** the Bone Priest's painted sheet at 1.6 times the size, with a violet glow.

## Locations

Every location is one 25 × 14 map with its own path, look and wave list, and brings one new thing. Arches stand
only on the path's vertical legs.

**Act I, The Descent**

| # | Location | Monsters | Leaders | New | What it teaches |
|---|---|---|---|---|---|
| 1 | **Tristram** | Fallen, Zombie | Shaman | Pyre, Frost; Cleanse | Fire and frost; a curse that catches two towers |
| 2 | **The Graveyard** | Skeleton, Zombie | Bone Priest | Storm, gates; Smite | Gate queues; Smite on the sign |
| 3 | **The Cathedral** | Fallen, Goatman, Skeleton | Shaman, Witch | Plague; Meteor | Resistances decide the mix |
| 4 | **The Catacombs** | Skeleton, Zombie, Overlord | Priest, Witch | Frozen Orb | Gate-breakers, four arches |
| 5 | **The Caves** | Goatman, Gargoyle, Fallen | Witch, Shaman | the lava floor | Flyers ignore gates; few places to build |
| 6 | **Hell's Gate** | everything, Azazel | all three | — | The council of curses |

**Act II, The Drowned Temples**

| # | Location | Monsters | Leaders | New | What it teaches |
|---|---|---|---|---|---|
| 1 | **Kurast Docks** | Flayer, Zealot | Fetish Shaman | Bone Altar | Amplify where the reaches cross; kill the shaman or burst the dead |
| 2 | **The Spider Forest** | Spider, Blood Bat, Flayer | Fetish Shaman | Druid Grove | Poison is useless; the grove's bunch against the curses' reach |
| 3 | **The Flayer Jungle** | Flayer, Zealot, Spider | Inquisitor, Fetish Shaman | the silent curse | Wards and spreading, since the curse gives no warning |
| 4 | **The Drowned City** | The Drowned, Thorned Hulk, Blood Bat | Inquisitor, Blood Witch | Thorned Hulks | Fire and lightning against the deaf-to-cold; gates fall fast; water everywhere |
| 5 | **Travincal** | Zealot, Hulk, Flayer, Bat | the High Council: all five leader kinds | — | Curses from every side |
| 6 | **The Temple of Light** | the Drowned, Zealot, Bat, the Bone Priest unbound | Inquisitor, Priest, and him | the boss | The narrator himself |

- **Where the new things are offered:** Act II offers every Act I tower, gate and spell from its first location. The
  Bone Altar arrives at the Docks and the Grove in the Spider Forest.
- **The maps:**
  - Docks: piers over black water, so few tiles to build on.
  - Spider Forest: a winding path between web-choked trees.
  - Flayer Jungle: long straight legs, where lanes of towers tempt.
  - Drowned City: canals everywhere, with two arches on bridges.
  - Travincal: a terrace that folds three times under the council.
  - Temple of Light: a short path, three arches, and the lamp hanging over the sanctuary.
- **The look:** the Act II floors are painted in greens, black water, moss, gilt and torchlight, the opposite of Act
  I's reds and browns.

## The story

Every location tells its part twice:

- **Before the fight:** a painted panel and a few lines on a story page. It opens the first time the lantern
  arrives, and the intro's **Story** button (S) replays it.
- **After the first victory:** a second page, after the reckoning.

The campaign opens with the prologue, the intro comic, which is already painted and voiced. It plays on the first
Descend, and **Prologue** on the title replays it. Each act ends with two or three ending pages after its last
fight. The script, and who speaks where, is [story](story.md). The Bone Priest's taunt stays on each intro screen.
Akara narrates what lies ahead. The necromancer and the eldest druid join as the Act II towers arrive. The
narration is written, not spoken; the prologue keeps its recorded voice.

A story page is:

- the painted panel, full screen, in the prologue's heavy-ink style (Gemini 3 Pro Image, with the game's sprites
  as references);
- the text fading in line by line over a dark band at the bottom;
- **Continue** (Enter or a click);
- **Skip** (Esc).

## Tuning by simulation

The method stays; the targets change.

- **What a player may do.** A player sees what a human sees: the intro's roster, the map, the gold, the mana, the
  leaders' chants. It chooses its skills for the location, places and upgrades towers, builds gates and casts every
  spell. It may plan a location's build by simulating it offline, as a player who has replayed the location many
  times has in effect done.
- **A human's hands** (`players/hands.py`): a leader's sign seen 0.5–0.8 s late, aim where the leader stood when the
  reaction began, one aimed spell each half second, never paused, no view of a leader's mind before it speaks.
- **Seeds:** offline planning uses training seeds 0–99; the tables use evaluation seeds 1000–1019.
- **The margin M:** the largest factor on every monster's life at which a player still wins, bisected to 2%, the
  median over 8 seeds.
- **B\*:** the strong player with the best margin at a location.
- **The players:** warden, planned and adaptive (the strong ones); apprentice (a thoughtful first descent); ordinary
  (the demo's defender, no skills).
  - All of them learn tower ranks from the tree.
  - All of them place towers knowing that a curse strikes an area.
  - All of them use the Act II towers.
  - The warden's and the planned player's builds are searched again after the rules change.
- **Sigils in hand:** a player at location i of an act holds three sigils for every location before it (Act II
  adds Act I's 18). That is the pace Ilya kept.

**Targets** (B*'s margin, with those sigils, against the smart leaders):

| | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| Act I | ≈1.8 | ≈1.5 | ≈1.35 | ≈1.25 | ≈1.2 | ≈1.1 |
| Act II | ≈1.3 | ≈1.25 | ≈1.2 | ≈1.15 | ≈1.1 | ≈1.0, won on about half the seeds |

- **The first two locations** also stay winnable by the apprentice. From the Cathedral on it may fall, since a person
  on a first descent should have to learn.
- **The leaders matter:**
  - the lives B* loses against the smart leaders, minus those against random curses, are at least 20% of what it
    loses;
  - at most half of all curses are broken before they land;
  - the planner keeps at least 0.85 of the best curse's value (`tools/curse_quality.py`).
- **The knobs:**
  - each location's life factor, its waves and its starting gold;
  - the leaders' cooldowns;
  - the curse radii (one table for the whole game).

  `tools/margin.py` sets the life factors, and `tools/campaign_balance.py` prints the table and records every run.
- **Speed:** the tools run the simulation compiled with mypyc (`sim/fastsim.py`, about 10× faster, bit-identical to
  the source), and heavy runs go through `~/saga/tools/slot.py`.

**What the first tuning taught** stays true of the rules:

- A gate queue rebuilt the moment it broke was a kill zone, so **a broken gate lies in rubble until the fight dies
  down between waves**.
- Smite broke seven chants in ten, so **every spell gathers itself** after a cast.
- Spells that grew with the difficulty turned hard fights into spell play, so **spells grow with the location
  only**.

## Screens

Title → Prologue (first time) → world map (act tabs) ↔ skill tree → the lantern travels → story page (first
arrival) → intro → defence → reckoning → story page (first victory) → world map; after an act's last fight, its
ending pages.

- **The intro:** its buttons are Defend (Enter), Skills (K), Story (S) and Back to the map (Esc).
- **The reckoning:** Again (Enter) returns to the intro; To the map is Esc.
- **The title:** Descend, Prologue, Watch the leaders at work, Settings, Leave.
- **The panel:** unchanged: spells at the right (Q W E), gold in the centre row, Pace and Menu at the top right.
