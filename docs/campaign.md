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
   his were, share one curse. Spreading them costs coverage, which is the trade the game needed. Frost's slow now
   follows each monster's cold resistance, so frost on every corner stops being the answer to everything.
2. **A tower's second and third ranks are learned in the tree.** Gold still pays for a rank in the fight, but only
   the ranks the tree allows can be bought. Sigils become scarce, and a player chooses which two or three towers to
   master.
3. **Tuned against a veteran.** A strong scripted player with a person's reaction time sets every location's
   difficulty. The first two locations stay gentle, and each act's end is near its limit. The strongest bots
   check that the game is hard for them too, and a bot playing Ilya's own opening checks that it no longer wins
   untouched.
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

Every curse has a **radius**. When a leader begins its chant it marks a **spot**: the tile of the tower it chose.
When the curse lands, it falls on every tower standing within the radius of that tile, whichever towers stand there
then. Selling the tower under the mark does not stop it, and **a cursed tower cannot be sold** ("The curse holds
it"). A chant fizzles only if its leader dies, is broken by a spell, or has walked out of reach of the spot.
Distances count whole tiles:

- 1.0 reaches the four towers edge to edge with the spot;
- 1.5 also reaches the diagonal ones;
- 2.3 reaches a knight's move away as well.

| Curse | Leader | Lasts | Radius | Reaches | Does |
|---|---|---|---|---|---|
| Weaken | Fallen Shaman, Blood Witch, Inquisitor | 8 s | 1.5 | a 3×3 block | a third of the damage |
| Decrepify | Blood Witch | 8 s | 1.5 | a 3×3 block | 40% attack speed |
| Dim Vision | Bone Acolyte, Inquisitor | 8 s | 2.3 | 21 tiles | 55% of the reach |
| Bone Prison | Bone Acolyte | 4.5 s | 1.0 | a cross of five | caged: no attack |

The Bone Priest's own curses (the last fight) are 1.0 wider.

**Why these radii:**

- **No single spacing beats all of them.** Towers a knight's move apart dodge a 1.5 curse but not Dim Vision, so the
  safe spacing depends on which leaders a location sends.
- **The player can plan for them.** The intro's leader cards print each curse's radius, so the spacing is chosen
  before the fight.
- **Clustering still has a price after the curse lands.** A warded tower (Salvation) inside the area is spared.
  Cleanse still clears **one** tower, so a curse that caught four needs four casts, or a Smite before it lands.
- **The player sees exactly what is coming.** The chant's rune circle is drawn at the curse's radius on the marked
  spot. When the curse lands, every caught tower gets the slam and the curse's lasting look. The world emits one
  `cursed` event per curse, carrying every tower it caught.

**Chill follows cold resistance.** A frost nova's slow, and the weaker blows on gates that come with it, are scaled by
how much cold the monster takes: a quarter shallower on a Skeleton, half on the Drowned, and none at all on the
cold-immune. Frost at every corner was Ilya's winning opening, and nothing answered it.

**The planner.** Candidates stay (curse, spot) pairs, one spot per tower in reach.

- The quick estimate works out every monster's walk once per decision.
- It prices each tower's loss once per curse.
- It adds up the loss over the unwarded towers each spot catches.
- A support tower's loss is what it lends: an aura's bonus on the towers under it, or the altar's amplification on
  the damage dealt in its reach.
- Spots that would catch the same towers with the same curse are one candidate.
- The rollouts do the rest as before.

## The skill tree

Eight columns. The four towers of Act I and the two of Act II each have a column of four skills, costing 1, 2, 2 and
3 sigils. Warding and Sorcery have three, costing 1, 2 and 3. A skill needs the one above it. Unlearning stays free
(Akara's blessing). The tree greys columns whose tower the location does not offer.

| Column | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| **Fire** (Pyre) | Adept of Fire: the second rank | Fire Ball: the first rank bursts too, every blast 0.3 wider | Master of Fire: the third rank | Blaze: fireballs leave the floor burning for 2 s |
| **Lightning** (Storm Obelisk) | Adept of Lightning | Chain Lightning: one more leap at every rank, leaps keep 95% | Master of Lightning | Static Field: strikes leaders first, and leaps to them first |
| **Cold** (Frost Shrine) | Adept of Cold | Glacial Spike: novas reach 0.4 further and hit 50% harder | Master of Cold | Shatter: a monster that dies chilled bursts for a tenth of its life |
| **Poison** (Plague Totem) | Adept of Poison | Contagion: venom leaps to a neighbour when its monster dies | Master of Poison | Lower Resist: a poisoned monster resists everything 25 points less |
| **Bone** (Bone Altar, Act II) | Adept of Bone | Corpse Explosion: a monster that dies amplified bursts for 15% of its life, unresisted, within 1.2 | Master of Bone | Life Tap: a monster that dies amplified gives a fifth of its bounty in mana |
| **Nature** (Druid Grove, Act II) | Adept of Nature | Hurricane: walkers within 2.5 tiles of a grove move 20% slower | Master of Nature | Twister: every 4 s the grove roots the walker nearest the sanctuary within 2.5 tiles for 1.5 s |
| **Warding** | Holy Shield: gates 50% stronger, mend fully between waves | Salvation: Cleanse costs 25, wards for 8 s, and may be cast on an uncursed tower to ward it | Thorns: a gate returns half of each blow | |
| **Sorcery** | Warmth: mana 40% faster, 25 more at most | Soul Harvest: a slain leader gives 10 mana | Spell Mastery: spells cost 25% less and strike 30% harder | |

A tower column costs 8 sigils, and Warding and Sorcery cost 6 each, so the whole tree costs 60. The old +25%
masteries are gone; the ranks carry that power now.

- **Buying a rank:** a tower whose next rank is not learned shows a padlock on its upgrade button, with the tip
  "Learn Adept of Fire in the skill tree (K)".
- **Planning for it:** the intro's arsenal shows each tower's highest learnable rank as pips.
- **Old saves:** a save's learned skills that the new tree no longer has are forgotten, and their sigils come back.

Bursts from Shatter and Corpse Explosion never set off another burst. Twister roots neither flyers nor anything worth
two or more lives (Overlords, Hulks, leaders, the Bone Priest).

## The Act II towers

Both are ordinary towers whose ranks use the same numbers as every other tower. Their **damage** is the bonus they
give, their **rate** is how often they act and their **range** is their reach. Every curse therefore acts on them
through the rules that already exist, and needs no new ones.

**Bone Altar** (the necromancer's). It curses the monsters back: it lays **Amplify Damage** on the thickest knot of
monsters in its reach, and they take more damage from everything while it lasts. It pulses, with a gap between
casts, so where it stands against the other towers' fire matters. It deals no damage of its own.

| Rank | Gold | Every | Reach | Amplify | Knot radius | Lasts |
|---|---|---|---|---|---|---|
| I | 90 | 4.0 s | 3.0 | +30% | 1.0 | 2.0 s |
| II | 100 | 3.6 s | 3.2 | +45% | 1.2 | 2.2 s |
| III | 160 | 3.2 s | 3.4 | +60% | 1.4 | 2.5 s |

- **Choosing the knot:** the altar centres on the monster, not yet amplified, whose circle holds the most such
  monsters' life. Amplify does not stack, and an immunity stays an immunity.
- **Curses on an altar:**
  - Weaken scales the amplification.
  - Decrepify slows its pulse.
  - Dim Vision shrinks its reach.
  - Bone Prison stops it.

**Druid Grove** (the druid's). It deals no damage. Its **aura** makes every tower within its radius strike harder.

| Rank | Gold | Aura | Radius |
|---|---|---|---|
| I | 100 | +20% | 1.5 |
| II | 110 | +30% | 1.5 |
| III | 170 | +40% | 2.3 |

- **Stacking:** groves do not stack; a tower takes the best aura on it.
- **The tension:** the grove pulls towers together, and the area curses push them apart. The aura's radius equals
  the commonest curse radius, so everything the grove helps, one curse on the grove catches.
- **Curses on a grove:**
  - Weaken scales its bonus.
  - Bone Prison switches it off.
  - Decrepify does nothing to it.
  - Dim Vision does nothing either, since an aura is not a reach.
- **Computed live:** the aura is worked out when a tower attacks, not kept on the world, so a clone never shares it.

## The Act II monsters and leaders

| Monster | Life | Pace | Gold | Lives | Resists | Its role |
|---|---|---|---|---|---|---|
| Flayer | 60 | 1.45 | 4 | 1 | fire 25 | the swarm; its shaman raises it again |
| Zealot | 190 | 1.0 | 10 | 1 | lightning 40, fire 25 | the fallen church's foot soldiers |
| Spider | 120 | 1.35 | 8 | 1 | immune to poison, cold −25 | fast, and poison is useless |
| Blood Bat | 55 | 1.9 | 5 | 1 | cold 50, poison 25; flies | the flock that ignores gates |
| Thorned Hulk | 760 | 0.55 | 30 | 2 | immune to poison, cold 25, fire −25 | breaks a gate in seconds (70 a second) |
| The Drowned | 320 | 0.7 | 14 | 1 | cold 50, poison 50, lightning −25 | slow, and deaf to cold and venom |

The Act II leaders bring new ways of cursing:

- **Fetish Shaman** (the Flayers'): Weaken, chanted as usual.
  - **Raising:** a Flayer that dies within 3 tiles of a living Fetish Shaman rises once, where it fell, at half its
    life, after lying still for a second. It keeps its place in its wave, and its gold is paid only once.
  - **Leaving nothing to raise:** a Flayer burst by Corpse Explosion or Shatter stays dead.
- **Zakarum Inquisitor** (the zealots'): Weaken and Dim Vision, **marked, not chanted**.
  - **The mark:** when it has chosen, its rune circle burns on the floor for 1.5 s, and then the curse lands. Nothing
    breaks a mark, not even Smite or Frozen Orb.
  - **The answers:** ward the marked towers (Salvation's Cleanse on an uncursed tower), move nothing into the circle,
    or kill the inquisitor before the mark runs out.
  - **Cooldown:** 12 s.
- **The Bone Priest**, the last fight's boss: the narrator fights at last.
  - **Numbers:** 6000 life, pace 0.45, resists 25 (poison: immune), 20 lives if he reaches the sanctuary.
  - **Curses:** Bone Prison, Weaken, Decrepify and Dim Vision, chanted, every 8 s, from 6 tiles, each 1.0 wider than
    usual.
  - **Mana:** each curse of his that lands burns 5 mana for every tower it caught.
  - **Look:** the prologue's crowned priest at 1.6 times a monster's size, with a violet glow.
- **The Bone Acolyte:** the Act I leader that was called "Bone Priest" is now his acolyte. It casts the curses his
  bones chose, and it loses the crown and the green orb, which are his alone.

## Locations

Every location is one 25 × 14 map with its own path, look and wave list, and brings one new thing. Arches stand
only on the path's vertical legs. The intro shows a location's **lesson** as a line of advice, in place of its blurb.
The blurb stays in the map's hover tip.

**Act I, The Descent**

| # | Location | Monsters | Leaders | New | Lesson |
|---|---|---|---|---|---|
| 1 | **Tristram** | Fallen, Zombie | Shaman | Pyre, Frost; Cleanse | His curses fall on a tower and the towers beside it: spread your fire and frost. |
| 2 | **The Graveyard** | Skeleton, Zombie | Acolyte | Storm, gates; Smite | A gate holds the dead in a queue, and Smite on the sign stops a curse before it comes. |
| 3 | **The Cathedral** | Fallen, Goatman, Skeleton | Shaman, Witch | Plague; Meteor | Goatmen shrug off lightning and skeletons venom: mix your towers by what comes. |
| 4 | **The Catacombs** | Skeleton, Zombie, Overlord | Acolyte, Witch | Frozen Orb | Overlords break gates in seconds; frost weakens their blows and venom seeks the biggest. |
| 5 | **The Caves** | Goatman, Gargoyle, Fallen | Witch, Shaman | the lava floor | Wings ignore gates, and the lava leaves few places to build. |
| 6 | **Hell's Gate** | everything, Azazel | all three | — | Every curse at once, and Azazel will not burn. |

**Act II, The Drowned Temples**

| # | Location | Monsters | Leaders | New | Lesson |
|---|---|---|---|---|---|
| 1 | **Kurast Docks** | Flayer, Zealot | Fetish Shaman | Bone Altar | Amplify where your towers' reaches cross; kill the shaman, or burst the dead so they stay down. |
| 2 | **The Spider Forest** | Spider, Blood Bat, Flayer | Fetish Shaman, Blood Witch | Druid Grove | Poison is useless here. A grove makes a bunch worth its risk. |
| 3 | **The Flayer Jungle** | Flayer, Zealot, Spider | Inquisitor, Fetish Shaman | the mark | The inquisitors curse without a chant: ward the marked towers, and kill them first. |
| 4 | **The Drowned City** | The Drowned, Thorned Hulk, Blood Bat | Inquisitor, Blood Witch | Thorned Hulks | Frost barely slows the drowned; fire and lightning must. Gates fall fast. |
| 5 | **Travincal** | Zealot, Hulk, Flayer, Bat | the High Council: all five leader kinds | — | Curses from every side. |
| 6 | **The Temple of Light** | the Drowned, Zealot, Bat, the Bone Priest | Inquisitor, Acolyte, and him | the boss | Each curse of his that lands burns your mana for every tower it catches. |

- **Where the new things are offered:** Act II offers every Act I tower, gate and spell from its first location. The
  Bone Altar arrives at the Docks and the Grove in the Spider Forest.
- **The Spider Forest's curses:** it sends a Blood Witch from its third wave, so the grove's bunch is cursed often
  enough to cost something.
- **The maps:**
  - Docks: piers over black water, so few tiles to build on.
  - Spider Forest: a winding path between web-choked trees.
  - Flayer Jungle: long straight legs, where lanes of towers tempt.
  - Drowned City: canals everywhere, with two arches on bridges.
  - Travincal: a terrace that folds three times under the council.
  - Temple of Light: a short path, three arches, and the mother lamp over the sanctuary.
- **The look:** the Act II floors are painted in greens, black water, moss, gilt and torchlight, the opposite of Act
  I's reds and browns.
- **The last two locations of each act** end with a large fast group worth one life each, after the gate-breakers.
  A defence slightly short of the bar then loses a few lives and earns one or two sigils, instead of falling.

## The story

[Story](story.md) has the cast, the rules the words keep and the panel bible. `hellward/story.py` holds every page.

**Who speaks:**

- **The Bone Priest:** the prologue's voice. He taunts on every intro; the twelve taunts carry his arc from certain
  to afraid.
- **Akara:** tells you what lies ahead in Act I.
- **The necromancer and the eldest druid:** join in Act II, as their towers arrive.

**The pages:**

- **The prologue:** the painted intro comic, with its recorded voice and music. It plays on the first Descend.
- **Before a fight:** a location's before page plays the first time the lantern arrives there. The intro's
  **Story** button (S) replays it.
- **After a fight:** its after page plays after its first victory, when the player leaves the reckoning by either
  button, and then goes where that button pointed.
- **Act endings:** each act's last fight has no after page; the act's ending takes its place. After the ending the
  map opens on the next act, and the lantern walks to its first location.

**What gets remembered:**

- **Seen pages:** the progress remembers every page that has opened; skipping one counts as seeing it.
- **Due pages:** when the map opens, it first plays any after page or ending that is due and unseen. That covers a
  player who quit at the reckoning, and a save that already holds Hell's Gate.
- **The Chronicle:** the title's **Chronicle** shows the prologue and then every page whose moment has come
  (a location opened, a location held, an act finished), grouped by act. So a player who won Act I before the story
  existed can read it.

A story page is:

- the painted panel, full screen, in the prologue's heavy-ink style;
- the text fading in over a dark band at the bottom;
- **Enter or a click:** the first shows all the text and the second continues;
- **Esc:** skips.

The screen after a story page ignores keys pressed before it opened, so a held Enter never starts a fight unread.

## Tuning by simulation

The method stays; the yardstick changes. The bots that beat the old Normal hardest hold two to nine times the
monsters' life a first-descent player holds. Tuned to their ceiling, the game would be unwinnable for people. It is
therefore tuned to a **veteran**: a strong player with a person's hands. The strongest bots are a check that the
game stays hard for them too.

- **What a player may do.** A player sees what a human sees: the intro's roster, the map, the gold, the mana, the
  leaders' chants and marks. It chooses its skills, places and upgrades towers, builds gates and casts every spell.
- **A human's hands** (`players/hands.py`): a leader's sign seen late, aim where the leader stood when the reaction
  began, never paused, no view of a leader's mind before it speaks. The strong players react in 0.5–0.8 s and cast an
  aimed spell each half second at most.
- **The players:**
  - **veteran:** the warden's rules drafting its build from the intro, with no stored or searched plan. It reacts in
    0.8–1.2 s and casts one aimed spell a second at most. This is the target.
  - **corner:** Ilya's stated opening: frost on every path corner, mixed towers packed round it, every coin spent. It
    checks that the area curses and chill-by-resistance took away the answer that won the old Normal.
  - **warden, planned, adaptive:** the strong players, with builds drafted or searched offline.
  - **apprentice:** a thoughtful first descent.
  - **ordinary:** the demo's defender.

  All of them learn ranks from the tree, space their towers knowing the curse radii, and use the Act II towers. The
  searched builds are searched again once the rules land, against leaders that roll out as the game's do.
- **Seeds:** offline planning uses training seeds 0–99; the tables use evaluation seeds 1000–1019.
- **Sigils in hand:** three for every earlier location (Act II adds Act I's 18). That is the pace Ilya kept.
- **The margin M:** how far a location's life factor could grow and still be won, `tools/margin.py` bisecting
  `Location.life` itself, spells and all. It is found to 2%, as the median over 8 seeds.

**Targets:**

| | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| veteran's M, Act I | ≈1.5 | ≈1.4 | ≈1.3 | ≈1.2 | ≈1.15 | ≈1.1 |
| veteran's M, Act II | ≈1.25 | ≈1.2 | ≈1.15 | ≈1.1 | ≈1.07 | ≈1.05 |

- **Winning:** at the tuned factor (M's 1.0) the veteran wins every seed. At each act's end it keeps a median of 10–17
  lives, shaped by the last waves.
- **The strongest bot's M, B\*:** at least 1.2 everywhere. Where the strong players' margins differ by more than 1.5
  times, the reason is found before that location is tuned: an outlier is a bot exploit until shown otherwise.
- **The apprentice** wins the first two locations of each act.
- **The corner player:** its M falls at least 20% when the curse radii go from zero to the table's, and it sits below
  the veteran's.
- **The leaders matter:** from each act's third location on, the veteran's M against random curses is at least
  1.10 times its M against the smart leaders. A landed curse catches about two of the veteran's towers on average.
- **The planner stays sharp:** `tools/curse_quality.py` keeps at least 0.85 of the best curse's value, at the
  Cathedral, Hell's Gate, the Docks, Travincal and the Temple.
- **Decision time:** at most 100 ms per decision at Travincal and the Temple on the build the game runs. The game's
  leaders think on the compiled simulation when it is built (`tools/sim_bench.py` measures it).
- **Ilya's own play:** from this build on, every defence a person plays is logged (location, seed, skills, every
  command with its game time) in `~/.hellward/replays/`. A ghost player can replay his build, so the veteran's targets
  can move to where his margin really sits.

**What the first tuning taught** stays true of the rules:

- A gate queue rebuilt the moment it broke was a kill zone, so **a broken gate lies in rubble until the fight dies
  down between waves**.
- Smite broke seven chants in ten, so **every spell gathers itself** after a cast.
- Spells that grew with the difficulty turned hard fights into spell play, so **spells grow with the location
  only**.

## Screens

Title → prologue (first time) → world map (act tabs) ↔ skill tree → the lantern travels → story page (first
arrival) → intro → defence → reckoning → story page (first victory) → world map; after an act's last fight, its
ending.

- **The intro:** its buttons are Defend (Enter), Skills (K), Story (S) and Back to the map (Esc). It shows the
  lesson line and the leaders' curse radii.
- **The reckoning:** Again (Enter) returns to the intro; To the map is Esc.
- **The title:** Descend, Chronicle, Watch the leaders at work, Settings, Leave.
- **The panel:** unchanged: spells at the right (Q W E), gold in the centre row, Pace and Menu at the top right.
