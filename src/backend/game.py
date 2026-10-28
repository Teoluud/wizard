from src.frontend.interface import GameInterface
from src.backend.cards import Card, Deck
from src.backend.player import Player
from src.backend.round import Round
from src.backend.rules import PassRule, rules_for


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
        round_ = Round(order, self.deck, number, rules_for(number))
        round_.start()

        if round_.needs_trump_choice:
            color = self.interface.ask_trump_color(round_.view_for(round_.dealer))
            round_.choose_trump_color(color)

        for player in round_.players:
            call = self.interface.ask_call(
                round_.view_for(player), round_.forbidden_call(player)
            )
            round_.set_call(player, call)

        pass_rule = round_.pending_pass
        if pass_rule is not None:
            self._pass_cards(round_, pass_rule)

        while not round_.is_over:
            while not round_.trick_is_complete:
                player = round_.current_player
                card = self.interface.ask_card(
                    round_.view_for(player), round_.legal_cards(player)
                )
                round_.play_card(player, card)
            # finish_trick() starts the next trick, so grab the table first
            table = round_.trick_plays
            winner = round_.finish_trick()
            self.interface.show_trick_winner(winner, table)

        round_.score()
        self.interface.show_scores(self.players)

    def _pass_cards(self, round_: Round, rule: PassRule) -> None:
        """Everybody chooses their cards to pass first, then they are swapped at once."""
        passes: dict[Player, list[Card]] = {}
        for player in round_.players:
            passes[player] = self.interface.ask_card_to_pass(
                round_.view_for(player), rule, round_.pass_target(player)
            )
        round_.pass_cards(passes)
