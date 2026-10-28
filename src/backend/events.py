from dataclasses import dataclass

from src.backend.cards import Card, Color
from src.backend.rules import Direction
from src.backend.view import PlayerStatus, Trump


@dataclass(frozen=True)
class GameStarted:
    players: list[str]  # in seating order
    n_rounds: int


@dataclass(frozen=True)
class RoundStarted:
    round_number: int
    dealer: str
    trump: Trump


@dataclass(frozen=True)
class TrumpChosen:
    """The dealer picked the trump suit because the trump card is a Wizard."""

    dealer: str
    color: Color


@dataclass(frozen=True)
class CallMade:
    player: str
    call: int


@dataclass(frozen=True)
class CardsPassed:
    """Everybody swapped cards. Who gave what stays secret."""

    count: int
    direction: Direction


@dataclass(frozen=True)
class CardPlayed:
    player: str
    card: Card


@dataclass(frozen=True)
class TrickWon:
    winner: str
    table: list[tuple[str, Card]]


@dataclass(frozen=True)
class RoundScored:
    round_number: int
    scores: list[PlayerStatus]


@dataclass(frozen=True)
class GameOver:
    scores: list[PlayerStatus]



GameEvent = (
    GameStarted
    | RoundStarted
    | TrumpChosen
    | CallMade
    | CardsPassed
    | CardPlayed
    | TrickWon
    | RoundScored
    | GameOver
)