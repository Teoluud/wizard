from collections import Counter
from collections.abc import Callable

from src.ai.knowledge import (
    beats,
    blind_win_chance,
    card_power,
    expected_tricks,
    hold_chance,
    unseen_cards,
)
from src.backend.cards import Card, Color
from src.backend.events import CardPlayed, GameEvent, RoundStarted
from src.backend.rules import PassRule
from src.backend.view import PlayerView

# When it wants a trick, the bot plays the weakest card that is at least this
# likely to still be winning once everybody has played.
WIN_THRESHOLD = 0.55
# Below this, a trick it needs is considered lost and it saves its good cards.
GIVE_UP_THRESHOLD = 0.25


def _winning_card(table: list[tuple[str, Card]], trump: Color | None) -> Card | None:
    """The card currently winning the trick, or None if nobody has played."""
    if not table:
        return None
    winner = table[0][1]
    for _, card in table[1:]:
        if beats(card, winner, trump):
            winner = card
    return winner


class HeuristicAgent:
    """A rule-based bot that plays the odds.

    It only uses what any player may know: its view and the cards played so far
    (it follows the game events, so the Game registers it as an observer on its
    own). It calls the number of tricks its hand is worth, then plays to hit
    that number: win the tricks it needs with the weakest card that holds, and
    get rid of its strong cards in the tricks it doesn't want.
    """

    def __init__(self) -> None:
        self._played: list[Card] = []

    async def on_event(self, event: GameEvent) -> None:
        match event:
            case RoundStarted():
                self._played.clear()
            case CardPlayed(card=card):
                self._played.append(card)
            case _:
                pass

    async def ask_trump_color(self, view: PlayerView) -> Color:
        hand = view.own_hand
        if hand is not None:
            # The suit we are strongest in
            return max(
                Color,
                key=lambda c: sum(card.number for card in hand if card.color == c),
            )
        # Round 1: we can't see our card, so make the suit the others are weakest in.
        others = [card for _, cards in view.hands for card in cards]
        return min(
            Color, key=lambda c: sum(card.number for card in others if card.color == c)
        )

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        expected = self._expected_tricks(view)
        allowed = [c for c in range(view.round_number + 1) if c != forbidden_call]
        return min(allowed, key=lambda call: (abs(call - expected), call))

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        hand = view.own_hand
        if hand is None:
            raise ValueError("Can't choose cards to pass without seeing them.")
        trump = view.trump.color
        expected = self._expected_tricks(view)
        ranked = sorted(hand, key=lambda card: card_power(card, trump))
        # Stronger than the call we made: give the best cards away, else the worst.
        if expected > (view.status.call or 0):
            return ranked[-rule.count :]
        return ranked[: rule.count]

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        if len(legal_cards) == 1:
            return legal_cards[0]
        trump = view.trump.color
        unseen = self.unseen_for(view)
        opponents_left = len(view.players) - 1 - len(view.table)
        leader = _winning_card(view.table, trump)

        def hold(card: Card) -> float:
            """The chance that playing `card` takes the trick."""
            if leader is not None and not beats(card, leader, trump):
                return 0.0
            return hold_chance(card, unseen, trump, opponents_left)

        def power(card: Card) -> int:
            return card_power(card, trump)

        status = view.status
        needed = (status.call or 0) - status.tricks_won
        if needed > 0:
            hand = view.own_hand or legal_cards
            # How many tricks our whole hand is currently expected to win
            hand_value = expected_tricks(hand, unseen, trump, len(view.players) - 1)
            # If we have excess winning power AND can safely lose this trick,
            # dump our strongest guaranteed loser now while it's safe.
            sure_losers = [c for c in legal_cards if hold(c) <= 0.0]
            if sure_losers and (hand_value - needed) >= 0.5:
                return max(sure_losers, key=power)
            
            return self._play_to_win(
                legal_cards, hold, power, must=needed >= len(hand)
            )
        return self._play_to_lose(legal_cards, hold, power)

    @staticmethod
    def _play_to_win(
        legal_cards: list[Card],
        hold: Callable[[Card], float],
        power: Callable[[Card], int],
        must: bool,
    ) -> Card:
        """`must` is True when every remaining trick has to be won."""
        decent = [card for card in legal_cards if hold(card) >= WIN_THRESHOLD]
        if decent:
            return min(decent, key=power)
        best = max(legal_cards, key=hold)
        if hold(best) <= 0.0:
            return min(legal_cards, key=power)  # can't win it: lose it cheaply
        if must or hold(best) >= GIVE_UP_THRESHOLD:
            return best
        return min(legal_cards, key=power)  # probably lost: keep the good cards

    @staticmethod
    def _play_to_lose(
        legal_cards: list[Card],
        hold: Callable[[Card], float],
        power: Callable[[Card], int],
    ) -> Card:
        sure_losers = [card for card in legal_cards if hold(card) <= 0.0]
        if sure_losers:
            return max(sure_losers, key=power)  # dump the strongest card that loses.
        return min(legal_cards, key=lambda card: (hold(card), power(card)))

    def _expected_tricks(self, view: PlayerView) -> float:
        unseen = self.unseen_for(view)
        opponents = len(view.players) - 1
        hand = view.own_hand
        if hand is not None:
            return expected_tricks(hand, unseen, view.trump.color, opponents)
        blind = blind_win_chance(view, unseen)
        if blind is not None:
            return blind  # round 1: we see the others' cards, not ours
        return view.round_number / len(view.players)  # fully blind: the fair share

    def unseen_for(self, view: PlayerView) -> list[Card]:
        """The cards that could still be in the opponents' hands."""
        # The table is part of the played cards, so take the larger count of each.
        known = Counter(self._played) | Counter(card for _, card in view.table)
        for _, cards in view.hands:
            known.update(cards)
        if view.trump.card is not None:
            known[view.trump.card] += 1
        return unseen_cards(known.elements())
