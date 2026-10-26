from collections import deque

from src.backend.cards import Deck
from src.backend.player import Player
from src.backend.game import Game


def wizard() -> None:
    deck = Deck()

    players: deque[Player] = deque(
        [Player("Matteo"), Player("Frassa"), Player("Stefano")]
    )

    game = Game(list(players), deck)

    game.deal_cards(n_cards=2)

    for _ in range(0, 3):
        # print(list(map(str, players)))
        players.rotate(-1)

    game.players[0].call_tricks(1)
    game.players[0].win_trick()
    game.players[0].update_points()

    print(game.players[0])


if __name__ == "__main__":
    wizard()
