import asyncio

import pytest

from src.backend.cards import Deck
from src.backend.game import Game
from src.frontend.cli import CliInterface
from tests.helpers import new_players

# What the CLI prints to wipe the screen between players.
CLEAR_SCREEN = "\033[H\033[2J\033[3J"


def fake_input(prompt: str = "") -> str:
    """Calls 0 tricks, picks the first option everywhere, Enter otherwise."""
    if "how many tricks" in prompt:
        return "0"
    if "Choose" in prompt or "to pass" in prompt:
        return "1"
    return ""


def test_the_cli_plays_a_whole_game_without_leaking_hands(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", fake_input)
    players = new_players()
    cli = CliInterface()
    agents = {p.name: cli for p in players}
    asyncio.run(Game(players, Deck(1), agents, [cli]).play())

    out = capsys.readouterr().out
    assert "Starting game..." in out
    assert "Final scores:" in out

    screens = out.split(CLEAR_SCREEN)
    blind = [s for s in screens if "You can't see your own cards" in s]
    assert blind, "rounds 1 and 6 should show blind screens"
    assert all("Your hand:" not in s for s in blind)

    passing = [s for s in screens if "Pass 2 cards" in s]
    assert any("=== Round 8 ===" in s and "on your right" in s for s in passing)
    assert any("=== Round 9 ===" in s and "on your left" in s for s in passing)
