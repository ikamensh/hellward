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
ground under Tristram**, and depth follows the order of play. Tristram and its churchyard lie on
the surface. The Cathedral's labyrinth is the first level under the church, as in Diablo. The
catacombs, the caves and hell's gate lie below it. The party is a lantern. It walks a lit trail
from one location to the next, zigzagging down.

```
   Tristram (1) ── The Graveyard (2)            surface
                          │
                  The Cathedral (3)             under the church
                  ╱
   The Catacombs (4)                            deeper
                  ╲
                   The Caves (5)
                          │
                   Hell's Gate (6)              the bottom
```

The descent is linear. Each location opens when the one before it is held, and each one brings
exactly one new thing (a table below), so every intro has something to announce.

**Difficulties:** **Normal**, and **Hell**, which opens once Hell's Gate falls on Normal. Hell
plays the same six locations with stronger monsters and quicker leaders, and the skill tree
carries over. Normal earns at most 18 sigils and Hell 18 more, which is exactly the tree's price.
(Diablo's Nightmare between them would triple the tuning for little. It can come later as a
plain multiplier.)

## Locations

Every location is one 25 × 14 map with its own path, look and wave list: five to eight waves
of two to four monster kinds and one or two kinds of leader. Each location is built around the
content it introduces, so that piece decides the fight there.

