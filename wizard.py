import asyncio

from src.backend.cards import Deck
from src.backend.game import Game
from src.backend.player import Player
from src.frontend.cli import CliInterface


def wizard() -> None:
    players = [Player("Matteo"), Player("Frassa"), Player("Stefano")]
    cli = CliInterface()
    # Hot-seat: the same terminal plays for every seat and shows every event.
    agents = {player.name: cli for player in players}
    game = Game(players, Deck(), agents, [cli])
    asyncio.run(game.play())


if __name__ == "__main__":
    wizard()
