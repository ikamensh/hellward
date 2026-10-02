# Hellward — the campaign

Two acts of six locations take the lamp from Tristram below the cathedral and across the sea to Kurast. [One defence](design.md) describes combat and the leaders' planner; [the story](story.md) gives the cast, pages and ending.

This campaign began as six compact locations, then gained a second act, area curses, ranks and a story after Ilya cleared the first version untouched. The current redesign makes its opening deliberately small and its growth slow. Direct damage, area damage, and resources for this fight compete with investments for later fights.

## Shape and progression

Each location opens after the previous one is held. Victories earn one, two or three sigils by sanctuary life left: at least 1, 10 or 18 of 20. Only an improvement over that location's best result adds sigils. A perfect campaign yields 36; the nine-column skill tree costs 63. Skills can be reset freely, but later skills stay locked until their location opens.

A location has 5–8 waves on a 33 × 18 map. Walkable monster halls are roughly three tiles wide around their route centerlines and branch into loops around buildable tower islands. Monster routes never cross tower plots. Tristram has one entrance and three routes. Every later location has two ordinary entrances, each with a direct route and a longer loop. From the Graveyard onward, one arch may hold a gate; a route through another hall bypasses it. The six breach locations have a third, sealed entrance that opens only by choice.

| # | Location | New usable power | Area damage |
|---:|---|---|---|
| 1 | Tristram | Arrow Tower, Smite | None |
| 2 | Graveyard | Gate, Battle Hymn, first breach | None |
| 3 | Cathedral | Single-target Pyre | None |
| 4 | Catacombs | Single-target Frost, Ballista; breach | None |
| 5 | Caves | Single-target Plague | None |
| 6 | Hell's Gate | Single-target Storm; breach | None |
| 7 | Kurast Docks | Bone Altar, Hook Tower, Knife Post; a saved three-trophy Blast Chamber can first be forged | Optional rank-III Pyre blast |
| 8 | Spider Forest | Druid Grove; breach | Optional forged blast |
| 9 | Flayer Jungle | Frozen Orb; Fire Ball and Shatter skills unlock | Trophy-free burst route |
| 10 | Drowned City | Chain Lightning and Corpse Explosion skills; Forked Coil can open; breach | Additional invested routes |
| 11 | Travincal | Meteor; Execution Bow can open | Spell, or stronger single target |
| 12 | Temple of Light | Final breach and the Bone Priest | Build-dependent |

Offering a tower does not grant its upgrades. A learned rank still costs battle gold. Pyre's ordinary ranks remain single-target; Storm's ordinary ranks have no jumps; Frost chills one enemy until its late burst skill. The opening has no damaging area attack.

## The common combat scale and gold

`sim/balance.py` is the starting point for global tuning. Every hit is a whole number: it goes through the damage pipeline of [one defence](design.md) (factors capped at ×2, rounded toward them, less armor, at least 1), so a tag always moves a hit by at least one and armor makes heavy hits count. Base enemy life is 6, multiplied by its role, `1.055 ^ location_index`, `1.05 ^ wave_index`, and any exceptional encounter factor. The first Fallen has 6 life and a rank-I Arrow hits for 2. Arrow ranks hit for 2, 3 and 4. Rank-I Arrow costs 12 in Tristram. Local gold units rise at the same 5.5% location rate; starting gold is three units in Tristram (36 gold) and adds half a unit per later location to cover more entrances. A wave's kills and clear bonus together pay `1 + 0.5 × wave_index` local Arrow-price units, starting at one unit and reaching three by Tristram's fifth wave. The old area-focused swarm counts scale by `max(0.4, 1 / (1 + 0.5 × max(location_index − 1, 0)))`, preserving the authored mix while making single-target defence viable.

A wave has one gold budget, with a share divided across its monsters and the rest paid on clearing it. Enemy type weights affect each kill's share, but adding bodies does not multiply total income. Leaked monsters forfeit their kill gold. Tower prices are role ratios of the local unit. At the Tristram price scale, rank-I values are 12 for Arrow and Knife Post, 18 for Pyre, Plague, Ballista and Hook Tower, 17 for Frost, 20 for Storm, and 19 for either support tower; later locations actually offer those other families. Upgrading buys less felt damage per gold than another rank-I tower at every location's armor and element mix, but more per cell (`tools/scorecard.py`, R3): Pyre ranks hit 3/4/5, Storm 3/4/6 at 1.2/1.3/1.3 a second, the Frost Shrine's ranks deepen its chill rather than its hit of 1, and the Plague Totem's venom grows 1/1.5/2 a second a stack. The Hook Tower's ranks buy pulls, not damage. Rank prices follow the same three-rank profile and rise with location. A gate starts at the local Arrow price and base 70 life before local and skill scaling.

