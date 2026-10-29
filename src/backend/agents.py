from typing import Protocol, runtime_checkable

from src.backend.cards import Card, Color
from src.backend.events import GameEvent
from src.backend.rules import PassRule
from src.backend.view import PlayerView


class PlayerAgent(Protocol):
    """Whoever sits at one seat and takes its decisions: a human, a bot, a client.

    The Game asks every question through the agent of the player whose turn it is,
    and only ever shows it that player's `PlayerView`.
    """

    async def ask_trump_color(self, view: PlayerView) -> Color:
        """The dealer picks the trump suit when the trump card is a Wizard."""
        ...

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        """How many tricks the player calls (never `forbidden_call`)."""
        ...

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        """The `rule.count` cards the player gives to the `recipient`."""
        ...

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        """The card to play, one of `legal_cards`."""
        ...


@runtime_checkable
class GameObserver(Protocol):
    """Whoever wants to follow the game: a screen, a log, a spectator, ...
    
    An agent that also has `on_event` is registered by the Game automatically,
    so a bot can keep track of the cards that were played.
    """

    async def on_event(self, event: GameEvent) -> None: ...
