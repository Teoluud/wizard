"""Terminal front end for a networked Wizard client.

Every time the player has to decide, the screen is redrawn as a small
dashboard (round, trump, scores, table, hand); what happens in between is
printed live as a short feed.
"""

import os
import sys
from collections import deque

from src.backend.cards import Card, Color, Jester, Wizard
from src.backend.events import (
    CallMade,
    CardPlayed,
    CardsPassed,
    GameEvent,
    GameOver,
    GameStarted,
    RoundScored,
    RoundStarted,
    TrickWon,
    TrumpChosen,
)
from src.backend.rules import PassRule
from src.backend.view import PlayerStatus, PlayerView, Trump

_CLEAR_SCREEN = "\033[H\033[2J"
_WIDTH = 56
_FEED_LINES = 10

_SUIT_STYLE: dict[Color, str] = {
    Color.RED: "91",
    Color.YELLOW: "93",
    Color.BLUE: "94",
    Color.GREEN: "92",
}
_WIZARD_STYLE = "1;95"
_JESTER_STYLE = "90"


class NetworkCliAgent:
    """Single-seat terminal UI: a `PlayerAgent` and a `GameObserver` in one.

    `name` is the player's own name, used to highlight it in the feed.
    Colors are used only on a terminal (and never if NO_COLOR is set).
    """

    def __init__(self, name: str | None = None, color: bool | None = None) -> None:
        self._me = name
        self._color = (
            sys.stdout.isatty() and "NO_COLOR" not in os.environ
            if color is None
            else color
        )
        self._n_rounds = 0
        self._seats: list[str] = []
        self._points: dict[str, int] = {}
        self._feed: deque[str] = deque(maxlen=_FEED_LINES)
        self._last_trick = ""

    # --- PlayerAgent --------------------------------------------------------

    async def ask_trump_color(self, view: PlayerView) -> Color:
        self._draw(view)
        print("The trump card is a Wizard: you are the dealer, choose the trump suit.")
        colors = list(Color)
        for i, color in enumerate(colors, start=1):
            print(f"  {i}) {self._suit(color)}")
        return colors[self._ask_index("Trump suit: ", len(colors)) - 1]

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        self._draw(view)
        if not view.can_see_own_hand:
            print("Blind call: you can't see your own cards yet.")
        if forbidden_call is not None:
            print(f"You are the dealer: you can't call {forbidden_call}.")
        while True:
            raw = input(f"How many tricks do you call (0-{view.round_number})? ")
            try:
                call = int(raw)
            except ValueError:
                print("Please enter a whole number.")
                continue
            if not 0 <= call <= view.round_number:
                print(f"The call must be between 0 and {view.round_number}.")
            elif call == forbidden_call:
                print(f"As the dealer, you can't call {forbidden_call}.")
            else:
                return call

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        self._draw(view)
        print(
            f"Pass {rule.count} cards to {self._who(recipient)} "
            f"(the player on your {rule.direction.value})."
        )
        remaining = self._sorted(view.own_hand or [])
        passed: list[Card] = []
        for n in range(1, rule.count + 1):
            for i, card in enumerate(remaining, start=1):
                print(f"  {i}) {self._card(card)}")
            choice = self._ask_index(f"Card {n} of {rule.count}: ", len(remaining))
            passed.append(remaining.pop(choice - 1))
        return passed

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        self._draw(view, legal_cards)
        if not view.can_see_own_hand:
            input("Press Enter to play your hidden card...")
            return legal_cards[0]
        playable = self._sorted(legal_cards)
        if len(playable) == 1:
            input(f"Only {self._card(playable[0])} is playable. Press Enter...")
            return playable[0]
        return playable[self._ask_index("Play a card: ", len(playable)) - 1]

    # --- GameObserver -------------------------------------------------------

    async def on_event(self, event: GameEvent) -> None:
        match event:
            case GameStarted(players=players, n_rounds=n_rounds):
                self._seats = list(players)
                self._n_rounds = n_rounds
                self._points = {name: 0 for name in players}
                print(f"Game of {n_rounds} rounds: {', '.join(players)}")
            case RoundStarted(round_number=number, dealer=dealer, trump=trump):
                self._feed.clear()
                self._say(
                    self._bold(f"Round {number}")
                    + f" - dealer {dealer}, trump {self._trump(trump)}",
                    keep=False,
                    live_prefix="\n",
                )
            case TrumpChosen(dealer=dealer, color=color):
                self._say(f"{self._who(dealer)} chose {self._suit(color)} as trump")
            case CallMade(player=player, call=call):
                self._say(f"{self._who(player)} called {call}")
            case CardsPassed(count=count, direction=direction):
                self._say(f"Everybody passed {count} cards to the {direction.value}")
            case CardPlayed(player=player, card=card):
                self._say(f"{self._who(player)} played {self._card(card)}", keep=False)
            case TrickWon(winner=winner, table=table):
                plays = ", ".join(f"{p} {self._card(c)}" for p, c in table)
                self._last_trick = f"{plays} -> {self._who(winner)}"
                self._say(f"{self._bold('Trick:')} {self._who(winner)} wins")
            case RoundScored(round_number=number, scores=scores):
                self._say(self._round_summary(number, scores))
                self._points = {s.name: s.points for s in scores}
            case GameOver(scores=scores):
                self._show_final(scores)

    # --- drawing ------------------------------------------------------------

    def _draw(self, view: PlayerView, legal_cards: list[Card] | None = None) -> None:
        """Clears the screen and shows the whole situation of the player."""
        print(_CLEAR_SCREEN, end="")
        rule = "-" * _WIDTH
        total = f" of {self._n_rounds}" if self._n_rounds else ""
        print(self._bold(f"WIZARD - Round {view.round_number}{total}"), end="")
        print(f" - dealer {view.dealer_name}")
        print(f"Trump: {self._trump(view.trump)}")
        print(rule)
        self._print_scores(view)
        print(rule)
        print(f"On the table: {self._table(view.table)}")
        if self._last_trick:
            print(self._dim(f"Last trick:   {self._last_trick}"))
        print(rule)
        for line in self._feed:
            print(self._dim(f"  {line}"))
        if self._feed:
            print(rule)
        self._print_hands(view, legal_cards)
        print()

    def _print_scores(self, view: PlayerView) -> None:
        print(self._dim(f"  {'Player':<18}{'Call':>5}{'Won':>5}{'Points':>8}"))
        for status in self._in_seat_order(view.players):
            marker = ">" if status.name == view.player_name else " "
            name = status.name + (" (you)" if marker == ">" else "")
            call = "-" if status.call is None else str(status.call)
            line = f"{marker} {name:<18}{call:>5}{status.tricks_won:>5}"
            line += f"{status.points:>8}"
            print(self._bold(line) if marker == ">" else line)

    def _print_hands(
        self, view: PlayerView, legal_cards: list[Card] | None = None
    ) -> None:
        for owner, cards in view.hands:
            if owner != view.player_name:
                print(f"{self._who(owner)}'s cards: {self._hand_line(cards)}")
        own = view.own_hand
        if own is None:
            print("Your cards: (hidden)")
            return
        print("Your hand:")
        playable = None if legal_cards is None else self._sorted(legal_cards)
        number = 0
        for card in self._sorted(own):
            if playable is not None and card not in playable:
                print(self._dim(f"     {self._plain(card)}  (can't play)"))
                continue
            number += 1
            print(f"  {number:>2}) {self._card(card)}")
        if playable is not None and not playable:
            print("  (nothing to play)")

    def _hand_line(self, cards: list[Card]) -> str:
        return ", ".join(self._card(c) for c in self._sorted(cards))

    def _round_summary(self, number: int, scores: list[PlayerStatus]) -> str:
        parts: list[str] = []
        for s in self._in_seat_order(scores):
            gain = s.points - self._points.get(s.name, 0)
            parts.append(f"{s.name} {gain:+d} ({s.tricks_won}/{s.call})")
        return f"Round {number} scored: " + ", ".join(parts)

    def _show_final(self, scores: list[PlayerStatus]) -> None:
        print("\n" + self._bold("Final scores"))
        ranking = sorted(scores, key=lambda s: s.points, reverse=True)
        for place, s in enumerate(ranking, start=1):
            print(f"  {place}. {self._who(s.name):<18}{s.points:>6}")
        if ranking:
            print(f"\n{self._who(ranking[0].name)} wins!")

    def _say(self, text: str, keep: bool = True, live_prefix: str = "") -> None:
        """Prints a line right away; `keep` also shows it in the next dashboards.

        The cards played are not kept: the table and the last trick show them.
        """
        if keep:
            self._feed.append(text)
        print(f"{live_prefix}  {text}")

    # --- formatting ---------------------------------------------------------

    def _in_seat_order(self, statuses: list[PlayerStatus]) -> list[PlayerStatus]:
        """The table order of the game, not the order in which people act."""
        if not self._seats:
            return statuses
        known = {s.name: s for s in statuses}
        ordered = [known[name] for name in self._seats if name in known]
        return ordered if len(ordered) == len(statuses) else statuses

    @staticmethod
    def _sorted(cards: list[Card]) -> list[Card]:
        """Wizards first, then each suit from high to low, Jesters last."""

        def key(card: Card) -> tuple[int, str, int]:
            if isinstance(card, Wizard):
                return (0, "", 0)
            if isinstance(card, Jester):
                return (2, "", 0)
            return (1, str(card.color), -card.number)

        return sorted(cards, key=key)

    def _style(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self._color else text

    def _bold(self, text: str) -> str:
        return self._style(text, "1")

    def _dim(self, text: str) -> str:
        return self._style(text, "90")

    def _who(self, name: str) -> str:
        return self._bold(name) if name == self._me else name

    def _suit(self, color: Color) -> str:
        return self._style(str(color), _SUIT_STYLE[color])

    @staticmethod
    def _plain(card: Card) -> str:
        if isinstance(card, Wizard):
            return "Wizard"
        if isinstance(card, Jester):
            return "Jester"
        return f"{card.number} {card.color}"

    def _card(self, card: Card) -> str:
        if isinstance(card, Wizard):
            return self._style("Wizard", _WIZARD_STYLE)
        if isinstance(card, Jester):
            return self._style("Jester", _JESTER_STYLE)
        assert card.color is not None
        return self._style(self._plain(card), _SUIT_STYLE[card.color])

    def _trump(self, trump: Trump) -> str:
        card = trump.card
        if card is None:
            return "none (last round)"
        if isinstance(card, Jester):
            return "none (the card is a Jester)"
        if isinstance(card, Wizard):
            if trump.color is None:
                return "Wizard (the dealer picks the suit)"
            return f"Wizard -> {self._suit(trump.color)}"
        return self._card(card)

    def _table(self, table: list[tuple[str, Card]]) -> str:
        if not table:
            return "(empty, you lead)"
        return ", ".join(f"{self._who(p)} {self._card(c)}" for p, c in table)

    @staticmethod
    def _ask_index(prompt: str, size: int) -> int:
        """Asks until the player enters a number between 1 and `size`."""
        while True:
            raw = input(prompt)
            try:
                choice = int(raw)
            except ValueError:
                print("Please enter a number.")
                continue
            if 1 <= choice <= size:
                return choice
            print(f"Choose a number between 1 and {size}.")
