"""The campaign on the server: profiles, the map, a location's briefing, the skill tree, the forge, the story and the
results of defences, all decided here and sent to the client as what to show.

The client asks (``campaign``, ``briefing``, ``skills``, ...) and acts (``learn``, ``forge``, ``defend``, ...);
every answer is plain data and finished words: a refusal says why, a briefing's lines are written out, the story
that is due names its pages. :class:`Campaign` keeps the active profile's :class:`~hellward.server.progress.Progress`
and saves it after every change, as the 2D game's screens did (their ways between screens were ``ui/flow.py``).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from hellward.server.battle import Battle
from hellward.server.progress import Progress, campaign_profiles, slot_for_profile
from hellward.server.saves import Saves
from hellward.sim import tuning
from hellward.sim.breaches import BREACHES
from hellward.sim.campaign import (
    ACT_ENDS, ACT_NAMES, ACTS, CATHEDRAL, LOCATIONS, ORDER, SIGIL_LIVES, Location, idle, offers, sigils,
)
from hellward.sim.content import CURSES, MONSTERS, SPELLS, START_LIVES, TOWERS, Curse, Element, MonsterKind
from hellward.sim.items import PATTERNS
from hellward.sim.model import Planner, World
from hellward.sim.players import PLAYERS
from hellward.sim.players.ghost import Ghost
from hellward.sim.players.hands import Player
from hellward.sim.skills import COLUMNS, SKILLS, above, can_learn, perks
from hellward.story import LAST_PAGES, STORIES, Story

ARSENAL = ("arrow", "ballista", "hook", "knife", "pyre", "storm", "frost", "plague", "altar", "grove", "gate", "smite",
           "hymn", "meteor", "orb")
ELEMENT_NAMES = {Element.PHYSICAL: "Physical", Element.FIRE: "Fire", Element.LIGHTNING: "Lightning",
                 Element.COLD: "Cold", Element.POISON: "Poison", Element.BONE: "Bone", Element.NATURE: "Nature"}
NAME_LIMIT = 24
BOSS_STRIKE_LIVES = tuning.integer("battle.boss_strike_lives")


class Refusal(Exception):
    """A request the campaign turns down, with the reason the client shows."""


class Campaign:
    def __init__(self, data: Path, *, planner: Planner, demo_player: Callable[[], Player], seed: int = 0,
                 profile: str = "main") -> None:
        self.data = Path(data)
        self.saves = Saves(self.data / "saves")
        self.planner = planner
        self.demo_player = demo_player
        self.seed = seed
        self.progress = Progress.load(self.saves, profile)
        self.battle: Battle | None = None
        self.last: dict | None = None    # the last decided defence: its location, outcome, and what it won

    # -- Profiles ---------------------------------------------------------------------------------

    def profiles(self) -> dict:
        names = campaign_profiles(self.saves)
        if self.progress.profile not in names:
            names = (*names, self.progress.profile)
        return {"profiles": list(names), "current": self.progress.profile}

    def create_profile(self, name: str) -> dict:
        name = name.strip().lower()
        if not name:
            raise Refusal("Start with a letter or underscore.")
        if len(name) > NAME_LIMIT:
            raise Refusal(f"Names can be at most {NAME_LIMIT} characters.")
        if not name.isidentifier():
            raise Refusal("Start with a letter or _; use only letters, digits and underscores.")
        if name in {p.casefold() for p in campaign_profiles(self.saves)} or \
                self.saves.load(slot_for_profile(name)) is not None:
            raise Refusal("That profile exists. Choose it from the list.")
        fresh = Progress(profile=name, saves=self.saves)
        fresh.save()
        self.progress = fresh
        return self.profiles()

    def switch_profile(self, name: str) -> dict:
        self.progress = Progress.load(self.saves, name)
        return self.profiles()

    # -- The map ----------------------------------------------------------------------------------

    def campaign(self) -> dict:
        """Both acts as the map shows them, the story the map owes first, and the purse of sigils."""
        p = self.progress
        acts = []
        for act, keys in ACTS.items():
            nxt = p.next_location(act)
            places = []
            for i, key in enumerate(keys):
                loc = LOCATIONS[key]
                opened = p.opened(loc)
                if opened:
                    tip = f"{loc.name}\n{loc.blurb}\nSigils won here: {p.best(key)} of 3."
                else:
                    tip = f"{loc.name}\nThe way opens when {LOCATIONS[loc.requires[0]].called} holds."
                places.append({"key": key, "name": loc.name, "number": i + 1, "opened": opened, "held": p.held(key),
                               "best": p.best(key), "tip": tip, "next": nxt is not None and nxt.key == key})
            won = sum(p.best(k) for k in keys)
            acts.append({"act": act, "name": ACT_NAMES[act], "places": places, "won": won, "total": 3 * len(keys),
                         "open": act == 1 or p.held(ACT_ENDS[act - 1]),
                         "line": f"Act {'I' * act}: {won} of {3 * len(keys)} sigils won. {p.free} to spend on skills."})
        due = self.due()
        return {"profile": p.profile, "sigils": p.sigils, "free": p.free, "at": p.at,
                "act": LOCATIONS[p.at].act, "acts": acts, "due": None if due is None else story(STORIES[due]),
                "prologue": "prologue" not in p.seen, "salvage": p.salvage, "trophies": len(p.trophies)}

    def due(self) -> str | None:
        """The story a map opening owes the player, if any: an act's ending once its last location is held, else the
        after page of a held location in an act not yet finished (a finished act's pages wait in the Chronicle), in
        campaign order. A player who quit at the reckoning gets it here."""
        seen = self.progress.seen
        for act, end in ACT_ENDS.items():
            if self.progress.held(end) and LAST_PAGES[act] not in seen:
                return LAST_PAGES[act]
        for key in ORDER:
            page = f"{key}/after"
            if (page in STORIES and page not in seen and self.progress.held(key)
                    and not self.progress.held(ACT_ENDS[LOCATIONS[key].act])):
                return page
        return None

    def seen(self, key: str) -> dict:
        """A story shown (an opening counts, even when skipped)."""
        if key != "prologue" and key not in STORIES:
            raise ValueError(f"no story {key!r}")
        self.progress.see(key)
        return {}

    def chronicle(self) -> dict:
        """Every story whose moment has come, in the story's order: a before page when its location is opened, an
        after page when it is held, an act's ending when its last location is held."""
        p = self.progress
        out = []
        for tale in STORIES.values():
            place, _, when = tale.key.partition("/")
            if when == "end":
                due = p.held(ACT_ENDS[tale.act])
            elif when == "before":
                due = p.opened(LOCATIONS[place])
            else:
                due = p.held(place)
            if due:
                out.append(story(tale))
        return {"stories": out}

    # -- A location's briefing --------------------------------------------------------------------

    def briefing(self, location: str) -> dict:
        """A location's intro; the lantern now stands there."""
        loc = self._location(location)
        p = self.progress
        p.move(loc.key)
        index = ORDER.index(loc.key)
        before_key = f"{loc.key}/before"
        story_first = before_key in STORIES and before_key not in p.seen
        host = []
        for key in loc.monsters:
            kind = MONSTERS[key]
            first = next(w for w in loc.waves if any(g.kind == key for g in w.groups))
            life = kind.hp * first.hp * loc.life
            pace = "fast" if kind.speed >= 1.3 else "steady" if kind.speed >= 0.9 else "slow"
            lives = f", {kind.lives} lives" if kind.lives > 1 else ""
            notes = monster_notes(kind)
            if kind.leader is not None:
                spec = kind.leader
                notes.append("Curses: " + ", ".join(CURSES[c].name for c in spec.curses))
                if spec.raises:
                    notes.append(f"Raises fallen {MONSTERS[spec.raises].name}s")
                if spec.mark > 0:
                    notes.append(f"Marks its spot {spec.mark:g} s before the curse lands")
                if spec.burn > 0:
                    notes.append(f"Each curse burns {spec.burn:g} mana per tower caught")
            host.append({"kind": key, "name": kind.name, "leader": kind.leader is not None,
                         "line": f"{life:.0f} life, {pace}{lives}", "notes": ", ".join(notes) or "Unarmored, no tags"})
        curses: list[Curse] = []
        for key in loc.monsters:
            spec = MONSTERS[key].leader
            if spec is not None:
                curses += [c for c in spec.curses if c not in curses]
        answers = ["spread your towers, so one curse catches few", "kill the leader before it curses"]
        if offers(loc, "smite"):
            answers.append("Smite (Q) strikes it anywhere")
        previous = LOCATIONS[ORDER[index - 1]] if index > 0 else None
        learned = perks(p.learned, index)
        arsenal = []
        for thing in ARSENAL:
            if not offers(loc, thing):
                continue
            if thing in TOWERS:
                name, tip, ranks = TOWERS[thing].name, TOWERS[thing].blurb, learned.top(thing) + 1
            elif thing == "gate":
                name, tip, ranks = "Warded Gate", "Bars an arch: walkers must break it; flyers pass over.", 0
            else:
                name, tip, ranks = SPELLS[thing].name, SPELLS[thing].blurb, 0
            arsenal.append({"key": thing, "name": name, "tip": tip, "ranks": ranks,
                            "new": previous is not None and not offers(previous, thing)})
        won = p.best(loc.key)
        next_sigil = None
        if won < 3:
            next_sigil = ("Hold the sanctuary to win the first." if won == 0
                          else f"The next: keep {SIGIL_LIVES[won]} of {START_LIVES} lives.")
        wasted = sum(SKILLS[k].cost for k in p.learned if SKILLS[k].first_location > index or idle(loc, SKILLS[k].needs))
        waste = None
        if wasted:
            waste = ("1 sigil sits in a skill that does" if wasted == 1 else f"{wasted} sigils sit in skills that do") + \
                " nothing here."
        breach = BREACHES.get(loc.key)
        return {
            "key": loc.key, "name": loc.name, "act": loc.act, "theme": loc.theme,
            "heading": f"{ACT_NAMES[loc.act]}, {ACTS[loc.act].index(loc.key) + 1} of {len(ACTS[loc.act])}  ·  "
                       f"{len(loc.waves)} waves",
            "lesson": loc.lesson, "taunt": loc.taunt, "blurb": loc.blurb, "host": host,
            "curses": [{"key": c.value, "title": f"{CURSES[c].name}, {CURSES[c].duration:g} s, radius {CURSES[c].radius:g}",
                        "line": f"The tower {CURSES[c].blurb}."} for c in curses],
            "answer": "The answer: " + "; ".join(answers) + ".",
            "arsenal": arsenal, "best": won, "next_sigil": next_sigil, "waste": waste,
            "breach": None if breach is None else {"name": breach.name, "blurb": breach.blurb,
                                                   "claimed": p.breach_claims.get(loc.key)},
            "story": story(STORIES[before_key]) if story_first else None,   # owed before the intro shows
            "before": story(STORIES[before_key]) if before_key in STORIES else None,   # the intro's Story button
            "opened": p.opened(loc),
        }

    # -- Skills -----------------------------------------------------------------------------------

    def skills(self, location: str | None = None) -> dict:
        p = self.progress
        loc = self._location(location) if location else None
        nodes = []
        for key, skill in SKILLS.items():
            learned = key in p.learned
            learnable = can_learn(p.learned, key, p.sigils, p.stage)
            parent = above(skill)
            if learned:
                state = "Learned."
            elif learnable:
                state = f"Click to learn it for {skill.cost} sigil{'s' if skill.cost > 1 else ''}."
            elif p.stage < skill.first_location:
                state = f"Opens in {LOCATIONS[ORDER[skill.first_location]].name}."
            elif parent is not None and parent.key not in p.learned:
                state = f"Needs {parent.name} first."
            else:
                state = f"Costs {skill.cost} sigils; {p.free} are free."
            note = ""
            dormant = False
            if loc is not None:
                index = ORDER.index(loc.key)
                if index < skill.first_location:
                    dormant = True
                    note = f"Inactive in {loc.called}; takes effect from {LOCATIONS[ORDER[skill.first_location]].called}."
                elif idle(loc, skill.needs):
                    dormant = True
                    note = "Nothing to work on here."
            nodes.append({"key": key, "name": skill.name, "column": skill.column, "tier": skill.tier,
                          "cost": skill.cost, "blurb": skill.blurb, "learned": learned, "learnable": learnable,
                          "parent": parent.key if parent is not None else None, "dormant": dormant,
                          "tip": f"{skill.name}\n{skill.blurb}\n{state}" + (f"\n{note}" if note else "")})
        heading = f"{p.free} sigil{'s' if p.free != 1 else ''} free of {p.sigils} won. Unlearning is free."
        if loc is not None:
            heading += f"  ·  greyed: no effect in {loc.called}"
        return {"columns": [{"key": k, "name": v} for k, v in COLUMNS.items()], "nodes": nodes,
                "sigils": p.sigils, "free": p.free, "heading": heading, "any": bool(p.learned)}

    def learn(self, key: str, location: str | None = None) -> dict:
        if key not in SKILLS:
            raise ValueError(f"no skill {key!r}")
        if not self.progress.learn(key):
            skill = SKILLS[key]
            parent = above(skill)
            if key in self.progress.learned:
                raise Refusal(f"{skill.name} is learned.")
            if self.progress.stage < skill.first_location:
                raise Refusal(f"{skill.name} opens in {LOCATIONS[ORDER[skill.first_location]].name}.")
            if parent is not None and parent.key not in self.progress.learned:
                raise Refusal(f"{skill.name} needs {parent.name} first.")
            raise Refusal(f"{skill.name} costs {skill.cost} sigils; {self.progress.free} are free.")
        return self.skills(location)

    def unlearn_all(self, location: str | None = None) -> dict:
        self.progress.unlearn_all()
        return self.skills(location)

    # -- The forge --------------------------------------------------------------------------------

    def forge_view(self) -> dict:
        p = self.progress
        cards = []
        at = ORDER.index(p.at) + 1
        for key, pattern in PATTERNS.items():
            owned = key in p.patterns
            equipped = key in p.loadout.equipped
            reached = p.stage + 1 >= pattern.first_location
            affordable = p.salvage >= pattern.salvage_cost and len(p.trophies) >= pattern.trophy_cost
            if owned and equipped and at < pattern.first_location:
                label = "Unequip (inactive here)"
                why = f"Equipped, but it has no effect here. It opens at {LOCATIONS[ORDER[pattern.first_location - 1]].called}."
            elif owned:
                label = "Unequip" if equipped else "Equip"
                why = "Owned permanently. Switch patterns without paying again."
            elif not reached:
                label = f"Opens at {LOCATIONS[ORDER[pattern.first_location - 1]].called}"
                why = "Win earlier locations to unlock this pattern."
            elif not affordable:
                label = "Need more drops"
                why = "Defeat monsters and claim side trophies to gather its materials."
            else:
                label = "Forge and equip"
                why = "Spend these materials permanently and equip the pattern for the next defence."
            price = f"{pattern.salvage_cost} salvage"
            if pattern.trophy_cost:
                price += f" + {pattern.trophy_cost} troph{'ies' if pattern.trophy_cost > 1 else 'y'}"
            cards.append({"key": key, "name": pattern.name, "family": pattern.family,
                          "family_name": f"{pattern.family.title()} Tower", "blurb": pattern.blurb, "price": price,
                          "owned": owned, "equipped": equipped, "enabled": owned or (reached and affordable),
                          "label": label, "why": why})
        trophies = len(p.trophies)
        return {"salvage": p.salvage, "trophies": trophies,
                "line": f"{p.salvage} salvage  ·  {trophies} troph{'ies' if trophies != 1 else 'y'} unspent",
                "cards": cards}

    def forge(self, key: str) -> dict:
        """A card's one button: forge and equip, equip, or unequip."""
        pattern = PATTERNS[key]
        p = self.progress
        try:
            if key not in p.patterns:
                p.forge(key)
                p.equip(key)
            elif key in p.loadout.equipped:
                p.unequip(pattern.family)
            else:
                p.equip(key)
        except ValueError as refused:
            raise Refusal(str(refused)) from refused
        return self.forge_view()

    # -- Battles ----------------------------------------------------------------------------------

    def defend(self, location: str, player: str | None = None) -> Battle:
        """The profile's defence of a location: its result goes into the campaign. A named scripted player may defend
        it in the person's place (a playtest's shortcut, and the tests' way to win honestly)."""
        loc = self._location(location)
        if not self.progress.opened(loc):
            raise Refusal(f"The way to {loc.called} is not open yet.")
        p = self.progress
        self.battle = Battle(loc, learned=p.learned, loadout=p.loadout, seed=self.seed, planner=self.planner,
                             player=PLAYERS[player](self.seed) if player is not None else None,
                             breach_claim=p.breach_claims.get(loc.key), replays=self.data / "replays",
                             on_outcome=self._keep)
        return self.battle

    def demo(self, location: str | None = None, player: str | None = None, replay: dict | None = None) -> Battle:
        """The title's "Watch the leaders at work": the strongest scripted player defends (the Cathedral unless told
        otherwise), with the skills the sigils won on the way there buy. A named scripted player, or a logged
        defence replayed by its ghost (which brings its own location), may play instead."""
        if replay is not None:
            scripted: Player = Ghost(replay)
            location = scripted.location
        elif player is not None:
            scripted = PLAYERS[player](self.seed)
        else:
            scripted = self.demo_player()
        loc = self._location(location) if location else CATHEDRAL
        seed = int(replay["seed"]) if replay is not None else self.seed
        self.battle = Battle(loc, seed=seed, planner=self.planner, player=scripted)
        return self.battle

    def _keep(self, world: World) -> dict:
        """The moment a person's defence is decided: keep its sigils, unsold drops and side trophy, and say how it
        went, as the reckoning shows it."""
        loc = world.location
        reward = self.progress.record_result(loc.key, world.outcome, world.lives, salvage=world.salvage_held,
                                             breach_mode=world.breach_mode, breach_cleared=world.breach_cleared)
        won = world.outcome == "victory"
        earned = sigils(world.outcome, world.lives)
        index = ORDER.index(loc.key)
        after = LOCATIONS[ORDER[index + 1]] if index + 1 < len(ORDER) else None
        lines = [f"Waves withstood: {world.wave + (1 if won else 0)} of {len(world.waves)}",
                 f"Monsters slain: {world.kills}",
                 f"Life kept: {world.lives} of {START_LIVES}",
                 f"Curses the leaders laid on your towers: {world.curses_landed}."]
        if won:
            gained = reward.sigils
            note = (f"{gained} new sigil{'s' if gained > 1 else ''}: spend {'them' if gained > 1 else 'it'} on skills."
                    if gained else "No new sigils: you have held this place as well before.")
        else:
            note = "No sigils for a fallen sanctuary. Reshape your skills and try again."
        extra = []
        if (after is not None and reward.sigils and self.progress.best(loc.key) == earned
                and self.progress.opened(after) and not self.progress.held(after.key)):
            extra.append(["holy", f"The way down to {after.called} is open."])
        if reward.salvage:
            extra.append(["gold", f"+{reward.salvage} salvage banked for the tower forge."])
        if reward.trophy:
            assert world.breach_spec is not None
            extra.append(["unique", f"The {world.breach_spec.name} trophy is yours. Rare patterns need trophies."])
        elif world.breach_cleared and world.breach_mode == "cash":
            extra.append(["pale", "The side cache paid gold during the defence; this site yields no trophy."])
        self.last = {"location": loc.key, "outcome": world.outcome}
        return {"won": won, "title": "The Sanctuary Holds" if won else "The Sanctuary Has Fallen",
                "location": loc.name, "lines": lines, "earned": earned, "gained": reward.sigils, "note": note,
                "extra": extra}

    def leave(self, again: bool) -> dict:
        """Leaving the reckoning by either button: after a victory the act ending (at the last location) or the
        location's after page plays first when unseen, then the button's way: ``intro`` (the location again),
        ``map``, or ``act2`` (Act II's map, its lantern walking to the Docks)."""
        last = self.last
        self.battle = None
        if last is None:
            return {"story": None, "then": "map"}
        loc = LOCATIONS[last["location"]]
        then = "intro" if again else "map"
        if last["outcome"] == "victory":
            act = loc.act
            key = LAST_PAGES[act] if loc.key == ACT_ENDS[act] else f"{loc.key}/after"
            tale = STORIES.get(key)
            finished = loc.key != ACT_ENDS[act] and self.progress.held(ACT_ENDS[act])
            if tale is not None and key not in self.progress.seen and not finished:
                self.progress.see(key)
                if key == LAST_PAGES[1]:
                    then = "act2"
                return {"story": story(tale), "then": then, "location": loc.key}
        return {"story": None, "then": then, "location": loc.key}

    def _location(self, key: str) -> Location:
        if key not in LOCATIONS:
            raise ValueError(f"no location {key!r}")
        return LOCATIONS[key]


def story(tale: Story) -> dict:
    return {"key": tale.key, "act": tale.act, "pages": [{"key": page.key, "text": list(page.text)} for page in tale.pages]}


def monster_notes(kind: MonsterKind) -> list[str]:
    """A monster's armor and element tags, whether it flies, and a boss's strike on the shrine."""
    notes = []
    if kind.armor:
        notes.append(f"Armor {kind.armor}")
    notes += [f"Protected from {ELEMENT_NAMES[e]}" for e in kind.protected]
    notes += [f"Vulnerable to {ELEMENT_NAMES[e]}" for e in kind.vulnerable]
    if kind.flying:
        notes.append("Flies over gates")
    if kind.boss:
        notes.append(f"Strikes the shrine for {BOSS_STRIKE_LIVES} lives, then walks again")
    return notes
