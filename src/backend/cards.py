from enum import StrEnum
from dataclasses import dataclass
from random import shuffle


class Color(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"
    GREEN = "green"


@dataclass(kw_only=True)
class Card:
    number: int
    color: Color | None

    def __str__(self) -> str:
        return "(" + str(self.number) + " " + str(self.color) + ")"


@dataclass(kw_only=True)
class Wizard(Card):
    number: int = 14
    color: Color | None = None


@dataclass(kw_only=True)
class Jester(Card):
    number: int = 0
    color: Color | None = None


class Deck:

    def __init__(self) -> None:
        self.cards: list[Card] = []
        self.reset_deck()

    def draw(self) -> Card:
        """Draws the top card of the deck."""
        return self.cards.pop(0)

    def _shuffle(self) -> None:
        """Shuffles the deck."""
        shuffle(self.cards)

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

    def __len__(self):
        return len(self.cards)
