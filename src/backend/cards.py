from dataclasses import dataclass
from enum import StrEnum
from random import Random
from typing import Any, Mapping


class Color(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    GREEN = "green"


@dataclass(frozen=True, kw_only=True)
class Card:
    number: int
    color: Color | None

    def __str__(self) -> str:
        return "(" + str(self.number) + " " + str(self.color) + ")"

    def to_dict(self) -> dict[str, Any]:
        card_type = "card"
        if isinstance(self, Wizard):
            card_type = "wizard"
        elif isinstance(self, Jester):
            card_type = "jester"
        return {
            "type": card_type,
            "number": self.number,
            "color": self.color.value if self.color is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Card":
        card_type = data.get("type", "card")
        if card_type == "wizard" or data["number"] == 14:
            return Wizard()
        if card_type == "jester" or data["number"] == 0:
            return Jester()
        raw_color = data.get("color")
        color = Color(raw_color) if raw_color is not None else None
        return Card(number=int(data["number"]), color=color)


@dataclass(frozen=True, kw_only=True)
class Wizard(Card):
    number: int = 14
    color: Color | None = None


@dataclass(frozen=True, kw_only=True)
class Jester(Card):
    number: int = 0
    color: Color | None = None


class Deck:
    """Standard 60-card Wizard deck with optional deterministic seeding."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = Random(seed)
        self.cards: list[Card] = []
        self.reset_deck()

    def draw(self) -> Card:
        """Draws the top card of the deck."""
        return self.cards.pop(0)

    def _shuffle(self) -> None:
        """Shuffles the deck using the deck's random number generator."""
        self._rng.shuffle(self.cards)

    def reset_deck(self) -> None:
        """Puts all the cards back in the deck and shuffles."""
        self.cards = []
        for color in Color:
            for n in range(1, 14):
                self.cards.append(Card(color=color, number=n))
        for _ in range(4):
            self.cards.append(Wizard())
            self.cards.append(Jester())

        self._shuffle()

    def __len__(self) -> int:
        return len(self.cards)
