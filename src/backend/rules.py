from dataclasses import dataclass
from enum import Enum, StrEnum, auto


class Visibility(Enum):
    """Which hands a player can look at."""

    OWN = auto()
    OTHERS = auto()
    NONE = auto()


class Direction(StrEnum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True)
class PassRule:
    """Every player passes `count` cards to their neighbor on `direction`."""

    count: int
    direction: Direction


@dataclass(frozen=True)
class RoundRules:
    """The special rules of a single round (the defaults are a normal round)."""

    call_visibility: Visibility = Visibility.OWN
    play_visibility: Visibility = Visibility.OWN
    passing: PassRule | None = None


# Round with special rules: every other round is a normal one.
SPECIAL_ROUNDS: dict[int, RoundRules] = {
    # Everybody sees the other's cards, but never their own.
    1: RoundRules(call_visibility=Visibility.OTHERS, play_visibility=Visibility.OTHERS),
    # Players call blind, then look at their own cards to play.
    6: RoundRules(call_visibility=Visibility.NONE),
    # After calling, everybody passes two cards to the player on the right...
    8: RoundRules(passing=PassRule(count=2, direction=Direction.RIGHT)),
    # ...or on their left
    9: RoundRules(passing=PassRule(count=2, direction=Direction.LEFT)),
}


def rules_for(round_number: int) -> RoundRules:
    return SPECIAL_ROUNDS.get(round_number, RoundRules())
