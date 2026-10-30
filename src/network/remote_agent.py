import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeVar

from src.backend.agents import GameObserver, PlayerAgent
from src.backend.cards import Card, Color
from src.backend.events import GameEvent
from src.backend.rules import PassRule
from src.backend.view import PlayerView
from src.network.protocol import JsonCodec, JsonStream

T = TypeVar("T")

# Everything a client can do wrong: vanish (OSError also covers timeouts), or
# answer with something that isn't what was asked.
_CLIENT_FAULTS = (OSError, ValueError, KeyError, TypeError)


class RemotePlayerAgent:
    """Server-side proxy for a remote client.

    Implements both `PlayerAgent` and `GameObserver`, so the `Game` registers it
    for events and only ever sends it its own `PlayerView`. If the client
    disconnects, times out or sends an invalid answer, the proxy drops it and
    the `fallback` bot plays from then on. The bot also follows every event, so
    it knows what was played when it takes over.
    """

    def __init__(
        self,
        name: str,
        stream: JsonStream,
        fallback: PlayerAgent,
        turn_timeout: float | None,
    ) -> None:
        self.name = name
        self._stream = stream
        self._fallback = fallback
        self._turn_timeout = turn_timeout
        self._connected = True

    @property
    def connected(self) -> bool:
        return self._connected

    # --- PlayerAgent --------------------------------------------------------

    async def ask_trump_color(self, view: PlayerView) -> Color:
        return await self._ask(
            "ask_trump_color",
            lambda reply: Color(reply["color"]),
            lambda: self._fallback.ask_trump_color(view),
            view=JsonCodec.encode_view(view),
        )

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        def parse(reply: Mapping[str, Any]) -> int:
            call = int(reply["call"])
            if not 0 <= call <= view.round_number or call == forbidden_call:
                raise ValueError(f"call {call} is not allowed")
            return call

        return await self._ask(
            "ask_call",
            parse,
            lambda: self._fallback.ask_call(view, forbidden_call),
            view=JsonCodec.encode_view(view),
            forbidden_call=forbidden_call,
        )

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        def parse(reply: Mapping[str, Any]) -> list[Card]:
            cards = [Card.from_dict(c) for c in reply["cards"]]
            remaining = list(view.own_hand or [])
            if len(cards) != rule.count:
                raise ValueError(f"expected {rule.count} cards, got {len(cards)}")
            for card in cards:
                remaining.remove(card)  # ValueError if it isn't in the hand
            return cards

        return await self._ask(
            "ask_card_to_pass",
            parse,
            lambda: self._fallback.ask_card_to_pass(view, rule, recipient),
            view=JsonCodec.encode_view(view),
            rule=JsonCodec.encode_pass_rule(rule),
            recipient=recipient,
        )

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        def parse(reply: Mapping[str, Any]) -> Card:
            card = Card.from_dict(reply["card"])
            if card not in legal_cards:
                raise ValueError(f"{card} is not a legal card")
            return card

        return await self._ask(
            "ask_card",
            parse,
            lambda: self._fallback.ask_card(view, legal_cards),
            view=JsonCodec.encode_view(view),
            legal_cards=[c.to_dict() for c in legal_cards],
        )

    # --- GameObserver -------------------------------------------------------

    async def on_event(self, event: GameEvent) -> None:
        if isinstance(self._fallback, GameObserver):
            await self._fallback.on_event(event)
        if not self._connected:
            return
        try:
            await self._stream.send(
                {"kind": "event", "data": JsonCodec.encode_event(event)}
            )
        except OSError as error:
            await self._drop(f"could not send an event ({error!r})")

    # --- connection ---------------------------------------------------------

    async def close(self) -> None:
        await self._stream.close()

    async def _ask(
        self,
        action: str,
        parse: Callable[[Mapping[str, Any]], T],
        fallback: Callable[[], Awaitable[T]],
        **payload: Any,
    ) -> T:
        """Asks the client; if it fails, the bot answers instead (for good)."""
        if self._connected:
            try:
                reply = await asyncio.wait_for(
                    self._request(action, **payload), self._turn_timeout
                )
                return parse(reply)
            except _CLIENT_FAULTS as error:
                await self._drop(f"{action} failed ({error!r})")
        return await fallback()

    async def _request(self, action: str, **payload: Any) -> dict[str, Any]:
        await self._stream.send({"kind": "request", "action": action, **payload})
        response = await self._stream.receive()
        if response.get("kind") != "response":
            raise ValueError(f"Expected response packet, got: {response}")
        return response

    async def _drop(self, reason: str) -> None:
        """Gives the seat to the bot. A late answer would desync, so don't wait."""
        if not self._connected:
            return
        self._connected = False
        print(f"{self.name} dropped ({reason}): a bot takes over the seat.")
        await self._stream.close()
