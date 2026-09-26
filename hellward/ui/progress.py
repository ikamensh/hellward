"""The campaign's progress: the sigils won at each location, the skills learned, and where the
lantern stands on the world map. Saved in the game's save folder (slot ``campaign``) after every change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from saga2d import Game

from hellward.sim.campaign import LOCATIONS, ORDER, Location, sigils
from hellward.sim.skills import SKILLS, can_learn, check, cost

SLOT = "campaign"


@dataclass
class Progress:
    won: dict[str, int] = field(default_factory=dict)   # location → sigils
    learned: frozenset[str] = frozenset()
    at: str = ORDER[0]              # the location the lantern stands at
    game: Game | None = field(default=None, repr=False, compare=False)

    # -- Saving -----------------------------------------------------------------------------------

    @classmethod
    def load(cls, game: Game) -> Progress:
        data = game.save_manager.load(SLOT)
        if data is None:
            return cls(game=game)
        state = data["state"]
        won = state["won"]["normal"] if "difficulty" in state else state["won"]   # a save from before the acts
        learned = frozenset(k for k in state["learned"] if k in SKILLS)
        progress = cls(won=dict(won), learned=learned, at=state["at"], game=game)
        check(progress.learned)
        return progress

    def save(self) -> None:
        if self.game is not None:
            state = {"won": self.won, "learned": sorted(self.learned), "at": self.at}
            self.game.save_manager.save(SLOT, state, "Progress", summary={"sigils": self.sigils, "at": self.at})

    # -- Sigils -----------------------------------------------------------------------------------

    @property
    def sigils(self) -> int:
        return sum(self.won.values())

    @property
    def free(self) -> int:
        return self.sigils - cost(self.learned)

    def best(self, location: str) -> int:
        return self.won.get(location, 0)

    def held(self, location: str) -> bool:
        return self.best(location) > 0

    def opened(self, location: Location) -> bool:
        return all(self.held(need) for need in location.requires)

    def record(self, location: str, outcome: str | None, lives: int) -> int:
        """Take in a defence's result; the sigils it added to the best there."""
        earned = sigils(outcome, lives)
        gained = max(0, earned - self.best(location))
        if gained:
            self.won[location] = earned
        self.at = location
        self.save()
        return gained

    def next_location(self) -> Location | None:
        """The first location that is open and not yet held."""
        for key in ORDER:
            location = LOCATIONS[key]
            if self.opened(location) and not self.held(key):
                return location
        return None

    # -- Skills -----------------------------------------------------------------------------------

    def learn(self, key: str) -> bool:
        if not can_learn(self.learned, key, self.sigils):
            return False
        self.learned = self.learned | {key}
        self.save()
        return True

    def unlearn_all(self) -> None:
        self.learned = frozenset()
        self.save()

    def move(self, location: str) -> None:
        self.at = location
        self.save()
