from src.backend.cards import Card, Color, Deck
from src.backend.player import Player
from src.backend.trick import Trick


class Round:
    """One round of Wizard: deal, trump, tricks, scoring."""

    def __init__(self, players: list[Player], deck: Deck, number: int) -> None:
        self.players = players
        self.deck = deck
        self.number = number
        self.trump_card: Card | None = None
        self.trick: Trick | None = None
        self._trick_count: int = 0

    @property
    def trump_color(self) -> Color | None:
        return self.trump_card.color if self.trump_card else None

    @property
    def is_over(self) -> bool:
        return all(not p.cards for p in self.players)

    def start(self) -> None:
        self.deck.reset_deck()
        for player in self.players:
            player.reset_for_round()
        for _ in range(self.number):
            for player in self.players:
                player.add_card_to_hand(self.deck.draw())
        self.trump_card = self.deck.draw() if len(self.deck) > 0 else None
        self._new_trick()

    def _new_trick(self) -> None:
        self._trick_count += 1
        self.trick = Trick(self.players, self.trump_color)

    @property
    def current_player(self) -> Player:
        return self._get_trick().current_player

    def legal_cards(self, player: Player) -> list[Card]:
        return self._get_trick().legal_cards(player)

    def set_call(self, player: Player, tricks: int) -> None:
        if tricks > self.number:
            raise ValueError("Can't call more tricks than cards in hand.")
        player.call_tricks(tricks)

    def play_card(self, player: Player, card: Card) -> None:
        trick = self._get_trick()
        if player is not trick.current_player:
            raise ValueError(f"It's not {player.name}'s turn.")
        if not trick.is_legal(player, card):
            raise ValueError(f"{card} is not a legal play.")
        trick.add_play(player, player.play_card(card))

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
            raise RuntimeError("Round has not been started.")
        return self.trick
