from src.backend.events import GameEvent, GameStarted, RoundScored
from src.backend.rules import ZERO_STREAK_BONUS, ZeroStreakBonus

# How likely a player who keeps its streak alive is to get through each of the
# rounds that are still to come (it's an estimate).
SURVIVAL_PER_ROUND = 0.57


class ZeroStreakWatch:
    """Follows who has broken the zero-call streak, from the public events.

    Register it as an observer of the game (the bots that own one do it from
    their `on_event`).
    """

    def __init__(self, rule: ZeroStreakBonus | None = ZERO_STREAK_BONUS) -> None:
        self.rule = rule
        self._broken: set[str] = set()

    def on_event(self, event: GameEvent) -> None:
        match event:
            case GameStarted():
                self._broken.clear()
            case RoundScored(round_number=number, scores=scores):
                if self.rule is not None and number <= self.rule.until_round:
                    self._broken.update(
                        s.name for s in scores if s.call != 0 or s.tricks_won != 0
                    )
            case _:
                pass

    def is_alive(self, name: str) -> bool:
        """Does `name` still have a perfect streak (and a bonus to play for)?"""
        return self.rule is not None and name not in self._broken

    def zero_bonus(self, name: str, round_number: int) -> float:
        """The bonus points that calling 0 in this round is worth, on average.

        Counted as if the call is a success: the bonus is paid in full at the
        end of the streak, so it's shrunk for every round that is still to be
        played after this one.
        """
        if self.rule is None or round_number > self.rule.until_round:
            return 0.0
        if not self.is_alive(name):
            return 0.0
        rounds_left = self.rule.until_round - round_number
        return self.rule.points * SURVIVAL_PER_ROUND**rounds_left
