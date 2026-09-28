"""The campaign's sigils, skills, banked loot, forged patterns and map position.

Saved in the game's save folder (slot ``campaign``) after every change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from saga2d import Game

from hellward.sim.breaches import BREACHES
from hellward.sim.campaign import ACTS, LOCATIONS, ORDER, Location, sigils
from hellward.sim.items import PATTERNS, Loadout, Pattern
from hellward.sim.skills import can_learn, check, cost, kept

SLOT = "campaign"
BREACH_SITES = frozenset(BREACHES)


def slot_for_profile(profile: str) -> str:
    """Keep the original campaign save intact; named playtests get separate slots."""
    if not profile.isidentifier():
        raise ValueError(f"Profile name must be a simple word: {profile!r}")
    return SLOT if profile == "main" else f"{SLOT}_{profile}"


@dataclass(frozen=True)
class RewardGain:
    """New persistent rewards earned by one defence, beyond earlier results at that location."""

    sigils: int = 0
    salvage: int = 0
    trophy: str | None = None


@dataclass
class Progress:
    won: dict[str, int] = field(default_factory=dict)   # location → sigils
    learned: frozenset[str] = frozenset()
    at: str = ORDER[0]              # the location the lantern stands at
    seen: frozenset[str] = frozenset()   # story keys shown: "prologue", "tristram/before", ...
    salvage_best: dict[str, int] = field(default_factory=dict)   # location → highest unsold victory salvage
    salvage: int = 0                # spendable banked salvage, after forging
    breach_claims: dict[str, str] = field(default_factory=dict)   # location → first successful choice: trophy or cash
    trophies: frozenset[str] = frozenset()   # unspent trophy IDs, each the breach location's key
    patterns: frozenset[str] = frozenset()   # forged patterns, owned permanently
    loadout: Loadout = field(default_factory=Loadout)
    profile: str = "main"
    game: Game | None = field(default=None, repr=False, compare=False)

    # -- Saving -----------------------------------------------------------------------------------

    @classmethod
    def load(cls, game: Game, profile: str = "main") -> Progress:
        data = game.save_manager.load(slot_for_profile(profile))
        if data is None:
            return cls(profile=profile, game=game)
        state = data["state"]
        won = state["won"]["normal"] if "difficulty" in state else state["won"]   # a save from before the acts
        stage = min(len(ORDER) - 1, max((ORDER.index(key) + 1 for key in won), default=0))
        learned = kept(state["learned"], sum(won.values()), stage)   # the tree may have changed since the save
        owned = frozenset(state.get("patterns", ()))
        unknown = sorted(key for key in owned if key not in PATTERNS)
        if unknown:
            raise ValueError(f"Unknown tower pattern in save: {unknown[0]}")
        loadout = Loadout(tuple(state.get("loadout", ())))
        if not set(loadout.equipped) <= owned:
            raise ValueError("Equipped tower pattern is not owned")
        progress = cls(won=dict(won), learned=learned, at=state["at"], seen=frozenset(state.get("seen", ())),
                       salvage_best=dict(state.get("salvage_best", {})), salvage=state.get("salvage", 0),
                       breach_claims=dict(state.get("breach_claims", {})),
                       trophies=frozenset(state.get("trophies", ())), patterns=owned, loadout=loadout,
                       profile=profile, game=game)
        check(progress.learned)
        return progress

    def save(self) -> None:
        if self.game is not None:
            state = {"won": self.won, "learned": sorted(self.learned), "at": self.at, "seen": sorted(self.seen),
                     "salvage_best": self.salvage_best, "salvage": self.salvage,
                     "breach_claims": self.breach_claims, "trophies": sorted(self.trophies),
                     "patterns": sorted(self.patterns), "loadout": list(self.loadout.equipped)}
            self.game.save_manager.save(slot_for_profile(self.profile), state, "Progress",
                                        summary={"sigils": self.sigils, "at": self.at})

    def see(self, key: str) -> None:
        """Remember a story key as shown (opening counts, even when skipped) and save."""
        self.seen = self.seen | {key}
        self.save()

    # -- Sigils -----------------------------------------------------------------------------------

    @property
    def sigils(self) -> int:
        return sum(self.won.values())

    @property
    def free(self) -> int:
        return self.sigils - cost(self.learned)

    @property
    def stage(self) -> int:
        """The furthest location now open for skills and patterns."""
        return min(len(ORDER) - 1, max((ORDER.index(key) + 1 for key in self.won), default=0))

    def best(self, location: str) -> int:
        return self.won.get(location, 0)

    def held(self, location: str) -> bool:
        return self.best(location) > 0

    def opened(self, location: Location) -> bool:
        return all(self.held(need) for need in location.requires)

    def record(self, location: str, outcome: str | None, lives: int) -> int:
        """Take in a defence's result; the sigils it added to the best there."""
        return self.record_result(location, outcome, lives).sigils

    def record_result(self, location: str, outcome: str | None, lives: int, *, salvage: int = 0,
                      breach_mode: str | None = None, breach_cleared: bool = False) -> RewardGain:
        """Apply a run's permanent rewards together, saving once at the outcome boundary."""
        if location not in LOCATIONS:
            raise KeyError(location)
        if salvage < 0:
            raise ValueError("Banked salvage cannot be negative")
        if breach_mode not in (None, "decline", "cash", "trophy"):
            raise ValueError(f"Unknown breach reward mode: {breach_mode}")
        if breach_mode is not None and location not in BREACH_SITES:
            raise ValueError(f"{location} has no breach")
        if breach_cleared and breach_mode not in ("cash", "trophy"):
            raise ValueError("A cleared breach needs a cash or trophy reward mode")
        earned = sigils(outcome, lives)
        gained = max(0, earned - self.best(location))
        if gained:
            self.won[location] = earned
        salvage_gained = 0
        if outcome == "victory":
            salvage_gained = max(0, salvage - self.salvage_best.get(location, 0))
            if salvage_gained:
                self.salvage_best[location] = salvage
                self.salvage += salvage_gained
        trophy_gained = None
        if outcome == "victory" and breach_cleared and location not in self.breach_claims:
            assert breach_mode in ("cash", "trophy")
            self.breach_claims[location] = breach_mode
            if breach_mode == "trophy":
                self.trophies = self.trophies | {location}
                trophy_gained = location
        self.at = location
        self.save()
        return RewardGain(gained, salvage_gained, trophy_gained)

    def next_location(self, act: int) -> Location | None:
        """The first location in the given act that is open and not yet held."""
        for key in ACTS[act]:
            location = LOCATIONS[key]
            if self.opened(location) and not self.held(key):
                return location
        return None

    # -- Skills -----------------------------------------------------------------------------------

    def learn(self, key: str) -> bool:
        if not can_learn(self.learned, key, self.sigils, self.stage):
            return False
        self.learned = self.learned | {key}
        self.save()
        return True

    def unlearn_all(self) -> None:
        self.learned = frozenset()
        self.save()

    # -- Forging ----------------------------------------------------------------------------------

    def forge(self, key: str) -> Pattern:
        """Spend banked salvage and trophies on one permanent, authored tower pattern."""
        pattern = PATTERNS[key]
        if key in self.patterns:
            raise ValueError(f"{pattern.name} is already forged")
        if self.stage + 1 < pattern.first_location:
            raise ValueError(f"{pattern.name} opens at location {pattern.first_location}")
        if self.salvage < pattern.salvage_cost:
            raise ValueError(f"{pattern.name} needs {pattern.salvage_cost} salvage")
        if len(self.trophies) < pattern.trophy_cost:
            raise ValueError(f"{pattern.name} needs {pattern.trophy_cost} trophies")
        spent = set(sorted(self.trophies, key=ORDER.index)[:pattern.trophy_cost])
        self.salvage -= pattern.salvage_cost
        self.trophies -= spent
        self.patterns |= {key}
        self.save()
        return pattern

    def equip(self, key: str) -> Loadout:
        """Equip an owned pattern, replacing any other pattern on that tower family."""
        pattern = PATTERNS[key]
        if key not in self.patterns:
            raise ValueError(f"{pattern.name} is not owned")
        other = tuple(owned for owned in self.loadout.equipped if PATTERNS[owned].family != pattern.family)
        self.loadout = Loadout(other + (key,))
        self.save()
        return self.loadout

    def unequip(self, family: str) -> Loadout:
        """Leave one tower family without a forged pattern for the next defence."""
        if family not in {pattern.family for pattern in PATTERNS.values()}:
            raise ValueError(f"Unknown tower pattern family: {family}")
        self.loadout = Loadout(tuple(key for key in self.loadout.equipped if PATTERNS[key].family != family))
        self.save()
        return self.loadout

    def move(self, location: str) -> None:
        self.at = location
        self.save()
