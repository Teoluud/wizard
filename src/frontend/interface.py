from typing import Protocol

from src.backend.cards import Card, Color
from src.backend.player import Player
from src.backend.rules import PassRule
from src.backend.view import PlayerView


class GameInterface(Protocol):
    """What the Game needs from any front end (CLI, GUI, ...)."""

    def ask_trump_color(self, view: PlayerView) -> Color:
        """The dealer picks the trump suit when the trump card is a Wizard."""
        ...

    def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int: ...

    def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: Player
    ) -> list[Card]:
        """Returns the `rule.count` cards the player gives to `recipient`."""
        ...

    def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card: ...

    def show_trick_winner(
        self, winner: Player, table: list[tuple[Player, Card]]
    ) -> None: ...

    def show_scores(self, players: list[Player]) -> None: ...