Smite deals six base holy damage, scaling with location life, through any armor or protection: enough to finish a stray, or a leader before its curse lands. It costs 35 mana and needs time before another cast. Battle Hymn, from the Graveyard, costs 40 mana and makes one tower attack twice as fast for 6 seconds; it gathers itself for 15. Frozen Orb, at 50 mana, opens in the Jungle; Meteor, at 60, opens in Travincal. No spell lifts a curse or breaks a chant. Mana starts at 60, holds 100, and regenerates at 1.5 per second before skills.

The pace of power is intentional: buying an immediate Arrow or selling salvage can save this wave, while reserving sigils, salvage and trophies unlocks stronger ranks or a pattern later. Strong single-target builds remain possible without any trophy.

## Curses and their answers

Every curse lands on a spot and catches the towers within its radius. Selling the tower under a pending sign does not remove the spot, and a cursed tower cannot be sold. A chant or a mark fizzles if its leader dies before it lands; nothing else stops it, and nothing lifts a curse that has landed.

| Curse | Common leaders | Lasts | Radius | Effect |
|---|---|---:|---:|---|
| Weaken | Shaman, Witch, Inquisitor | 8 s | 1.5 | Tower damage × 0.35 |
| Decrepify | Witch | 8 s | 1.5 | Attack rate × 0.4 |
| Dim Vision | Acolyte, Inquisitor | 8 s | 2.3 | Reach × 0.55 |
| Bone Prison | Acolyte | 4.5 s | 1.0 | Tower cannot attack |

The Bone Priest knows all four curses, casts from farther away, and widens them by one tile. A curse of his that lands burns 5 mana per tower caught. The Inquisitor marks its spot for 1.5 seconds instead of chanting. The leaders' planner sees a hymned tower at its hymned rate, so the boost draws their curses. Spacing reduces shared curses but may sacrifice overlapping tower reach. A Grove rewards clustering, making that tradeoff sharper.

## Sigils and skills

A skill needs the one above it in its column. Steel has two rank skills costing 2 and 3 sigils, which raise every physical tower. Each of the six other tower columns costs 1, 2, 2 and 3; Warding costs 1 and 3, Sorcery 1, 2 and 3. The whole tree costs 63 sigils, so a perfect campaign still requires choices.

| Column | Skill order and effects |
|---|---|
| Steel | Adept of Steel (rank II), Master of Steel (rank III): Arrow, Ballista, Hook Tower and Knife Post |
| Fire | Adept (rank II), Master (rank III), Fire Ball (Pyre blast, opens in Jungle), Blaze (burning floor) |
| Lightning | Adept, Master, Static Field (leaders first), Chain Lightning (one jump, opens in Drowned City) |
| Cold | Adept, Glacial Spike (+0.4 reach and +50% hit), Master, Shatter (bolt burst and chilled-death burst, opens in Jungle) |
| Poison | Adept, Master, Lower Resist (a poisoned monster loses its protections), Contagion (venom spreads on death, opens in Jungle) |
| Bone | Adept, Master, Life Tap (amplified kills give mana), Corpse Explosion (amplified deaths burst, opens in Drowned City) |
| Nature | Adept, Hurricane (nearby walkers slow 20%), Master, Twister (periodic root of a front walker) |
| Warding | Holy Shield (stronger, fully mending gates), Thorns (gates return half a blow) |
| Sorcery | Warmth (faster, larger mana pool), Soul Harvest (leader-kill mana), Spell Mastery (every spell cheaper, Smite, Meteor and Frozen Orb stronger) |

Shatter and Corpse Explosion do not chain from deaths caused by their own burst. Twister cannot root flyers or monsters worth at least two lives. Skills can be reset between defences; forged patterns are a separate, permanent purchase.

## Salvage, breaches and forged patterns

A seeded sample of up to three ordinary spawns in a defence carries salvage. Their kills give gold immediately and drop one salvage each; a leak loses that drop. During a wave break, one held salvage can be sold for about one-third of a local Arrow price in battle gold. Unsold salvage is banked only after victory. The campaign stores each location's best unsold victory haul and credits only the improvement on a replay, so repeating an easy fight cannot farm unlimited materials.

At six authored breaks, the player may leave a sealed entrance shut or open it for a **cash** or **trophy** reward. Its named elite and unusual pack join the next ordinary wave from that entrance. The pack's kills share an extra half-unit of local battle gold. Any side enemy leaking voids the side reward. A cash cache of about 0.8 local units pays as soon as the full pack is cleared; it can help finish the current defence. A trophy is permanent only if the pack clears and the whole defence is won. The first victorious clear of the side pack fixes that site's permanent choice: choosing cash gives up its one trophy, though later replays can still choose run-only cash. Declining or losing leaves the permanent choice open for a later attempt.

