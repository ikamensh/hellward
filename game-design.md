
Hellward - TD but different

1) no grind; since we have efficient sim, we should be able to predict that player definitely kills a wave with no losses. When we do, we offer them to skip the grind and give a small bonus for that, we should show some visuals to make this still juicy, aka the vision of dark god how his minions die (change lighting of level, show just snappy/partial animation of what happened in sim).

2) Not bullet hell, not numbers infinitum. Amount of monsters, towers and their levels is kept reasonably low by game balance. Progression is getting more options and tools, and modestly improving stats of some of your towers. Plus unlocking tower control AI modes which makes them more efficient.

3) Hard difficulty, but if a player is great they can accumulate advantage fast across levels, i.e. bonus waves player can control can make them fabulously rich, even if its very hard to do.


Meta-progression:

for some things that we want to let player accumulate and "get all of them", e.g. AI strategies for their towers, we could have in-game currency and shop, since it just adds up from their runs. 

Others, which are more like mutually exclusive choices we can use equivalents of skill points. Since we took style of diablo, we can take diablos experience bar and level up jolly. We can add up sigil points on top of it (your skill points are sigils + your level), but I'd want to make sigils a bit more varied - 3 for excellence on lives, 3 on extra level goals that are about how you pass it.

On tech trees: we can make a lot of different kinds of towers, but way to expensive for player to open all of them (paying skill points, not gold). Then different runs would combine different towers and see what are their synergies. Player might get struck by leveling into something that doesn't really synergize.

We can compliment this system by player winning relics, that like in slay the spire augment some random mechanics in unique ways. This would again shape the run outside of players control, forcing them to adapt and not just follow known best synergy, because their unique combo of relics forces them into different mechanics. To foster this half of our towers could be mechanics towers (maybe no towers at all them, moon wells and druid trees?..) What could be equivalent of the unique fun mechanics of drawing, exiling, debuffing (ok this one present) on which we could trigger things? (Answered as principles in **Verbs** below.)

So lets say our basic towers are all just shooting fire bolt / ice bolt / single target lightning. They keep doing that. Now we can introduce either 1) much more expensive towers that do next level thing (fireball, firewall, frost nova, chain lightning) or we can have an upgrade per tower that gives it some charges e.g. max 3 charges, recharge every 15 sec. Would be cool if we could sell AI mode that predicts when its worth to lose a charge and when to keep it since current mobs will die downstream anyway. Again, the progression should be very slow, start of the game we start with numbers like 10 life monster, 1-2 dmg tower, I want to end the game with 100 life, smarter faster monsters, not 10k life. Accordingly our skills don't give terribly much abs numbers.

We should have absolute armor (damage reduction) because it quickly makes it interesting to choose DPS vs heavy hitting towers. We can play with how not to overwhelm player with number of unique params. But absolute armor makes for interesting situations where at some point you must have something heavy hitting or you suddenly fall behind.

Bosses: we can make it so that any mob that passes attacks our holy shrine. Normal mobs get obliterated on hitting it (different visual than before - attack and getting destroyed, same math), bosses are just sent back as they are to the portal, so they need to pass again to hit again.

Global spells:
a small bit of action rpg and direct action to keep player from sleeping. Remove curse dispel, this makes it grindy to click around urgently dispelling curses. Keep global spells mostly a way to kill 1-2 stray mobes when you got unlucky with tower targeting.

we can also allow spells that significantly boost towers, but this should be fragile because smart curse AI will likely disable a boosted tower. A nice interaction.

## Verbs: what mechanics and relics trigger on

Relics and mechanics towers hook on verbs: events in the player's own engine, as Slay the Spire's hook on drawing
and exhausting. Damage is not a verb.

- A verb happens a handful to a few dozen times a wave, and every occurrence is visible on the field.
- The player sets how often it happens, through the build and where towers stand.
- Leaning into a verb costs something; a relic's job is to turn that cost into the payoff.
- The set stays small, around five. Each verb is one concept, learned once. Each mechanics tower produces or
  consumes one verb.
- Most relics read one verb and write another. A few verbs then give many relics without new concepts, and a
  converter can join two engines that a run levelled into separately.
- Consuming a debuff can be a verb. 
- A new mechanic per relic is not wanted, relics interact with existing ones
- some relics can enable you to use tech you would not have access to otherwise. Many relics come with downsides too.
- No chance procs. A relic fires on a count ("once every 10 attacks") or other predictable condition (last hit two monsters over last minute)
  when it lands. Simple counter relics are fine; a relic does not have to be clever.

## Real estate

The map is a resource: where a tower stands matters as much as what it is.

- Good cells are scarce by map design. Many cells start occupied (rock, water, ...). A cell is worth what it reaches
  of the routes.
- Upgrading buys less power per gold than building another tower, but more power per cell. Rank is how a player gets
  more out of a prime cell; more towers is how they spend gold efficiently on poor ones.
- Scarcity keeps the tower count low without a hard cap.
- Scarcity and area curses pull against each other: the best cells sit together near chokes, and leaders punish
  towers that sit together.
- The map changes during a defence: monsters can take cells away from later building. An enemy's action on the map
  follows the rule of curses: visible before it lands.
- A change to a cell shows on the cell, with how long it lasts.

Specific ideas toward these principles, not yet decided: [docs/mechanics-ideas.md](docs/mechanics-ideas.md).
