from __future__ import annotations

from sanguosha.cli import run_cli
from sanguosha.player import Player


class DummyGame:
    def __init__(self, human: Player, ai: Player) -> None:
        self.human = human
        self.ai = ai

    def run(self) -> Player:
        return self.human


def test_cli_uses_local_players_and_default_name() -> None:
    answers = iter(["", "n"])
    outputs: list[str] = []
    created: list[tuple[Player, Player]] = []

    def fake_input(_: str) -> str:
        return next(answers)

    def fake_output(msg: str) -> None:
        outputs.append(msg)

    def game_factory(human: Player, ai: Player) -> DummyGame:
        created.append((human, ai))
        return DummyGame(human, ai)

    run_cli(input_func=fake_input, output_func=fake_output, game_factory=game_factory)

    assert len(created) == 1
    human, ai = created[0]
    assert human.name == "玩家"
    assert human.is_ai is False
    assert ai.name == "电脑"
    assert ai.is_ai is True
    assert any("本地 1v1 三国杀" in line for line in outputs)


def test_cli_restart_flow_starts_new_game_instances() -> None:
    answers = iter(["测试", "y", "n"])
    created: list[tuple[Player, Player]] = []

    def fake_input(_: str) -> str:
        return next(answers)

    def game_factory(human: Player, ai: Player) -> DummyGame:
        created.append((human, ai))
        return DummyGame(human, ai)

    run_cli(input_func=fake_input, output_func=lambda _: None, game_factory=game_factory)

    assert len(created) == 2
    assert created[0][0] is not created[1][0]
    assert created[0][1] is not created[1][1]
    assert created[0][0].name == "测试"
    assert created[1][0].name == "测试"
