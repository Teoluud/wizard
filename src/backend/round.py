from src.backend.player import Player


class Round:

    def __init__(self, players: list[Player], id: int) -> None:
        self.players = players
        self.id = id
