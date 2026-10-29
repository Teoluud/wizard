from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypeVar

from src.backend.agents import GameObserver, PlayerAgent
from src.backend.cards import Card, Deck
from src.backend.events import (
    CallMade,
    CardPlayed,
    CardsPassed,
    GameEvent,
    GameOver,
    GameStarted,
    RoundScored,
    RoundStarted,
    TrickWon,
    TrumpChosen,
)
from src.backend.player import Player
from src.backend.round import Round
from src.backend.rules import PassRule, rules_for
from src.backend.view import PlayerStatus

T = TypeVar("T")

# How many times an agent can give an answer the rules reject before giving up.
MAX_ATTEMPTS = 3


class InvalidMoveError(Exception):
    """An agent kept answering with something the rules don't allow."""


class Game:
    """Orchestrates the whole match.

    The Game never prints or reads input: it asks the agent of each seat
    for decisions and tells the observers what happens.
    """

    def __init__(
        self,
        players: list[Player],
        deck: Deck,
        agents: Mapping[str, PlayerAgent],
        observers: Sequence[GameObserver] = (),
    ) -> None:
        """`agents` maps each player's name to the agent that plays for them."""
        names = [p.name for p in players]
        if len(set(names)) != len(names):
            raise ValueError("Player names must be unique.")
        missing = [name for name in names if name not in agents]
        if missing:
            raise ValueError(f"No agent for: {', '.join(missing)}.")
        self.players = players
        self.deck = deck
        self.agents = agents
        # An agent that is also an observer (the CLI, a bot that counts cards)
        # gets the events too, without being listed twice
        self.observers: list[GameObserver] = list(observers)
        for agent in agents.values():
            if isinstance(agent, GameObserver) and not any(
                agent is observer for observer in self.observers
            ):
                self.observers.append(agent)

        self.n_rounds = len(deck) // len(players)

    async def play(self) -> None:
        await self._emit(GameStarted([p.name for p in self.players], self.n_rounds))
        for number in range(1, self.n_rounds + 1):
            await self._play_round(number)
        await self._emit(GameOver(self._scores()))

    async def _play_round(self, number: int) -> None:
        shift = number % len(self.players)
        order = self.players[shift:] + self.players[:shift]
        round_ = Round(order, self.deck, number, rules_for(number))
        round_.start()
        await self._emit(RoundStarted(number, round_.dealer.name, round_.trump))

        if round_.needs_trump_choice:
            await self._choose_trump(round_)
        await self._calls(round_)
        pass_rule = round_.pending_pass
        if pass_rule is not None:
            await self._pass_cards(round_, pass_rule)
        await self._tricks(round_)

        round_.score()
        await self._emit(RoundScored(number, self._scores()))

    async def _choose_trump(self, round_: Round) -> None:
        dealer = round_.dealer
        agent = self.agents[dealer.name]
        view = round_.view_for(dealer)
        color = await self._ask_until_valid(
            dealer, lambda: agent.ask_trump_color(view), round_.choose_trump_color
        )
        await self._emit(TrumpChosen(dealer.name, color))

    async def _calls(self, round_: Round) -> None:
        for player in round_.players:
            agent = self.agents[player.name]
            view = round_.view_for(player)
            forbidden = round_.forbidden_call(player)
            call = await self._ask_until_valid(
                player,
                lambda: agent.ask_call(view, forbidden),
                lambda c: round_.set_call(player, c),
            )
            await self._emit(CallMade(player.name, call))

    async def _pass_cards(self, round_: Round, rule: PassRule) -> None:
        """Everybody chooses their cards to pass first, then they are swapped."""
        passes: dict[Player, list[Card]] = {}
        for player in round_.players:
            agent = self.agents[player.name]
            view = round_.view_for(player)
            recipient = round_.pass_target(player).name
            passes[player] = await self._ask_until_valid(
                player,
                lambda: agent.ask_card_to_pass(view, rule, recipient),
                lambda cards: round_.check_pass(player, cards),
            )
        round_.pass_cards(passes)
        await self._emit(CardsPassed(rule.count, rule.direction))

    async def _tricks(self, round_: Round) -> None:
        """Handles all the tricks in the `round_`."""
        while not round_.is_over:
            while not round_.trick_is_complete:
                player = round_.current_player
                agent = self.agents[player.name]
                view = round_.view_for(player)
                legal_cards = round_.legal_cards(player)
                card = await self._ask_until_valid(
                    player,
                    lambda: agent.ask_card(view, legal_cards),
                    lambda c: round_.play_card(player, c),
                )
                await self._emit(CardPlayed(player.name, card))
            # finish_trick() starts the next trick, so grab the whole table first
            table = [(p.name, card) for p, card in round_.trick_plays]
            winner = round_.finish_trick()
            await self._emit(TrickWon(winner.name, table))

    async def _ask_until_valid(
        self,
        player: Player,
        ask: Callable[[], Awaitable[T]],
        apply: Callable[[T], None],
    ) -> T:
        """Asks until the rules accept the answer.

        `apply` raises ValueError when the answer is not allowed. The engine is
        the referee: it never trusts an agent (a remote client can send anything).
        """
        last_error: ValueError | None = None
        for _ in range(MAX_ATTEMPTS):
            try:
                answer = await ask()
                apply(answer)
            except ValueError as error:
                last_error = error
                continue
            return answer
        raise InvalidMoveError(
            f"{player.name} gave {MAX_ATTEMPTS} invalid answers in a row: {last_error}."
        )

    def _scores(self) -> list[PlayerStatus]:
        return [PlayerStatus.of(p) for p in self.players]

    async def _emit(self, event: GameEvent) -> None:
        """Emits the event for all the observers."""
        for observer in self.observers:
            await observer.on_event(event)
