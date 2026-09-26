"""The campaign's progress: the sigils won at each location on each difficulty, the skills learned, and where the
lantern stands on the world map. Saved in the game's save folder (slot ``campaign``) after every change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from saga2d import Game

from hellward.sim.campaign import DIFFICULTIES, LAST, LOCATIONS, ORDER, Difficulty, Location, sigils
from hellward.sim.skills import can_learn, check, cost

SLOT = "campaign"


@dataclass
class Progress:
    won: dict[str, dict[str, int]] = field(default_factory=lambda: {d: {} for d in DIFFICULTIES})   # difficulty → location → sigils
    learned: frozenset[str] = frozenset()
    at: str = ORDER[0]              # the location the lantern stands at
    difficulty: str = "normal"
    game: Game | None = field(default=None, repr=False, compare=False)

    # -- Saving -----------------------------------------------------------------------------------

    @classmethod
    def load(cls, game: Game) -> Progress:
        data = game.save_manager.load(SLOT)
        if data is None:
            return cls(game=game)
        state = data["state"]
        progress = cls(won={d: dict(state["won"].get(d, {})) for d in DIFFICULTIES}, learned=frozenset(state["learned"]),
                       at=state["at"], difficulty=state["difficulty"], game=game)
        check(progress.learned)
        return progress

    def save(self) -> None:
        if self.game is not None:
            state = {"won": self.won, "learned": sorted(self.learned), "at": self.at, "difficulty": self.difficulty}
            self.game.save_manager.save(SLOT, state, "Progress", summary={"sigils": self.sigils, "at": self.at})

    # -- Sigils -----------------------------------------------------------------------------------

    @property
    def sigils(self) -> int:
        return sum(sum(by_location.values()) for by_location in self.won.values())

    @property
    def free(self) -> int:
        return self.sigils - cost(self.learned)

    def best(self, location: str, difficulty: str | None = None) -> int:
        return self.won[difficulty or self.difficulty].get(location, 0)

    def held(self, location: str, difficulty: str | None = None) -> bool:
        return self.best(location, difficulty) > 0

    def opened(self, location: Location, difficulty: str | None = None) -> bool:
        return all(self.held(need, difficulty) for need in location.requires)

    def difficulty_opened(self, difficulty: Difficulty) -> bool:
        return difficulty.requires is None or self.held(LAST, difficulty.requires)

    def record(self, location: str, outcome: str | None, lives: int) -> int:
        """Take in a defence's result on the chosen difficulty; the sigils it added to the best there."""
        earned = sigils(outcome, lives)
        gained = max(0, earned - self.best(location))
        if gained:
            self.won[self.difficulty][location] = earned
        self.at = location
        self.save()
        return gained

    def next_location(self) -> Location | None:
        """The first location on the chosen difficulty that is open and not yet held."""
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

    def choose(self, difficulty: str) -> None:
        self.difficulty = difficulty
        self.save()

    def move(self, location: str) -> None:
        self.at = location
        self.save()

