from dataclasses import dataclass

from src.backend.cards import Card, Color
from src.backend.player import Player


@dataclass(frozen=True)
class Trump:
    """The trump card of a round and the suit it makes trump.

    `color` is None when there is no trump (no card left, a Jester, or a
    Wizard whose suit the dealer has not chosen yet).
    """

    card: Card | None
    color: Color | None


@dataclass(frozen=True)
class PlayerView:
    """Everything one player is allowed to see when it is their turn."""

    player: Player
    round_number: int
    trump: Trump
    hands: list[tuple[Player, list[Card]]]
    table: list[tuple[Player, Card]]

    @property
    def can_see_own_hand(self) -> bool:
        return any(owner is self.player for owner, _ in self.hands)
