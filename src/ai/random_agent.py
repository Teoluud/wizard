from random import Random

from src.backend.cards import Card, Color
from src.backend.rules import PassRule
from src.backend.view import PlayerView


class RandomAgent:
    """Plays a random legal move every time. The baseline every bot must beat."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = Random(seed)

    async def ask_trump_color(self, view: PlayerView) -> Color:
        return self._rng.choice(list(Color))

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        allowed = [c for c in range(view.round_number + 1) if c != forbidden_call]
        return self._rng.choice(allowed)

    async def ask_card_to_pass(self, view: PlayerView, rule: PassRule, recipient: str) -> list[Card]:
        hand = view.own_hand
        if hand is None:
            raise ValueError("Can't choose cards to pass without seeing them.")
        return self._rng.sample(hand, rule.count)

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        return self._rng.choice(legal_cards)