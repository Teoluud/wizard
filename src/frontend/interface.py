from typing import Protocol

from src.backend.cards import Card
from src.backend.player import Player


class GameInterface(Protocol):
    """What the Game needs from any front end (CLI, GUI, ...)."""

    def ask_call(
        self, player: Player, round_number: int, trump: Card | None
    ) -> int: ...

    def ask_card(self, player: Player, legal_cards: list[Card]) -> Card: ...

    def show_trick_winner(self, winner: Player) -> None: ...

    def show_scores(self, players: list[Player]) -> None: ...
