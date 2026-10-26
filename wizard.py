from src.backend.cards import Deck
from src.backend.game import Game
from src.backend.player import Player
from src.frontend.cli import CliInterface


def wizard() -> None:
    players = [Player("Matteo"), Player("Frassa"), Player("Stefano")]
    game = Game(players, Deck(), CliInterface())
    game.play()


if __name__ == "__main__":
    wizard()