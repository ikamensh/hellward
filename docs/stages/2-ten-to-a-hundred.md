# Stage 2 — Ten to a hundred, on scarce ground

The second readiness stage ([design-choices.md](../design-choices.md) section 20): the design's number scale,
shorter locations, maps where good ground is scarce, cell worth while placing, and the Kit that stage 3's runs
build on. It ships as a release Ilya plays, after stage 1. The maps' measurements and decisions are in
[2-maps-analysis.md](2-maps-analysis.md).

## Rules

### Numbers (G2.4, G3.4)

- **Life:** a role-1 monster has 10 life at Tristram's first wave (`economy.base_hp = 10`). Life grows ×1.16 per
  location (`economy.life_growth`, which replaces `location_growth` for life and spell power) and ×1.05 per wave.
- **Roles are compressed** so that no ordinary monster at the Temple exceeds 200 and the median sits in 60–120:
  - the Hulk at about 2.9, the Overlord about 2.6;
  - leaders 1.8–2.2;
  - Azazel about 16 (about 440 life at Hell's Gate), the Bone Priest about 12 (about 860 at the Temple).
- **Prices do not grow:** the gold unit is `economy.base_gold_unit` at every location, so a rank-I Arrow costs 12
  everywhere.
- **Income grows** ×1.12 per location (`economy.income_growth`), on top of the per-wave growth within a location.
  Starting gold per location stays as a stipend until stage 3 carries gold.
- **Per-location factors:** each location keeps one life factor in `campaign.toml`, the result of tuning (it starts
  at 1). The curve itself lives in `economy.toml`.
- **The power table** (`tools/scorecard.py`, G3.4): at each location, the last wave's monster life per second
  arriving on the field, against the damage per second of the strongest bot's board at that location, with no
  charges or relics.

### Waves (G2.1)

- Every location has **four to six waves**, at most 30 bodies a wave:
  - Act I: Tristram 4, the Graveyard and the Cathedral 5, the Catacombs, the Caves and Hell's Gate 5–6;
  - Act II: 5–6.
- Rosters escalate by kind, not by count. Late locations bring faster kinds (Flayers, Blood Bats, Spiders) and more
  armored ones, rather than more bodies.
- **Every route a location's map draws is walked** by some wave: wanderers from its entrance, or the route is
  deleted.
- Breaches stay as they are until stage 3's bonus waves.

### Ground (R1–R3, R5)

**Each map is re-designed by hand** to the decisions in 2-maps-analysis.md:
- at least 40% of the ground beside the halls is occupied, weighted by worth;
- at most 12 prime cells;
- prime cells clustered near chokes;
- each entrance keeps a good cell.

The geometry may change: shorter shared stretches, islands, narrower halls at chokes.

**Terrain** has two kinds:
- **Rock** (today's pillar tile): clusters of boulders, ruins, collapsed walls.
- **Water** (today's pool tile): ponds by the kept clusters.

**Rubble:** up to three rock cells per map.
- During a break, `clear` turns one into floor for 1, 2, then 3 gold units (the next costs more).
- Event: `cleared_rubble`.
- Order: `clear` with a tile.

**Cell worth:**
- `tools/maps.py`'s `cell_worth` moves into the simulation (`hellward/sim/level.py` or a sibling module). It stays a
  pure function of the level and the location's waves.
- The battle's start sends each buildable cell's worth.

**Upgrades (R3):** rank prices are set so that, at each location's armor mix, ranks II and III buy less damage per
gold than another rank-I tower and more per cell. The scorecard checks every attacking kind.

### The Kit

- `hellward.sim.kit.Kit` is a frozen dataclass: everything a defence starts from.
  - The location key, the learned skills, the loadout, starting gold, sanctuary lives and the seed.
  - Empty slots for stage 3's relics and carried counters.
- `World(kit, planner=...)` replaces today's keyword arguments.
- A replay is a Kit plus the order log.
- The server, the scripted players' `defend`, and the tools build Worlds from Kits.

## The wire and the client

- **The battle's start:**
  - the per-cell worth;
  - the rubble cells and their clearing prices.
- **Orders and events:** `clear`; `cleared_rubble`.
- **While placing a tower,** the client tints every buildable cell by its worth, prime cells outlined, and shows the
  number on hover.
- **The terrain looks like what it is:**
  - rock clusters as boulders, ruins or a collapsed wall, in the location's theme;
  - water as ponds;
  - rubble visibly clearable, with its price.

## Bots and tuning

- **Plans:** the scripted players' searched plans (`players/plans/*.json`) are re-searched once, after the waves and
  maps settle (`tools/plan_player.py plan all`, `tools/warden_plans.py`, through slot.py).
- **Life factors:** each location's factor is tuned with `tools/margin.py`:
  - the strongest bot wins every location with margin 1.1–1.3;
  - the veteran wins Act I's first two.
- The before and after of `tools/balance.py` and `tools/curse_quality.py` go in the commit.

## Exit criteria

**Scorecard:**
- **G2.1:** ≤ 30 bodies a wave, and p99 ≤ 25 alive at once (from bot runs).
- **G2.2:** median ≤ 10 towers.
- **G2.4:** every number target.
- **G3.4:** the power table closes at every location.
- **R1, R3, R5** met on every map.

**Tests:**
- the Kit round-trip (a World from a Kit, replayed, gives the same events);
- clearing rubble (price, break only, refusal);
- cell worth's properties;
- the compiled simulation equals the source;
- the server equals `hands.defend`;
- `godot/tools/test.sh`.

**Ilya sees:**
- Tristram's 10-life Fallen;
- the Temple's 60–120 host;
- each map's worth heatmap while placing;
- rubble being cleared;
- the power table as a chart.