| # | Location | Monsters | Leaders (curses) | New for the player | What it teaches |
|---|---|---|---|---|---|
| 1 | **Tristram**, the burning village | Fallen, Zombie | Fallen Shaman (Weaken) | Pyre, Frost Shrine; Cleanse | Fire bursts the Fallen swarm and burns zombies half again as hard. Frost holds them in the fire. A shaman's Weaken cuts your best tower to a third until you cleanse it. |
| 2 | **The Graveyard** | Skeleton, Zombie | Bone Priest (Bone Prison, Dim Vision) | Storm Obelisk, warded gates; Smite | Crypt gates hold the dead in a queue under your fire, and lightning leaps along a queue. Skeletons shrug off a quarter of your cold. Smite a priest as it ponders or chants and the curse never comes. |
| 3 | **The Cathedral** (today's map) | Fallen, Goatman, Skeleton | Fallen Shaman, Blood Witch (Decrepify, Weaken) | Plague Totem; Meteor | Goatmen shrug off lightning, so venom and fire take over, and skeletons shrug off venom. Meteor breaks a queue at a gate. Two kinds of leader. |
| 4 | **The Catacombs** | Skeleton, Zombie, Overlord | Bone Priest, Blood Witch | Frozen Orb | Overlords break gates in seconds. Frost weakens their blows and venom seeks the biggest. Four arches, one behind another. |
| 5 | **The Caves** | Goatman, Gargoyle, Fallen | Blood Witch, Fallen Shaman | the whole arsenal, and the lava floor | Gargoyles fly over every gate, so the answer is reach and lightning, not walls. A lava lake takes the middle of the map. |
| 6 | **Hell's Gate** | Fallen, Goatman, Gargoyle, Overlord, Azazel | all three | — | The one exception to "a few kinds": everything at once, and Azazel, immune to fire, walks behind a council of three leaders. |

What a location offers is fixed by its place in the campaign, not by the save. Tristram always
has the Pyre and the Frost Shrine and nothing else, so a replay is the same puzzle, and the
balance tools measure the fight the player gets. A build slot for something the location does
not offer keeps its place and key, drawn dark with a padlock and a tip ("arrives in the
Graveyard"), so the keys never shift between locations.

**Maps.** Arches stand only on the path's vertical legs, since the gate is drawn facing the
camera. The village road bends once. The graveyard's path folds twice past two crypt arches. The
catacombs' corridor runs down and up the screen with four arches in it. The caves' path loops
round a lava lake. Hell's Gate folds three times and has three arches. Each location has its own
theme (`art/mapart.py`: floor, path and wall colours, lights, the painter's words) and its own
floor, painted over its stand-in the way the cathedral floor was. Only the cathedral keeps
standing pillars; elsewhere obstacles and pits (gravestones, bone heaps, rocks, lava) are painted
flat into the floor. Tristram is painted first, and the others follow once its overlay checks
out.

## Meta-progression: sigils and the skill tree

A victory earns **sigils** by the sanctuary's life left: one for holding, two for keeping 10 of
20, three for keeping 18. A location's best result counts on each difficulty, so the campaign
holds 18 sigils on Normal and 36 in all. Every sigil is a skill point.

The **skill tree** has six columns of three skills. A skill needs the one above it. The three
tiers cost 1, 2 and 3 sigils, so the whole tree costs 36. Normal buys at most half of it and Hell
the rest. **Unlearning is free** (Akara's blessing), from the map or a location's intro, so a
player can reshape the tree for the location ahead once its intro shows who is coming. The tree
greys the columns whose tower the location does not offer, and the intro warns about sigils
spent on them.

| Column | 1 (1 sigil) | 2 (2 sigils) | 3 (3 sigils) |
|---|---|---|---|
| **Fire** (Pyre) | Fire Mastery: 25% more damage | Fire Ball: the first rank bursts too, every blast 0.3 wider | Blaze: fireballs leave the ground burning for 2 s |
| **Lightning** (Storm Obelisk) | Lightning Mastery: 25% more damage | Chain Lightning: one more leap at every rank, leaps keep 95% | Static Field: lightning strikes leaders first, and leaps to them first |
| **Cold** (Frost Shrine) | Cold Mastery: chills 10 points deeper and 30% longer | Glacial Spike: novas reach 0.4 further and hit 50% harder | Shatter: a monster that dies chilled bursts for a tenth of its life around it (a burst does not set off another) |
| **Poison** (Plague Totem) | Poison Mastery: venom 30% stronger | Contagion: a poisoned monster's venom jumps to its neighbour when it dies | Lower Resist: a poisoned monster resists everything 25 points less (immunities hold) |
| **Warding** (gates, curses) | Holy Shield: gates have 50% more life and mend fully between waves | Salvation: Cleanse costs 25 and wards the tower against curses for 8 s | Thorns: a gate returns half of each blow to whoever strikes it (frost does not soften it) |
| **Sorcery** (mana, spells) | Warmth: mana flows 40% faster, 25 more at most | Soul Harvest: a slain leader gives 10 mana | Spell Mastery: Smite, Meteor and Frozen Orb cost 25% less and strike 30% harder |

Each skill is one change to a number or a rule of the simulation, which works out every
modifier once when a defence begins (`sim/skills.py` → `Perks`). A skill for a tower the
location does not offer does nothing there, and the intro says so.

## Spells: what mana is for

Mana (the blue orb) fills at 1.5 a second up to 100 and starts at 60, about two casts a wave.
Four spells spend it:

| Spell | Mana | Aim | What it does |
|---|---|---|---|
| **Cleanse** | 35 | a tower | Burns every curse off it: **C**, or the button on a selected tower. |
| **Smite** | 30 | a monster | Holy lightning from the vault: 100 damage, which no resistance reduces. A leader it strikes while pondering or chanting loses its curse and waits its whole cooldown again. |
| **Meteor** | 60 | the floor | Lands 1.2 s later: 110 fire damage within 1.4 tiles. The floor burns for 3 s after, 12 a second. |
| **Frozen Orb** | 50 | the floor | Everything within 1.8 tiles freezes for 2.5 s: it cannot walk or batter, and a leader's pondering or chant breaks. It also deals 50 cold damage. |

Smite, Meteor and Frozen Orb sit in a bar of three slots on the panel's right (**Q W E**), with
their mana under them the way the towers show their gold. A spell is picked, then aimed with a
click, as a tower is placed; right click or Esc lets go of it. **Q while a leader ponders or
chants smites the one closest to cursing**, with no aiming: that is the answer to the
telegraph, and a player can give it at a glance. Aimed spells are **not cast while paused**:
the leaders' moves are answered in the fight's time, or with Cleanse after they land. Towers can
still be built and upgraded while paused.

Spell damage grows with the wave's life multiplier, so a spell keeps its worth through a
location. The damage is sized so that a spell dents a queue rather than erasing it. Cleanse
answers a curse after it lands; Smite and Frozen Orb stop one before it lands.

## Leaders against the new tools

- A **warded** tower (Salvation) cannot be cursed. The planner leaves it out of its candidates
  while the ward will outlast the chant, and a curse that reaches one breaks on the ward.
- A leader that is **smitten or frozen** while it ponders or chants loses the curse and waits its
  whole cooldown again. A frozen leader cannot start a chant. The window is the half second of
  pondering (the dots) plus the one-second chant.
- The planner's rollouts copy everything the world carries (wards, frozen monsters, burning
  ground, the perks), so a leader already sees what the skills do: that a Thorns gate hurts its
  pack, that a frost tower under Shatter is worth more to break. It does not foresee the
  player's spells, just as it does not foresee cleanses. A leader that curses into a full mana
  orb takes that risk.
- Difficulty makes leaders quicker (shorter cooldowns). It never makes them less clever.

## The design review

Three critics (a tower-defence designer, the planner and tuning method, scope and screens) read
the first draft. This page takes their numbers for the spells and skills (a Meteor, Shatter or
Thorns that erased a gate queue or Azazel at the gate; a Smite that one-shot every shaman), the
human limits on the strong players, the leader-impact target, the linear descent, two
difficulties, arches on vertical legs only, and the panel's layout.

## The intro to a location

Before every defence there is one screen. It shows:

- the location's name and a painted strip of its floor;
- two lines in the Bone Priest's voice. He narrates the intro film, and he taunts here, since
  he has seen this fight before;
- **The host:** a card per monster kind, with its painted figure, its life and pace, and its
  resistances in Diablo's words ("Immune to Poison", "Flies over gates");
- **Their curses:** one row of cards, at most four, each with its length, what it does to a tower
  ("Bone Prison, 4.5 s: caged, cannot attack") and its answer; the leader cards only name the
  curses they cast. A monster's life is its first wave's, on the chosen difficulty;
- **Your arsenal:** a row of small icons for the towers, gates and spells on offer, with only the
  new ones captioned;
- the sigils won there so far, and what the next one takes.

Its buttons are **Defend** (Enter), **Skills** (K, the tree opens over the intro and returns
to it) and **Back to the map** (Esc).

## Curses you cannot miss

A curse is the leader's move. Today it shows as a thin violet line and a small sigil. It
becomes three beats:

1. **Telegraph** (the chant, 1 s): a violet rune circle opens on the floor under the tower and
   closes as the chant runs out. It is a countdown the player can read and answer with Smite or
   Frozen Orb. The beam is thicker and pulses, and motes stream along it. The leader burns with
   a violet aura, and the chant cue plays.
2. **Landing:** the curse's sigil slams down from three times its size onto the tower with a
   shockwave ring, and the curse's name rises over it in large type (the leaders' minds label
   takes its place when minds are shown). The screen's edges flash violet only when the cursed
   tower is the selected one or the dearest on the map: late in the campaign a curse lands every
   few seconds, and neither the flash nor a camera jolt may become noise.
3. **While it lasts,** the curse shows on the tower in its own look. Weaken: the tower bleeds, red
   motes dripping. Decrepify: rust-coloured motes circle it slowly and its shots slow. Dim Vision:
   black smoke hangs over it, and its shrunken reach shows as a dashed ring. Bone Prison: a cage
   of bones, drawn in lines, closes round it. A small draining ring counts the time left.

Cleanse and Salvation shatter the sigil in holy light.

## The world map

The map is one painted picture of the cut-away, with no words in it. It is painted over a
laid-out stand-in (six chambers at fixed places, the way the floors are painted over theirs),
and a half-transparent overlay checks that the painting kept them. The game draws on top of it:
the trail between locations (dotted, lit where walked), a banner per location with the chosen
difficulty's three sigil slots, locked locations in shadow, and the lantern. Choosing a location
sends the lantern along the trail (1–2 s, with footsteps; a click skips it), then opens its
intro. The first **Descend** with no progress walks the lantern straight to Tristram's intro. The
map also holds the difficulty choice, the **Skills** button (with the unspent sigils on it) and
the way back to the title.

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
- **A human's hands.** The strong players play under a shared harness that gives them a human's
  limits: they see a leader's pondering and chant 0.6 s of game time late (drawn per seed
  between 0.5 and 0.8 s), aim where the leader was when they began to react, cast at most one
  aimed spell each half second, and never pause. They may not call the planner or read the
  leaders' decisions: a human sees the dots and the beam, not the leader's mind before it
  speaks. They see the leaders' minds as a human does, from the events after the fact.
- **Seeds.** Offline planning, if a player does any, runs on training seeds 0–99; every number in
  the tables is measured on evaluation seeds 1000–1019. Seeds differ in the monsters' lanes and
  queue places and in the players' reaction times.
- **The margin M** is the continuous measure of difficulty: the largest factor on every
  monster's life at which the best player B* still wins, bisected to 2% and the median over 8
  seeds. B* is the frozen player with the best median lives at a location, with its own skills.
- **Targets**, with the sigils B* has earned by then by playing the campaign in order:
  - **Normal**, Tristram and the Graveyard: wins 20 of 20, median lives ≥ 18, M ≥ 1.5. They
    teach, and may be easy.
  - **Normal**, from the Cathedral on: wins 20 of 20, median lives 10–17, the fewest ≥ 5,
    M 1.10–1.35. The demo's ordinary defender loses at least one of the Catacombs, the Caves
    and Hell's Gate.
  - **Hell**, with the whole tree: Hell's Gate won on 4–12 of 20 seeds, median lives in the
    wins ≤ 9, M 0.97–1.03. Every other location is won on at least 16 of 20.
  - **The leaders matter**, from the Cathedral on, with B* and its build: the lives it loses
    against the smart leaders minus those against random ones (uncapped, as `balance.py` counts
    them) ≥ 3 and ≥ 20% of the lives lost; curse-seconds held on towers per leader ≥ 3; at most
    half of all chants broken.
  - **The planner stays sharp:** `curse_quality.py` share of the best ≥ 0.85 on every location,
    with B*'s skills.
- **The knobs** are per location (the waves, their life multiplier, the starting gold) and per
  difficulty (monster life, the leaders' cooldown). `tools/campaign_balance.py` plays every
  player on every location and difficulty over the seeds and prints the table the targets are
  read from. It records, per run: the player and its commit, source or build hash, location,
  difficulty, seed, reaction time, skills, leader policy, outcome, lives kept and lost, sigils,
  leaks per wave, spells by kind, mana wasted at the cap, chants started, broken and landed,
  curse-seconds held, and the planner's decision times. The players are frozen before a tuning
  pass; a change to a player reruns the table. The table goes into this page with the commit
  that tunes.
- **Speed.** A whole defence against rollout leaders costs 0.3–5 s of processor time from source,
  nearly all of it in the rollouts. As Warband does (`warband/league/fastsim.py`), the simulation
  (`sim/`) is compiled with mypyc into `build/fastsim/<source hash>`, built with
  `-ffp-contract=off` so every float operation rounds as Python's does. The source stays the
  reference: a parity test plays one defence per location with smart leaders from source and
  compiled and compares a digest of every event, and a clone-fidelity test steps a world full of
  meteors, burning floors, frozen monsters, wards and curses beside its clone. The tools activate
  the build and hand it to their worker processes. The heavy runs go through
  `~/saga/tools/slot.py`.

## Screens

Title → **Descend** → world map ↔ skill tree; world map → (the lantern travels) → intro →
defence → reckoning (sigils won, what the next location brings) → world map. The reckoning's
**Again** (Enter) returns to the intro, so the tree can be reshaped before a retry; **To the map**
is Esc. The pause menu offers **Start this defence again** and **To the map**. The title's **Watch
the leaders at work** plays the Cathedral with the strongest scripted player.

**The panel.** The spell slots take the right of the panel where the gold and the buttons were.
The gold moves to the centre panel's heading row. **Pace** and **Menu** become two small buttons
at the top right, over the wall. The **Leaders' minds** button goes: Tab and the settings toggle
the minds.
