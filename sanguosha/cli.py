from __future__ import annotations

from typing import Callable

from .game import Game
from .player import Player


GameFactory = Callable[[Player, Player], Game]


def _default_game_factory(
    human: Player,
    ai: Player,
    *,
    input_func: Callable[[str], str],
    output_func: Callable[[str], None],
) -> Game:
    return Game(human, ai, input_func=input_func, output_func=output_func)


def run_cli(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    game_factory: GameFactory | None = None,
) -> None:
    output_func("=== 本地 1v1 三国杀（最小核心）===")
    player_name = input_func("请输入你的名字（默认 玩家 ）: ").strip() or "玩家"
    factory = game_factory or (
        lambda human, ai: _default_game_factory(human, ai, input_func=input_func, output_func=output_func)
    )
    while True:
        human = Player(name=player_name, is_ai=False)
        ai = Player(name="电脑", is_ai=True)
        game = factory(human, ai)
        winner = game.run()
        if winner is None:
            output_func("对局异常结束（超过最大回合）。")
        else:
            output_func(f"对局结束，胜者：{winner.name}")
        again = input_func("是否再来一局？(y/n): ").strip().lower()
        if again != "y":
            output_func("感谢游玩。")
            return
