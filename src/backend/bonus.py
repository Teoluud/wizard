from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.backend.player import Player
from src.backend.rules import ZeroStreakBonus


@dataclass(frozen=True)
class Award:
    """Points a player earned on top of their score for the round."""

    player: str
    points: int
    reason: str


class ZeroStreakTracker:
    """Follows who still has a perfect streak of successful calls of 0.

    Call `record_round` after every round has been scored; it says who earns
    the bonus once the last round of the streak is over.
    """

    def __init__(self, rule: ZeroStreakBonus, names: Iterable[str]) -> None:
        self._rule = rule
        self._alive = set(names)

    def record_round(self, round_number: int, players: Sequence[Player]) -> list[Award]:
        """Updates the streaks with the round just played; returns the awards."""
        if round_number > self._rule.until_round:
            return []
        for player in players:
            if player.call != 0 or player.tricks_won != 0:
                self._alive.discard(player.name)
        if round_number < self._rule.until_round:
            return []
        reason = f"called 0 and won no tricks in rounds 1-{self._rule.until_round}"
        return [
            Award(player.name, self._rule.points, reason)
            for player in players
            if player.name in self._alive
        ]
