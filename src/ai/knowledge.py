"""What a player can work out about the cards, shared by all the bots.

Everything here only uses information a player is allowed to have: the cards
they can see, the trump and the cards already played. The cards nobody has
shown yet are called "unseen": each of them can be in any opponent's hand.
"""

from collections import Counter
from collections.abc import Iterable, Sequence

from src.backend.cards import Card, Color, Deck, Jester, Wizard
from src.backend.view import PlayerView

FULL_DECK: tuple[Card, ...] = tuple(Deck(0).cards)


def unseen_cards(known: Iterable[Card]) -> list[Card]:
    """The cards of the deck that are not among the `known` ones.

    Equal cards (the four Wizards, the four Jesters) are counted one by one.
    """
    remaining = Counter(FULL_DECK)
    remaining.subtract(known)
    return list(remaining.elements())


def beats(challenger: Card, holder: Card, trump: Color | None) -> bool:
    """Would `challenger`, played after `holder`, take the lead of the trick?

    `holder` is the card currently winning the trick, so it is either a Wizard,
    a Jester, a trump or a card of the led suit.
    """
    if isinstance(holder, Wizard):
        return False  # the first Wizard wins
    if isinstance(challenger, Wizard):
        return True
    if isinstance(challenger, Jester):
        return False
    if isinstance(holder, Jester):
        return True
    if challenger.color == holder.color:
        return challenger.number > holder.number
    return challenger.color == trump  # a trump beats any other suit


def trick_winner(plays: Sequence[tuple[str, Card]], trump: Color | None) -> str:
    """Who wins a trick made of `plays` (player name, card), in play order."""
    winner_name, winner_card = plays[0]
    for name, card in plays[1:]:
        if beats(card, winner_card, trump):
            winner_name, winner_card = name, card
    return winner_name


def card_power(card: Card, trump: Color | None) -> int:
    """A rough strength to sort cards: Jester < plain cards < trumps < Wizard."""
    if isinstance(card, Wizard):
        return 100
    if isinstance(card, Jester):
        return -1
    if card.color == trump:
        return 50 + card.number
    return card.number


def beat_fraction(card: Card, unseen: Sequence[Card], trump: Color | None) -> float:
    """The share of unseen cards that would take the lead from `card`."""
    if not unseen:
        return 0.0
    return sum(beats(other, card, trump) for other in unseen) / len(unseen)


def hold_chance(
    card: Card, unseen: Sequence[Card], trump: Color | None, opponents_left: int
) -> float:
    """The chance that `card` is still winning after `opponents_left` more cards.
    
    Each of them is treated as a random unseen card. Roughly right, since the
    opponents don't know our hand and are bound to follow suit.
    """
    return (1.0 - beat_fraction(card, unseen, trump)) ** opponents_left


def _calibration_exponent(values: Sequence[float], target_mean: float) -> float:
    """The power g >= 1 that makes the average of `v ** g` equal `target_mean`."""
    if sum(values) / len(values) <= target_mean:
        return 1.0
    low, high = 1.0, 30.0
    for _ in range(40):
        middle = (low + high) / 2
        if sum(v**middle for v in values) / len(values) > target_mean:
            low = middle
        else:
            high = middle
    return high # the values are probabilities (< 1)


def expected_tricks(hand: Sequence[Card], unseen: Sequence[Card], trump: Color | None, opponents: int) -> float:
    """How many tricks `hand` should win, adding up what each card can do.
    
    Treating every card as if it led the trick is too optimistic: an average
    hand would be worth more than its fair share of (hand size / players) tricks. So the
    chances are shrunk (raised to a power) until an average card is worth
    exactly 1 / players. Sure winners, like the Wizards, stay at 1.
    """
    pool = [hold_chance(card, unseen, trump, opponents) for card in (*unseen, *hand)]
    exponent = _calibration_exponent(pool, 1 / (opponents + 1))
    total = sum(hold_chance(card, unseen, trump, opponents) ** exponent for card in hand)
    return min(total, float(len(hand)))


def blind_win_chance(view: PlayerView, unseen: Sequence[Card]) -> float | None:
    """The chance of winning the single trick of round 1, when you see the others'.
    
    Tries every unseen card as or own hidden one. Returns None if the view isn't
    a round where everybody holds one card and we see all the others'.
    """
    others = dict(view.hands)
    if view.own_hand is not None or any(len(cards) != 1 for cards in others.values()):
        return None
    if any(s.name not in others for s in view.players if s.name != view.player_name):
        return None
    wins = 0
    for candidate in unseen:
        plays = [
            (s.name, candidate if s.name == view.player_name else others[s.name][0])
            for s in view.players
        ]
        wins += trick_winner(plays, view.trump.color) == view.player_name
    return wins / len(unseen) if unseen else None