from src.frontend.interface import GameInterface
from src.backend.cards import Deck
from src.backend.player import Player
from src.backend.round import Round


class Game:
    """Orchestrates the whole match and talks to the interface"""

    def __init__(
        self, players: list[Player], deck: Deck, interface: GameInterface
    ) -> None:
        print("Starting game...")
        self.players = players
        self.deck = deck
        self.interface = interface
        self.n_rounds = len(deck) // len(players)

    def play(self) -> None:
        for number in range(1, self.n_rounds + 1):
            self._play_round(number)
        self.interface.show_scores(self.players)

    def _play_round(self, number: int) -> None:
        shift = number % len(self.players)
        order = self.players[shift:] + self.players[:shift]
        round_ = Round(order, self.deck, number)
        round_.start()

        for player in round_.players:
            call = self.interface.ask_call(player, number, round_.trump_card)
            round_.set_call(player, call)

        while not round_.is_over:
            while not round_.trick_is_complete:
                player = round_.current_player
                card = self.interface.ask_card(player, round_.legal_cards(player))
                round_.play_card(player, card)
            self.interface.show_trick_winner(round_.finish_trick())

        round_.score()
        self.interface.show_scores(self.players)