| Site | Offer after wave | Side challenge |
|---|---:|---|
| Graveyard — Ash Crypt | 2 | Ashwing, a fast gate-bypassing gargoyle with Fallen |
| Catacombs — Iron Ossuary | 3 | Door Eater, a hulk with skeletons |
| Hell's Gate — Red Kennel | 4 | Blood Caller, a Flayer-raising Fetish Shaman |
| Spider Forest — Root Pit | 3 | Rootbreaker, a hulk with drowned walkers |
| Drowned City — Bell Tower | 4 | Saltwing, a fast gargoyle with bats |
| Temple — Lightless Choir | 4 | Last Warden, an overlord with two Inquisitors |

The Forge opens from the briefing. Forging spends banked salvage and any required trophies once; the resulting pattern is permanently owned. At most one owned pattern per tower family can be equipped before a defence, and it modifies all towers of that family for the whole run. Skill ranks still unlock and cost gold independently.

| Pattern | First available | Cost | Tradeoff |
|---|---|---|---|
| Honed String (Arrow) | Graveyard | 3 salvage | +1 hit at every rank: quick, flat return |
| Laminated Limbs (Arrow) | Graveyard | 6 salvage | +0/+1/+2 by rank: weak now, stronger after rank investment |
| Blast Chamber (Pyre) | Docks | 8 salvage + 3 trophies | Rank-III blast; requires all three earlier trophies |
| Forked Coil (Storm) | Drowned City | 9 salvage + 2 trophies | One jump at rank III |
| Execution Bow (Arrow) | Travincal | 10 salvage + 2 trophies | Slower shots, later rank damage, and a large leader bonus |

With six trophies in the campaign, buying one large area recipe can deny another. Cash, flat Arrow damage, later skill-based area effects, and boss-focused single-target damage give distinct ways through the acts.

## Towers and enemy roles

The Bone Altar amplifies the thickest knot of enemies in reach without dealing damage itself. Its ranks add +15%, +20% and +25% damage taken for 2–2.5 seconds, pulsing every 4.0–3.2 seconds: a factor of each hit, under the ×2 cap. Weaken lowers the bonus; Decrepify slows pulses; Dim Vision cuts reach; Bone Prison stops it.

The Druid Grove gives nearby towers the best available aura, without stacking. Its ranks lend +10%, +15% and +20% damage within 1.5, 1.5 and 2.3 tiles. Weaken lowers that bonus and Bone Prison disables it. Its pull toward clustering competes with area curses.

Ordinary Act II roles keep different defenses and movement on the smaller scale. Multiply each role factor below by the profile's `base_hp`, then by location and wave growth; gold bounty in a battle comes from the wave budget, not a fixed per-species price.

| Enemy | Life factor | Pace | Role |
|---|---:|---:|---|
| Flayer | 0.85 | 1.45 | Direct runner, protected against fire; a Fetish Shaman can raise it once at half life |
| Zealot | 1.8 | 1.0 | Direct, armor 2, protected against lightning, vulnerable to fire |
| Spider | 1.4 | 1.35 | Wanders, protected against poison, vulnerable to cold |
| Blood Bat | 0.8 | 1.9 | Direct flyer, passes gates, protected against cold and poison |
| Thorned Hulk | 5.0 | 0.55 | Wandering gatebreaker, two sanctuary lives, armor 3, protected against poison, vulnerable to fire |
| Drowned | 2.2 | 0.7 | Wanders, protected against cold, vulnerable to lightning |

A Fetish Shaman raises a nearby dead Flayer once unless a burst leaves nothing to raise. An Inquisitor's curse arrives as a visible mark, burning on its spot longer than a chant. The Bone Priest is the Temple's boss: life factor 24 (144 before location and wave growth at the current profile), armor 3 and protected against every element, 5 lives a strike at the shrine, after which he is struck back to his portal to walk again, four curses with wider reach, and mana burn per caught tower.

## Locations

Each map keeps its theme and story in a distinct network of halls and tower plots. A gate covers only the routes that cross its single arch; other halls may bypass it. The side entrance changes approach direction, and a breach adds an optional third threat on six maps.

**Act I — The Descent**

| Location | Host and lesson |
|---|---|
| Tristram | Fallen and zombies, then Shamans. Spread the opening Arrows against area curses. |
| Graveyard | Skeletons and zombies approach from two roads. An Acolyte teaches gates, and that a hymned tower draws the curses. |
| Cathedral | Fallen, goatmen, skeletons and Witches split between two aisles; cover both before buying fire. |
| Catacombs | Skeletons, zombies, Overlords and Acolytes meet in an open ossuary; the Overlords' armor halves an arrow and barely dents a Ballista's bolt. |
| Caves | Goatmen and flying Gargoyles cross between lava pools; wings ignore the arch. |
| Hell's Gate | The Act I roster and all three early leaders culminate in Azazel, armored, protected against every element, and struck back from the shrine to walk again. |

