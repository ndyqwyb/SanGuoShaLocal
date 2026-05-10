"""本地 1v1 三国杀最小核心包。"""

from .cards import Card, CardName, build_deck
from .generals import GENERAL_POOL, GeneralDefinition, SkillDefinition
from .game import AIStrategyConfig, Game
from .player import Player

__all__ = [
    "Card",
    "CardName",
    "build_deck",
    "Game",
    "Player",
    "GENERAL_POOL",
    "GeneralDefinition",
    "SkillDefinition",
]
