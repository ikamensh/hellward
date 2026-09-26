# Hellward — the campaign

The brief (Ilya, 2026-09-26), after playing the one-map build: "I kind of like the setting. Now we
need more distinct levels that let each bit of content shine and play a role for the player":

1. separate small locations, each with a few monster types;
2. meta-progression through a skill tree;
3. global spells that spend mana;
4. an intro screen for each level, describing its enemies and their curses;
5. a more visible curse animation;
6. difficulty tuned by simulation: strong scripted players should find the game hard to beat;
7. a drawn world map, travelled between locations.

This page is the design; [design](design.md) keeps the rules of one defence and how a leader
chooses.

## The shape: a descent

The game is called Hellward, so the campaign goes down. The world map is a **cut-away of the
ground under Tristram**. The village and its cathedral stand on the surface. Below them lie the
graveyard's crypts, and deeper still the catacombs on one side and the caves on the other. The
gate of hell is at the bottom. The party is a lantern. It walks a lit trail from one location to
the next, downwards.

```
                  Tristram (1)
                      │
                 The Graveyard (2)
                      │
                 The Cathedral (3)
                 ╱            ╲
       The Catacombs (4)    The Caves (5)
                 ╲            ╱
                  Hell's Gate (6)   needs both
```

The branch after the Cathedral is the one choice of route. Both branches must be won before
Hell's Gate opens, so the finale meets a player who has seen every monster.

**Difficulties** are Diablo's: **Normal**, **Nightmare** (opens once Hell's Gate falls on Normal)
and **Hell** (once it falls on Nightmare). A harder difficulty plays the same six locations with
stronger monsters and quicker leaders. The skill tree carries over.

## Locations

Every location is one 25 × 14 map with its own path, look and wave list: five to eight waves
of two to four monster kinds and one or two kinds of leader. Each location is built around the
content it introduces, so that piece decides the fight there.