**Act II — The Drowned Temples**

| Location | Host and lesson |
|---|---|
| Kurast Docks | Flayers, Zealots and Fetish Shamans cross open piers; hooks drag Flayers back under the towers, knives make the gate a kill zone. |
| Spider Forest | Venom-protected spiders, bats and Flayers; Groves tempt clustering despite curses. |
| Flayer Jungle | Flayers, Zealots, spiders and Inquisitors; kill a mark's source before it lands. |
| Drowned City | Drowned, Hulks and bats arrive from streets across narrow canals; cold is a poor sole answer. |
| Travincal | The High Council gathers leaders and swarms from multiple approaches. |
| Temple of Light | The Bone Priest's widened curses and mana burn test the player's chosen build. |

Act I descends in reds and brown stone. Act II moves through piers, webs, jungle, black water and gilt toward the mother lamp. Every location has its own intro, wave names, taunt and terrain theme.

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

## Tuning and verification

The earlier six-location and twelve-location tuning tables were measured before this low-number, branching-hall economy. Their life factors, bot margins, planner gains and timing figures no longer describe the current rules. The common profile supplies the starting curve; authored roles, wave compositions, entrances and optional packs were checked with an eight-seed earned-sigil campaign after the corridor revision. The [redesign notes](redesign.md#earned-sigil-campaign-on-the-corridor-maps) summarize that result, including the tight Temple finale and the current planner-latency limit.

Each location's life is its growth times a factor in `hellward/sim/data/campaign.toml`, tuned with `tools/margin.py`
after stage 1's rules (2026-10-02, evaluation seeds 1000-1007, smart leaders): the strongest bot wins every location
and the veteran every location of Act I, each with its worst seed at a margin of at least 1.0. The factors are 1.0
but for the Graveyard 0.76, the Cathedral 0.61 and Hell's Gate 0.80 (where the veteran, drafting from the intro,
lost before them; it already lost the Cathedral at 0.49 before stage 1, while the planned player holds it at 2.6),
the Catacombs 1.5 and Kurast Docks 1.07 (where an Arrow-only build now loses and one with Ballistas for the same gold
wins, `tools/armor_ab.py`, M9), and Travincal 0.86 (the planned player's worst seed). Margins, median (veteran in
Act I; the better of the planned and adaptive players everywhere, measured with the Graveyard at 0.78, Hell's Gate at
0.82 and Travincal at 0.91, a shade harder): Tristram 1.28 / 1.39, Graveyard 1.19 / 2.07, Cathedral 1.11 / 2.58,
Catacombs 1.12 / 2.31, Caves 1.61 / 1.80, Hell's Gate 1.23 / 1.57; Docks 1.63, Spider Forest 2.26, Jungle 1.73,
Drowned City 1.91, Travincal 1.17 (at 0.86), Temple 1.43. Ballistas fill the
searched builds from the Catacombs on: the armor answer is also the strongest general tower at these numbers.

`tools/balance.py` compares leader policies and defenders, `tools/curse_quality.py` measures the curse planner, `tools/campaign_balance.py` follows progression, and `tools/margin.py` estimates spare difficulty. The source simulation and mypyc build should agree on events, rewards and outcomes for the same seed, including a breach and a forged loadout. Tests cover route geometry, clone determinism, rewards and replayed commands. Record each balance result with its profile and command so later curve changes remain comparable.

The original tuning still taught useful rules: a broken gate remains rubble until a break; a spell recharges after casting; and spells grow with location and wave, rather than an arbitrary hardship multiplier. These mechanics remain in the game. Stage 1 ([its spec](stages/1-armor-and-pirates.md)) took Cleanse, wards, Salvation and chant interrupts out: no spell lifts, prevents or breaks a curse.

## Screens

Title → prologue (first time) → world map (act tabs) ↔ skill tree → lantern travel → story page (first arrival) → briefing ↔ Forge → defence → reckoning → story page (first victory) → world map. The act ending follows its last fight.

The briefing shows the lesson, roster, available towers and spells, and a Forge button. During a defence, the HUD shows held salvage and offers a sale during breaks. At an offered breach it shows the sealed entrance, named threat and the cash, trophy and decline choices. The chronicle shows leaders' curse decisions. Reckoning applies best-result sigils, any improved unsold salvage and an earned trophy together on victory.
