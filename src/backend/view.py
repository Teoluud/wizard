from dataclasses import dataclass
from typing import Self

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
class PlayerStatus:
    """Public state of a single player at the table."""

    name: str
    call: int | None
    tricks_won: int
    points: int
    card_count: int

    @classmethod
    def of(cls, player: Player) -> Self:
        return cls(
            name=player.name,
            call=player.call,
            tricks_won=player.tricks_won,
            points=player.points,
            card_count=len(player.cards),
        )


@dataclass(frozen=True)
class PlayerView:
    """Everything one player is allowed to see when it is their turn.

    It only holds plain data (names, cards, numbers), never live game objects,
    so it can be sent to a bot, a GUI or over the network as it is.
    """

    player_name: str
    round_number: int
    dealer_name: str
    trump: Trump
    players: list[PlayerStatus]  # in play order, the next to act first
    hands: list[tuple[str, list[Card]]]  # (owner name, cards) the player can see
    table: list[tuple[str, Card]]  # (player name, card) played in this trick

    @property
    def own_hand(self) -> list[Card] | None:
        """The player's own cards, or None if they can't see them right now."""
        for owner, cards in self.hands:
            if owner == self.player_name:
                return cards
        return None

    @property
    def can_see_own_hand(self) -> bool:
        return self.own_hand is not None

    @property
    def status(self) -> PlayerStatus:
        """The public status (call, tricks won, ...) of the player themselves."""
        for status in self.players:
            if status.name == self.player_name:
                return status
        raise ValueError(f"{self.player_name} is not in this round.")