| # | Location | Monsters | Leaders (curses) | New for the player | What it teaches |
|---|---|---|---|---|---|
| 1 | **Tristram**, the burning village | Fallen | Fallen Shaman (Weaken) | Pyre, Frost Shrine; Cleanse | Fire bursts the Fallen swarm. Frost holds them in the fire. A shaman's Weaken halves your best tower until you cleanse it. |
| 2 | **The Graveyard** | Skeleton, Zombie | Bone Priest (Bone Prison, Dim Vision) | Storm Obelisk, warded gates; Smite | Zombies burn and shrug off poison, skeletons are immune to poison. Crypt gates hold walkers under your fire. Smite a priest mid-chant and the curse fizzles. |
| 3 | **The Cathedral** (today's map) | Fallen, Goatman | Fallen Shaman, Blood Witch (Decrepify, Weaken) | Plague Totem; Meteor | Goatmen shrug off lightning, so venom and fire take over. Meteor breaks a queue at a gate. The first location with two kinds of leader. |
| 4 | **The Catacombs** | Skeleton, Zombie, Overlord | Bone Priest, Blood Witch | Frozen Orb | Overlords break gates in seconds. Frost weakens their blows and venom seeks the biggest. Four gates, one behind another. |
| 5 | **The Caves** | Goatman, Gargoyle, Fallen | Blood Witch, Fallen Shaman | Frozen Orb (whichever branch comes first teaches it) | Gargoyles fly over every gate, so the answer is reach and lightning, not walls. |
| 6 | **Hell's Gate** | Fallen, Goatman, Gargoyle, Overlord, Azazel | all three | — | Everything at once, and Azazel, immune to fire, walks behind a council of three leaders. |

What a location offers is fixed by its place in the campaign, not by the save. Tristram always
has the Pyre and the Frost Shrine and nothing else, so a replay is the same puzzle, and the
balance tools measure the fight the player gets. From the Catacombs on, everything is available.

**Maps.** The locations after the Cathedral are shorter than its 56-tile path. The village road
bends once. The graveyard's path folds twice past two crypt arches. The catacombs are a long
corridor with four arches in a row. The caves' path runs beside lava in wide loops that flyers
follow too. Hell's Gate folds three times and has three arches. Each map has its own floor
(`art/mapart.py` themes: village, graveyard, cathedral, catacombs, caves, hell), painted over
its stand-in the way the cathedral floor was. The obstacles that stand up (pillars today) come
in the theme's kind: gravestones, bone heaps, stalagmites, brimstone spires.

## Meta-progression: sigils and the skill tree

A victory earns **sigils** by the sanctuary's life left: one for holding, two for keeping 10 of
20, three for keeping 18. A location's best result counts on each difficulty, so the campaign
holds 18 sigils per difficulty and 54 in all. Every sigil is a skill point.

The **skill tree** has six columns of three skills. A skill needs the one above it. The three
tiers cost 1, 2 and 3 sigils, so the whole tree costs 36. Normal alone buys half of it and
Nightmare buys the rest. **Unlearning is free** (Akara's blessing), from the map or a
location's intro, so a player can reshape the tree for the location ahead once its intro
shows who is coming.

| Column | 1 (1 sigil) | 2 (2 sigils) | 3 (3 sigils) |
|---|---|---|---|
| **Fire** (Pyre) | Fire Mastery: 25% more damage | Fire Ball: the first rank bursts too, every blast 0.3 wider | Blaze: fireballs leave the ground burning for 2 s |
| **Lightning** (Storm Obelisk) | Lightning Mastery: 25% more damage | Chain Lightning: one more leap at every rank, leaps keep 95% | Static Field: lightning leaps to leaders first and hits them twice as hard |
| **Cold** (Frost Shrine) | Cold Mastery: chills 10 points deeper and 30% longer | Glacial Spike: novas reach 0.4 further and hit 50% harder | Shatter: a monster that dies chilled bursts for a quarter of its life around it |
| **Poison** (Plague Totem) | Poison Mastery: venom 30% stronger | Contagion: a poisoned monster's venom jumps to its neighbour when it dies | Lower Resist: a poisoned monster resists everything 25 points less (immunities hold) |
| **Warding** (gates, curses) | Holy Shield: gates have 50% more life and mend fully between waves | Salvation: Cleanse costs 25 and wards the tower against curses for 8 s | Thorns: a gate returns twice each blow to whoever strikes it |
| **Sorcery** (mana, spells) | Warmth: mana flows 40% faster, 25 more at most | Soul Harvest: a slain leader gives 20 mana | Spell Mastery: Smite, Meteor and Frozen Orb cost 25% less and strike 30% harder |

Each skill is one change to a number or a rule of the simulation, which works out every
modifier once when a defence begins (`sim/skills.py` → `Perks`). A skill for a tower the
location does not offer does nothing there, and the intro says so.

## Spells: what mana is for

Mana (the blue orb) fills at 1.5 a second up to 100 and starts at 60. Four spells spend it.
They sit in a bar beside the orb (**Q W E R**). A spell is picked, then aimed with a click, as
a tower is placed; right click or Esc lets go of it.

| Spell | Mana | Aim | What it does |
|---|---|---|---|
| **Cleanse** | 35 | a tower | Burns every curse off it (today's Cleanse, also **C** on a selected tower). |
| **Smite** | 40 | a monster | Holy lightning from the vault: 150 damage, which no resistance reduces, and a chanting leader's curse fizzles. Its cooldown starts again. |
| **Meteor** | 60 | the floor | Lands 1.2 s later: 180 fire damage within 1.4 tiles. The ground burns for 3 s after. |
| **Frozen Orb** | 50 | the floor | Everything within 1.8 tiles freezes for 2.5 s: it cannot walk or batter, and a leader's chant breaks. It also deals 50 cold damage. |

Spell damage grows with the wave's life multiplier, so a spell keeps its worth through a
location. Cleanse answers a curse after it lands. Smite and Frozen Orb stop one before it
lands. Reading the leaders' minds (Tab) and the chant's telegraph tells the player which one is
worth the mana.

## Leaders against the new tools

- A **warded** tower (Salvation) cannot be cursed. The planner leaves it out of its candidates
  while the ward will outlast the chant, and a curse that reaches one breaks on the ward.
- A leader that is **smitten or frozen** mid-chant loses the curse and waits its whole
  cooldown again. A frozen leader cannot start a chant.
- The planner's rollouts copy everything the world carries (wards, frozen monsters, burning
  ground, the perks), so a leader already sees what the skills do: that a Thorns gate hurts its
  pack, that a frost tower under Shatter is worth more to break. It does not foresee the
  player's spells, just as it does not foresee cleanses. A leader that curses into a full mana
  orb takes that risk.
- Difficulty makes leaders quicker (shorter cooldowns). It never makes them less clever.

## The intro to a location

Before every defence there is one screen. It shows:

- the location's name and a painted strip of its floor;
- two lines in the Bone Priest's voice. He narrates the intro film, and he taunts here, since
  he has seen this fight before;
- **The host:** a card per monster kind, with its painted figure, its life and pace, and its
  resistances in Diablo's words ("Immune to Poison", "Flies over gates");
- **Their leaders:** each leader's card lists its curses, each with its length and what it does
  to a tower ("Bone Prison, 4.5 s: caged, cannot attack"), and how to answer it;
- **Your arsenal:** the towers, gates and spells on offer, with what is new marked;
- the sigils won there so far, and what the next one takes.

Its buttons are **Defend** (Enter), **Skills** (K) and **Back to the map** (Esc).

## Curses you cannot miss

A curse is the leader's move. Today it shows as a thin violet line and a small sigil. It
becomes three beats:

1. **Telegraph** (the chant, 1 s): a violet rune circle opens on the floor under the tower and
   closes as the chant runs out. It is a countdown the player can read and answer with Smite or
   Frozen Orb. The beam is thicker and pulses, and motes stream along it. The leader burns with
   a violet aura, and the chant cue plays.
2. **Landing:** the curse's sigil slams down from three times its size onto the tower, with a
   shockwave ring, a violet flash at the screen's edges and a jolt of the camera. The curse's
   name rises over the tower in large type.
3. **While it lasts,** the curse shows on the tower in its own look. Weaken: the tower bleeds, red
   motes dripping. Decrepify: rust-coloured motes circle it slowly and its shots slow. Dim Vision:
   black smoke hangs over it, and its shrunken reach shows as a dashed ring. Bone Prison: a cage
   of bones closes round it. A small draining ring counts the time left.

Cleanse and Salvation shatter the sigil in holy light.

## The world map

The map is one painted picture of the cut-away, painted the way the title's key art was, with no
words in it. The game draws on top of it: the trail between locations (dotted, lit where
walked), a banner per location with its sigils won (three slots per difficulty), locked
locations in shadow, and the lantern. Choosing a location sends the lantern along the trail
(1–2 s, with footsteps), then opens its intro. The map also holds the difficulty tabs, the
**Skills** button (with the unspent sigils on it) and the way back to the title.

Progress (the sigils per location and difficulty, the learned skills, where the lantern stands)
is saved in `~/.hellward/saves` after every change.

## Tuning by simulation

The locations and difficulties are tuned by playing them with **strong scripted players**. The
yardstick is how the best of them fares, not the ordinary scripted defender of the demo.

- **The players** (`hellward/sim/players/`). Several strategies are written independently by
  sub-agents and compete, each aiming to be the strongest. A player sees what a human sees: the
  intro's roster, the map, the gold, the mana, the leaders' chants. It chooses its skills for
  the location, places and upgrades towers, builds gates and casts every spell (Smite at a
  chanting leader, Frozen Orb at a breaking gate, Meteor at a queue, Cleanse on the tower that
  matters). It may plan a location's build by simulating it offline, as a player who has
  replayed the location many times has in effect done. At 18 sigils per difficulty that is a
  ceiling on skill, and difficulty is set against the ceiling.
- **Targets.** With the skill points a player would have by then (two sigils per earlier
  location on Normal, 18 on Nightmare, the full tree on Hell):
  - **Normal:** the best player wins every location, with three sigils on Tristram and the
    Graveyard and at most two on average from the Cathedral on. The demo's ordinary defender
    loses at least one of the last three locations.
  - **Nightmare:** the best player wins everything, keeping about half the sanctuary's life on
    Hell's Gate.
  - **Hell:** the best player with the whole tree wins Hell's Gate on some seeds, not all, and
    keeps fewer than half the lives when it does.

  Tristram and the Graveyard may be easy: they teach.
- **The knobs** are per location (the waves, their life multiplier, the starting gold) and per
  difficulty (monster life, the leaders' cooldown). `tools/campaign_balance.py` plays every
  player on every location and difficulty over several seeds and prints the table the targets
  are read from. The table goes into this page with the commit that tunes.
- **Speed.** A whole defence against rollout leaders costs about 3.6 s of processor time today,
  and nearly all of it is the rollouts. As Warband does (`warband/league/fastsim.py`), the
  simulation (`sim/`) is compiled with mypyc into `build/fastsim/<source hash>`. The source stays
  the reference, a test holds the compiled defence to the same result as the source's, and the
  tools activate the build and hand it to their worker processes. The heavy runs go through
  `~/saga/tools/slot.py`.

## Screens

Title → **Descend** → world map ↔ skill tree; world map → (the lantern travels) → intro →
defence → reckoning (sigils won, what was learned) → world map. The title's **Watch the leaders
at work** plays the Cathedral with the strongest scripted player.
