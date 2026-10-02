"""The LLM's turn loop: text commands in, text replies out, the fight in between.

A session is a profile's seat at the game: with a
:class:`~hellward.server.campaign.Campaign` it defends open locations, learns
skills and forges patterns, and every decided defence keeps its sigils, salvage
and trophies in the profile. Without one it is a lab: any location, fixed
skills, nothing kept. Either way the current defence runs through the server's
:class:`~hellward.server.battle.Battle` — the same orders, refusals and replay
log as a person's — with the autos' casts logged too, so a logged defence
replays identically.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from hellward.server.battle import Battle
from hellward.server.campaign import Campaign, Refusal
from hellward.sim.campaign import LOCATIONS, sigils
from hellward.sim.content import CURSES, MONSTERS, SPELLS, TOWERS, Curse, felt_hit
from hellward.sim.items import EMPTY_LOADOUT
from hellward.sim.model import SIM_DT, Monster, Planner, Refused, World
from hellward.sim.players.hands import Hands

from hellward.llm import advisor, auto as auto_mod, view
from hellward.llm.auto import Autos

REACT = 1.0        # the LLM answers a leader's sign a second late, like a person
AIM_GAP = 1.0      # seconds between two aimed spells from autos or orders
WAIT_DEFAULT = 4.0  # the digest's beat, in seconds
WAIT_MAX = 30.0
DEFAULT_AUTOS = frozenset({"smite_leader", "smite_leak"})

HELP = """commands (tiles as `x y`):
  map                  the map with towers (T), entrances (E), shrine (S)
  threats              smite targets with their ids
  build <kind> <x> <y> raise a tower
  up <x> <y>           raise a tower's rank
  sell <x> <y>         sell a tower (cursed towers hold)
  gate <n>             ward the nth arch
  call                 start the next wave early for bonus gold
  breach <cash|trophy|decline>
  salvage              sell one held salvage for battle gold
  smite [id]           holy strike (no id: the best target)
  hymn <x> <y>         one tower attacks x2 for 6s (draws curses)
  meteor <x> <y>       fire from the sky (lands 1.2s late)
  orb <x> <y>          freeze a patch solid
  auto [<rule> on|off] reflexes: smite_leader smite_leak hymn meteor orb
  advise <kind> [N]   best N tiles for a tower kind (default 5, max 10)
  advise wave [n]      a wave's mix and the best tower per gold
  advise up <x> <y>    rank this tower or build anew
  wait [seconds]       play on (default 4s) and report the digest
  watch [leaks N]      play to the next break (or N leaked lives) in one digest
  status [towers]      purse, towers (counts; `towers` lists all), next wave
  briefing             repeat the opening briefing
  campaign             the profile: sigils, map, salvage, trophies
  defend <location>    begin that location's defence
  learn <skill>        spend sigils on a skill
  unlearn              take every skill back (free)
  skills [location]    the tree: learned, learnable, costs
  forge [pattern]      the forge, or its one button for a pattern
  profiles             profiles and the current one
  profile <name>       switch profile (a new name starts one)
  quit"""

DECIDED = {"build", "up", "upgrade", "sell", "gate", "call", "breach", "salvage", "smite", "hymn", "meteor",
           "orb"}


def policy_for(leaders: str, seed: int) -> Planner | None:
    """A leader policy by name, as the balance tools name them."""
    from hellward.sim import planner as policies
    if leaders not in ("none", "random", "nearest", "greedy", "smart"):
        raise ValueError(f"leaders is one of none random nearest greedy smart, not {leaders!r}")
    return {"none": None, "random": policies.RandomLeaders(seed), "nearest": policies.nearest,
            "greedy": policies.greedy, "smart": policies.smart}[leaders]


class Session:
    def __init__(self, location: str = "tristram", *, seed: int = 0,
                 skills: frozenset[str] = frozenset(), leaders: str = "smart",
                 autos: set[str] | None = None, campaign: Campaign | None = None,
                 on_events: Callable[[list], None] | None = None) -> None:
        self.campaign = campaign
        # Every event, as defend's watch sees the world's: plain frame lists, raw tuples only for a
        # hands-cast spell's own step.
        self.on_events = on_events
        self.seed = seed
        self.policy = policy_for(leaders, seed)
        self.standalone_skills = skills
        self.enabled = set(autos) if autos is not None else set(DEFAULT_AUTOS)
        self.closed = False
        self.battle: Battle | None = None
        self._counts: Counter = Counter()
        self._curses: list[str] = []
        self._result: dict = {}
        self._defend(location)

    @property
    def world(self) -> World:
        if self.battle is None:
            raise Refused("No defence: `defend <location>` first.")
        return self.battle.world

    @property
    def hands(self) -> Hands:
        if self.battle is None:
            raise Refused("No defence: `defend <location>` first.")
        return self.battle.hands

    @property
    def skills(self) -> frozenset[str]:
        if self.battle is None:
            raise Refused("No defence: `defend <location>` first.")
        return self.battle.learned

    # -- One line in -------------------------------------------------------------------

    def open(self) -> str:
        out = self.briefing()
        return out + "\nauto: " + self._auto_line() + "\n" + view.purse(self.world)

    def briefing(self) -> str:
        return view.briefing(self.world, seed=self.seed, skills=self.skills)

    def do(self, line: str) -> str:
        words = line.replace(",", " ").split()
        if not words:
            return view.purse(self.world)
        verb, args = words[0].lower(), words[1:]
        try:
            if verb == "help":
                return HELP
            if verb == "campaign":
                return self._campaign()
            if verb == "defend":
                return self._defend_cmd(args)
            if verb == "learn":
                return self._learn(args)
            if verb == "unlearn":
                return self._unlearn()
            if verb == "skills":
                return self._skills(args)
            if verb == "forge":
                return self._forge(args)
            if verb == "profiles":
                return self._profiles()
            if verb == "profile":
                return self._profile(args)
            if verb == "briefing":
                return self.briefing()
            if verb == "map":
                return view.map_ascii(self.world)
            if verb == "status":
                if args and args != ["towers"]:
                    raise ValueError("`status` or `status towers`")
                return view.status(self.world, full=bool(args))
            if verb == "threats":
                return view.threats(self.world, smite_damage=self._smite_hits())
            if verb in DECIDED and self.world.outcome is not None:
                return "refused: The defence is decided."
            if verb == "build":
                return self._build(args)
            if verb in ("up", "upgrade"):
                return self._rank(args, up=True)
            if verb == "sell":
                return self._rank(args, up=False)
            if verb == "gate":
                return self._gate(args)
            if verb == "call":
                return self._call()
            if verb == "breach":
                return self._breach(args)
            if verb == "salvage":
                return self._salvage()
            if verb == "smite":
                return self._smite(args)
            if verb == "hymn":
                return self._hymn(args)
            if verb in ("meteor", "orb"):
                return self._ground(verb, args)
            if verb == "auto":
                return self._auto(args)
            if verb == "advise":
                return self._advise(args)
            if verb == "wait":
                return self._wait(args)
            if verb == "watch":
                return self._watch(args)
            if verb == "quit":
                self.closed = True
                return "left the defence."
            return f"unknown command {verb!r} — `help` lists them"
        except Refused as refusal:
            return f"refused: {refusal}"
        except Refusal as refusal:
            return f"refused: {refusal}"
        except (ValueError, KeyError, IndexError) as bad:
            return f"bad {verb}: {bad}"

    # -- The defence -------------------------------------------------------------------

    def _defend(self, location: str) -> Battle:
        """Begin a defence: the profile's, gated by the map, or the lab's free one."""
        if location not in LOCATIONS:
            raise ValueError(f"no location {location!r}")
        if self.campaign is not None:
            battle = self.campaign.defend(location)
        else:
            battle = Battle(LOCATIONS[location], learned=self.standalone_skills, loadout=EMPTY_LOADOUT,
                            seed=self.seed, planner=self.policy)
        battle.hands = Hands(battle.world, REACT, AIM_GAP)   # the LLM's slower hands
        battle.hands.record.skills = battle.learned
        self.battle = battle
        self.autos = Autos(battle.hands, set(self.enabled), battle.commands)
        self._counts.clear()
        self._curses.clear()
        self._result = {}
        return battle

    def _defend_cmd(self, args: list[str]) -> str:
        if len(args) != 1:
            raise ValueError("`defend <location>`")
        self._defend(args[0].lower())
        return self.briefing()

    # -- Orders, through the battle -----------------------------------------------------

    def _order(self, name: str, args: dict[str, Any]) -> None:
        """One battle order: accepted, its frame's events join the digest; refused, its reason."""
        assert self.battle is not None
        why, frame = self.battle.order(name, args)
        if why is not None:
            raise Refused(why)
        assert frame is not None
        self._drain(frame["events"])
        self._result_frame(frame)

    def _tile(self, args: list[str]) -> tuple[int, int]:
        if len(args) != 2:
            raise ValueError("a tile is two numbers: `12 7`")
        return int(args[0]), int(args[1])

    def _tower_on(self, args: list[str]):  # the tower standing on a tile, or a refusal
        tile = self._tile(args)
        tower = self.world.tower_at(tile)
        if tower is None:
            raise Refused(f"No tower stands at {tile[0]},{tile[1]}.")
        return tower

    def _build(self, args: list[str]) -> str:
        if len(args) != 3:
            raise ValueError("`build <kind> <x> <y>`")
        kind = args[0].lower()
        if kind not in TOWERS:
            raise ValueError(f"no tower {kind!r} (offered: {', '.join(self.world.location.arsenal.towers)})")
        tile = (int(args[1]), int(args[2]))
        self._order("build", {"kind": kind, "tile": [tile[0], tile[1]]})
        tower = self.world.tower_at(tile)
        assert tower is not None
        return f"built #{tower.id} {kind} at {tile[0]},{tile[1]} — {view.purse(self.world)}"

    def _rank(self, args: list[str], *, up: bool) -> str:
        tower = self._tower_on(args)
        gold = self.world.gold
        if up:
            self._order("upgrade", {"tower": tower.id})
            return f"#{tower.id} {tower.kind.key} is now rank {tower.level + 1} — {view.purse(self.world)}"
        self._order("sell", {"tower": tower.id})
        return f"sold #{tower.id} {tower.kind.key} for {self.world.gold - gold}g — {view.purse(self.world)}"

    def _gate(self, args: list[str]) -> str:
        if len(args) != 1:
            raise ValueError("`gate <n>` wards the nth arch")
        self._order("gate", {"door": int(args[0])})
        return f"warded arch {args[0]} — {view.purse(self.world)}"

    def _call(self) -> str:
        bonus = self.world.early_call_bonus
        self._order("call_wave", {})
        wave = self.world.wave + 1
        name = self.world.location.wave_names[self.world.wave]
        return f"called w{wave} '{name}' (+{bonus}g) — {view.purse(self.world)}"

    def _breach(self, args: list[str]) -> str:
        if len(args) != 1 or args[0] not in ("cash", "trophy", "decline"):
            raise ValueError("`breach cash|trophy|decline`")
        self._order("breach", {"mode": args[0]})
        return f"breach: {args[0]} — {view.purse(self.world)}"

    def _salvage(self) -> str:
        gold = self.world.gold
        self._order("sell_salvage", {})
        return f"sold salvage for {self.world.gold - gold}g — {view.purse(self.world)}"

    def _smite(self, args: list[str]) -> str:
        if len(args) > 1:
            raise ValueError("`smite [id]` strikes foe #id (see `threats`), or the best target")
        monster = self.world.monster(int(args[0])) if args else self._best_smite()
        if monster is None:
            if args:
                raise Refused(f"No foe #{args[0]} walks.")
            return f"no smite target worth it (smite hits for {self._smite_hits():.0f})"
        x, y = self.world.position(monster)
        self.hands.smite(monster.id)   # through the hands: the aim gap binds orders too
        self._log("smite", [x, y])
        self._spell_events()
        left = monster.hp if self.world.monster(monster.id) is not None else 0
        return f"smitten #{monster.id} {monster.kind.key} ({left:.0f}hp left) — {view.purse(self.world)}"

    def _hymn(self, args: list[str]) -> str:
        tower = self._tower_on(args)
        self.hands.hymn(tower.id)
        self._log("hymn", [list(tower.tile)])
        self._spell_events()
        return f"hymn on #{tower.id} {tower.kind.key} — {view.purse(self.world)}"

    def _ground(self, spell: str, args: list[str]) -> str:
        if len(args) != 2:
            raise ValueError(f"`{spell} <x> <y>` aims at the floor")
        x, y = float(args[0]), float(args[1])
        getattr(self.hands, spell)(x, y)
        self._log(spell, [x, y])
        self._spell_events()
        return f"{spell} at {x:g},{y:g} — {view.purse(self.world)}"

    def _log(self, name: str, logged: list) -> None:
        """A hands-cast spell joins the replay log in the battle's own form (see battle.py)."""
        assert self.battle is not None
        self.battle.commands.append([self.world.time, name, *logged])

    def _spell_events(self) -> None:
        """Fold a hands-cast spell's events into the hands and the digest, then clear them."""
        self.hands.observe(self.world.events)
        self._drain(self.world.events)
        self.world.events.clear()

    def _smite_hits(self) -> float:
        return felt_hit(SPELLS["smite"].damage * self.world.power(), None, MONSTERS["fallen"])

    def _best_smite(self) -> Monster | None:
        """A killable chanting leader first, else the nearest killable foe to the shrine."""
        hits = self._smite_hits()
        foes = sorted(self.world.monsters, key=lambda m: view.threat_seconds(self.world, m))
        chanters = [m for m in foes if m.hp <= hits and (m.chant_curse is not None or m.marking)]
        if chanters:
            return chanters[0]
        killable = [m for m in foes if m.hp <= hits]
        return killable[0] if killable else None

    # -- Autos and advice ---------------------------------------------------------------

    def _auto_line(self) -> str:
        return " ".join(f"{rule}={'on' if rule in self.autos.enabled else 'off'}" for rule in auto_mod.RULES)

    def _auto(self, args: list[str]) -> str:
        if not args:
            return "auto: " + self._auto_line()
        if len(args) != 2 or args[0] not in auto_mod.RULES or args[1] not in ("on", "off"):
            raise ValueError("`auto <rule> on|off`; rules: " + " ".join(auto_mod.RULES))
        if args[1] == "on":
            self.autos.enabled.add(args[0])
        else:
            self.autos.enabled.discard(args[0])
        self.enabled = set(self.autos.enabled)
        return "auto: " + self._auto_line()

    def _advise(self, args: list[str]) -> str:
        if not args:
            raise ValueError("`advise <kind>` | `advise wave [n]` | `advise up <x> <y>`")
        if args[0] == "wave":
            wave = self.world.wave + 1 if len(args) == 1 else int(args[1]) - 1
            if not 0 <= wave < len(self.world.waves):
                raise ValueError(f"waves are 1..{len(self.world.waves)}")
            return advisor.wave_brief(self.world, wave)
        if args[0] == "up":
            return advisor.upgrade_value(self.world, self._tile(args[1:]))
        kind = args[0].lower()
        if kind not in TOWERS or kind not in self.world.location.arsenal.towers:
            raise ValueError(f"no {kind!r} here (offered: {', '.join(self.world.location.arsenal.towers)})")
        count = 5 if len(args) == 1 else int(args[1])
        if len(args) > 2 or not 1 <= count <= 10:
            raise ValueError("`advise <kind> [N]`, N 1..10")
        spots = advisor.placement(self.world, kind, top=count)
        if not spots:
            return f"no tile sees the path for {kind}"
        rows = [f"({s.tile[0]},{s.tile[1]}) score {s.score:.1f} cover {s.cover:.1f} dps {s.dps:.1f}"
                + (f" — {s.note}" if s.note else "") for s in spots]
        return f"{kind} tiles: " + "; ".join(rows)

    # -- The clock ----------------------------------------------------------------------

    def _wait(self, args: list[str]) -> str:
        seconds = WAIT_DEFAULT if not args else float(args[0])
        if not 0 < seconds <= WAIT_MAX:
            raise ValueError(f"wait 0..{WAIT_MAX:g} seconds")
        return self._run(steps=round(seconds / SIM_DT))

    def _watch(self, args: list[str]) -> str:
        """Play to the next break in one digest: nothing mid-wave needs ruminating on, unless the
        lives run out sooner. `watch leaks N` stops early once N lives leak."""
        limit = None
        if args:
            if len(args) != 2 or args[0] != "leaks":
                raise ValueError("`watch` or `watch leaks N`")
            limit = int(args[1])
            if limit < 1:
                raise ValueError("`watch` or `watch leaks N`, N at least 1")
        return self._run(steps=None, leak_limit=limit)

    def _run(self, *, steps: int | None, leak_limit: int | None = None) -> str:
        if self.battle is None:
            raise Refused("No defence: `defend <location>` first.")
        world = self.world
        gold, kills, lives = world.gold, world.kills, world.lives
        mark, peak = world.time, world.gold
        n = 0
        while steps is None or n < steps:
            if world.outcome is not None:
                break
            if steps is None and world.break_left is not None and n > 0:
                break   # watched into the next break: the digest is the decision point
            if leak_limit is not None and lives - world.lives >= leak_limit:
                break
            self.autos.act()
            frames = self.battle.advance(1)
            if not frames:
                break
            n += 1
            peak = max(peak, world.gold)
            self._drain(frames[0]["events"])
            self._result_frame(frames[0])
        return self._digest(mark, gold, kills, peak)

    def _result_frame(self, frame: dict) -> None:
        if "result" in frame:
            self._result = frame["result"]

    def _drain(self, events: list) -> None:
        """Fold events into the digest's counts: a frame's plain lists or the world's raw tuples."""
        if self.on_events is not None:
            self.on_events(events)
        for e in events:
            kind = e[0]
            if kind == "death":
                self._counts["kills"] += 1
            elif kind in ("leak", "returned"):
                self._counts["lives"] += e[3]
            elif kind == "wave":
                self._counts[f"started w{e[1] + 1}"] += 1
            elif kind == "cleared":
                self._counts[f"cleared w{e[1] + 1} +{e[2]}g"] += 1
            elif kind in ("chant", "mark"):
                self._counts["chants"] += 1
            elif kind == "cursed":
                caught = len(e[4])
                self._counts["landed"] += 1
                self._counts["caught"] += caught
                self._curses.append(f"{CURSES[Curse(e[3])].name} at {e[2][0]},{e[2][1]} caught {caught}")
            elif kind == "fizzle":
                self._counts["fizzled"] += 1
            elif kind in ("smite", "meteor_cast", "orb", "hymn"):
                self._counts[f"cast {kind.replace('meteor_cast', 'meteor')}"] += 1
            elif kind == "door_broken":
                self._counts["gates broke"] += 1
            elif kind == "door_built":
                self._counts["gates raised"] += 1
            elif kind == "breach_failed":
                self._counts["breach failed"] += 1
            elif kind == "breach_cleared":
                self._counts["breach cleared"] += 1

    def _digest(self, mark: float, gold: int, kills: int, peak: int) -> str:
        world = self.world
        held = f" peak {peak}" if peak > max(gold, world.gold) else ""
        lines = [f"+{world.time - mark:.1f}s {view.purse(world)} "
                 f"(gold {gold}->{world.gold}{held}, kills {kills}->{world.kills})"]
        waves = [f"{k}" for k in self._counts if k.startswith(("started", "cleared"))]
        if waves:
            lines.append("waves: " + "; ".join(f"{k} x{v}" if (v := self._counts[k]) > 1 else k for k in waves))
        if self._curses:
            lines.append("curses: " + "; ".join(self._curses[-4:]))
        chants = self._counts["chants"] + self._counts["landed"] + self._counts["fizzled"]
        if chants and not self._curses:
            lines.append(f"curses: {self._counts['chants']} chants, "
                         f"{self._counts['landed']} landed, {self._counts['fizzled']} fizzled")
        casts = [f"{k} x{v}" if (v := self._counts[k]) > 1 else k
                 for k in self._counts if k.startswith("cast")]
        if casts:
            lines.append("spells: " + "; ".join(casts))
        if self._counts["lives"]:
            lines.append(f"LEAKED {self._counts['lives']} lives")
        for key in ("gates broke", "gates raised", "breach failed", "breach cleared"):
            if self._counts[key]:
                lines.append(f"{key}: {self._counts[key]}")
        if world.monsters:
            lines.append("field: " + view.field(world))
        cursed = [f"#{t.id} {t.kind.key} " + ",".join(f"{c.value[:4]}:{left:.0f}s" for c, left in t.curses.items())
                  for t in world.towers.values() if t.curses]
        if cursed:
            lines.append("cursed now: " + "; ".join(cursed))
        if world.outcome is not None:
            lines.append(self._reckoning())
        else:
            lines.append(self._action_line())
        self._counts.clear()
        self._curses.clear()
        return "\n".join(lines)

    def _reckoning(self) -> str:
        """How the defence ended: the campaign's reckoning, or the lab's plain line."""
        world = self.world
        if self._result:
            out = [f"{self._result['title']} — {self._result['note']}"]
            out += [text for _, text in self._result["extra"]]
            return "\n".join(out)
        earned = sigils(world.outcome, world.lives)
        return f"{(world.outcome or '').upper()} with {world.lives} lives — {earned} sigils"

    def _action_line(self) -> str:
        """What the gold can do right now, and the advisor's top tile: the digest's decision point,
        so a digest rarely needs a `status` and an `advise` after it."""
        world = self.world
        gold = world.gold
        afford = [k for k in world.location.arsenal.towers if world.cost(k) <= gold]
        if (world.location.arsenal.gates and world.door_cost <= gold
                and any(not d.built for d in world.doors)):
            afford.append("gate")
        if not afford:
            cheapest = min([world.cost(k) for k in world.location.arsenal.towers]
                           + ([world.door_cost] if world.location.arsenal.gates else []))
            return f"hold ({gold}g; cheapest {cheapest}g)"
        best: tuple[str, str, float] | None = None
        for kind in afford:
            if kind == "gate":
                continue
            spots = advisor.placement(world, kind, top=1)
            if spots and (best is None or spots[0].score > best[2]):
                best = (kind, f"({spots[0].tile[0]},{spots[0].tile[1]})", spots[0].score)
        if best is None:
            return f"afford ({gold}g): {' '.join(afford)}"
        return f"afford ({gold}g): {' '.join(afford)} | top: {best[0]} {best[1]}"

    # -- The campaign -------------------------------------------------------------------

    def _need_campaign(self) -> Campaign:
        if self.campaign is None:
            raise Refused("No profile: start with --profile to keep a campaign.")
        return self.campaign

    def _campaign(self) -> str:
        return view.campaign_text(self._need_campaign())

    def _learn(self, args: list[str]) -> str:
        if len(args) != 1:
            raise ValueError("`learn <skill>` (see `skills`)")
        campaign = self._need_campaign()
        campaign.learn(args[0].lower())
        return (f"learned {args[0].lower()} ({campaign.progress.free} free of {campaign.progress.sigils}) — "
                "takes effect next `defend`")

    def _unlearn(self) -> str:
        campaign = self._need_campaign()
        campaign.unlearn_all()
        return f"unlearned all ({campaign.progress.free} free of {campaign.progress.sigils})"

    def _skills(self, args: list[str]) -> str:
        campaign = self._need_campaign()
        location = args[0].lower() if args else None
        if location is not None and location not in LOCATIONS:
            raise ValueError(f"no location {location!r}")
        return view.skills_text(campaign, location)

    def _forge(self, args: list[str]) -> str:
        campaign = self._need_campaign()
        if not args:
            return view.forge_text(campaign.forge_view())
        if len(args) != 1:
            raise ValueError("`forge [pattern]`")
        try:
            data = campaign.forge(args[0].lower())
        except KeyError:
            raise ValueError(f"no pattern {args[0]!r}") from None
        return view.forge_text(data)

    def _profiles(self) -> str:
        campaign = self._need_campaign()
        data = campaign.profiles()
        names = " ".join(f"*{n}" if n == data["current"] else n for n in data["profiles"])
        return f"profiles: {names}"

    def _profile(self, args: list[str]) -> str:
        if len(args) != 1:
            raise ValueError("`profile <name>`")
        campaign = self._need_campaign()
        campaign.switch_profile(args[0].strip().lower())
        self.battle = None   # the old defence belongs to the old profile: begin anew
        data = campaign.campaign()
        return (f"profile {data['profile']} — {data['free']} free of {data['sigils']} sigils. "
                "`defend <location>` to begin.")
