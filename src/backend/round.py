from enum import Enum, auto

from src.backend.cards import Card, Color, Deck, Wizard
from src.backend.player import Player
from src.backend.rules import Direction, PassRule, RoundRules, Visibility
from src.backend.trick import Trick
from src.backend.view import PlayerStatus, PlayerView, Trump


class Phase(Enum):
    CALLING = auto()
    PASSING = auto()
    PLAYING = auto()


class Round:
    """One round of Wizard: deal, trump, calls, passing, tricks, scoring."""

    def __init__(
        self, players: list[Player], deck: Deck, number: int, rules: RoundRules
    ) -> None:
        """`players` must be in calling order: the dealer is the last one."""
        self.players = players
        self.deck = deck
        self.rules = rules
        self.phase = Phase.CALLING
        self.number = number
        self.dealer = players[-1]
        self.trump_card: Card | None = None
        self.trump_color: Color | None = None
        self.trick: Trick | None = None
        self._trick_count: int = 0

    @property
    def is_over(self) -> bool:
        return all(not p.cards for p in self.players)

    @property
    def needs_trump_choice(self) -> bool:
        """True while the dealer still has to pick the suit for a Wizard trump."""
        return isinstance(self.trump_card, Wizard) and self.trump_color is None

    @property
    def pending_pass(self) -> PassRule | None:
        """The passing rule, while the players still have to pass their cards."""
        return self.rules.passing if self.phase is Phase.PASSING else None

    @property
    def trump(self) -> Trump:
        return Trump(self.trump_card, self.trump_color)

    def start(self) -> None:
        """Deals the cards and turns up the trump card.

        If the trump card is a Wizard, the first trick only starts once the
        dealer has called `choose_trump_color`.
        """
        self.deck.reset_deck()
        self.phase = Phase.CALLING
        for player in self.players:
            player.reset_for_round()
        for _ in range(self.number):
            for player in self.players:
                player.add_card_to_hand(self.deck.draw())
        self.trump_card = self.deck.draw() if len(self.deck) > 0 else None
        # Wizard and Jesters have no color: Jester -> no trump,
        # a Wizard stays without trump until the dealer chooses.
        self.trump_color = self.trump_card.color if self.trump_card else None
        if not self.needs_trump_choice:
            self._new_trick()

    def choose_trump_color(self, color: Color) -> None:
        """The dealer's choice of trump suit when the trump card is a Wizard."""
        if not self.needs_trump_choice:
            raise ValueError("There is no trump color to choose.")
        self.trump_color = color
        self._new_trick()

    def _new_trick(self) -> None:
        self._trick_count += 1
        self.trick = Trick(self.players, self.trump_color)

    @property
    def current_player(self) -> Player:
        return self._get_trick().current_player

    def legal_cards(self, player: Player) -> list[Card]:
        return self._get_trick().legal_cards(player)

    def _current_visibility(self) -> Visibility:
        if self.phase is Phase.PASSING:
            # You have to see your cards to choose the ones to pass.
            return Visibility.OWN
        if self.phase is Phase.PLAYING:
            return self.rules.play_visibility
        return self.rules.call_visibility

    def visible_hands(self, viewer: Player) -> list[tuple[str, list[Card]]]:
        """The hands `viewer` may look at right now, as (owner_name, cards)."""
        visibility = self._current_visibility()
        if visibility is Visibility.OWN:
            return [(viewer.name, list(viewer.cards))]
        if visibility is Visibility.OTHERS:
            return [
                (p.name, list(p.cards))
                for p in self.players
                if p is not viewer and p.cards
            ]
        return []

    def view_for(self, player: Player) -> PlayerView:
        """Snapshot of what `player` is allowed to see (plain data, no Players)."""
        plays = self.trick.plays if self.trick is not None else []
        return PlayerView(
            player_name=player.name,
            round_number=self.number,
            dealer_name=self.dealer.name,
            trump=self.trump,
            players=[PlayerStatus.of(p) for p in self.players],
            hands=self.visible_hands(player),
            table=[(p.name, card) for p, card in plays],
        )

    def forbidden_call(self, player: Player) -> int | None:
        """The call `player` isn't allowed to make, or None if any call is fine.

        The dealer (who calls last) can't make the calls add up to the number
        of tricks in the round, so someone always has to be wrong.
        """
        if player is not self.dealer:
            return None
        others = sum(p.call or 0 for p in self.players if p is not player)
        forbidden = self.number - others
        return forbidden if forbidden >= 0 else None

    def set_call(self, player: Player, tricks: int) -> None:
        if self.phase is not Phase.CALLING:
            raise ValueError("The calls are already over.")
        if self.needs_trump_choice:
            raise ValueError("The dealer must choose the trump color first.")
        if tricks > self.number:
            raise ValueError("Can't call more tricks than cards in hand.")
        if tricks == self.forbidden_call(player):
            raise ValueError(
                f"The dealer can't call {tricks}: the calls would add up to "
                f"the {self.number} tricks of the round."
            )
        player.call_tricks(tricks)
        if all(p.call is not None for p in self.players):
            passing = self.rules.passing is not None
            self.phase = Phase.PASSING if passing else Phase.PLAYING

    def pass_target(self, player: Player) -> Player:
        """The player who receives the cards `player` passes.

        `players` is in play order, which goes clockwise around the table, so
        the player on your left is the next one and the one on your right is
        the previous one.
        """
        if self.rules.passing is None:
            raise ValueError("This round has no card passing.")
        step = 1 if self.rules.passing.direction is Direction.LEFT else -1
        index = self.players.index(player)
        return self.players[(index + step) % len(self.players)]

    def check_pass(self, player: Player, chosen: list[Card]) -> None:
        """Raises ValueError unless `chosen` is a valid pass for `player`."""
        rule = self.pending_pass
        if rule is None:
            raise ValueError("There are no cards to pass right now.")
        hand = list(player.cards)
        for card in chosen:
            if card not in hand:
                raise ValueError(f"{player.name} doesn't have {card}.")
            hand.remove(card)

    def pass_cards(self, passes: dict[Player, list[Card]]) -> None:
        """Everybody passes their chosen cards at the same time."""
        # Validate everybody first, so a bad pass can't leave a half-done swap.
        for player in self.players:
            chosen = passes.get(player)
            if chosen is None:
                raise ValueError(f"{player.name} didn't choose cards to pass.")
            self.check_pass(player, chosen)

        received: dict[Player, list[Card]] = {p: [] for p in self.players}
        for player in self.players:
            chosen = passes[player]
            for card in chosen:
                player.remove_card_from_hand(card)
            received[self.pass_target(player)].extend(chosen)
        for player, cards in received.items():
            for card in cards:
                player.add_card_to_hand(card)
        self.phase = Phase.PLAYING

    def play_card(self, player: Player, card: Card) -> None:
        if self.phase is not Phase.PLAYING:
            raise ValueError("Cards can't be played yet.")
        trick = self._get_trick()
        if player is not trick.current_player:
            raise ValueError(f"It's not {player.name}'s turn.")
        if card not in player.cards:
            raise ValueError(f"{player.name} doesn't have {card}.")
        if not trick.is_legal(player, card):
            raise ValueError(f"{card} is not a legal play.")
        trick.add_play(player, player.play_card(card))

    @property
    def trick_plays(self) -> list[tuple[Player, Card]]:
        """The cards played so far in the current trick, in play order."""
        return list(self._get_trick().plays)

    @property
    def trick_is_complete(self) -> bool:
        return self._get_trick().is_complete

    def finish_trick(self) -> Player:
        """Awards the trick; the winner leads the next one."""
        winner = self._get_trick().winner()
        winner.win_trick()
        index = self.players.index(winner)
        # sort the players to make the winner the next to play
        self.players = self.players[index:] + self.players[:index]
        if not self.is_over:
            self._new_trick()
        return winner

    def score(self) -> None:
        for player in self.players:
            player.update_points()

    def _get_trick(self) -> Trick:
        if self.trick is None:
            raise RuntimeError(
                "No trick in progress: the round has not been started, "
                "or the trump color has not been chosen."
            )
        return self.trick
