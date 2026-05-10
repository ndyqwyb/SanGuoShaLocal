from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    kind: str
    trigger: str
    description: str


@dataclass(frozen=True)
class GeneralDefinition:
    name: str
    max_hp: int
    skills: tuple[SkillDefinition, ...]


GUAN_YU = GeneralDefinition(
    name="关羽",
    max_hp=4,
    skills=(
        SkillDefinition(
            name="武圣",
            kind="active",
            trigger="play_phase",
            description="你可以将一张红色牌当【杀】使用或打出。",
        ),
    ),
)

ZHANG_FEI = GeneralDefinition(
    name="张飞",
    max_hp=4,
    skills=(
        SkillDefinition(
            name="咆哮",
            kind="passive",
            trigger="play_phase",
            description="锁定技，你使用【杀】无次数限制。",
        ),
    ),
)

HUANG_YUEYING = GeneralDefinition(
    name="黄月英",
    max_hp=3,
    skills=(
        SkillDefinition(
            name="集智",
            kind="passive",
            trigger="after_use_trick",
            description="当你使用非延时锦囊牌时，你可以摸一张牌。",
        ),
        SkillDefinition(
            name="奇才",
            kind="passive",
            trigger="play_phase",
            description="锁定技，你使用锦囊牌无距离限制。",
        ),
    ),
)

HUA_TUO = GeneralDefinition(
    name="华佗",
    max_hp=3,
    skills=(
        SkillDefinition(
            name="青囊",
            kind="active",
            trigger="play_phase",
            description="出牌阶段限一次，你可以弃置一张手牌，令一名角色回复1点体力。",
        ),
        SkillDefinition(
            name="急救",
            kind="passive",
            trigger="dying",
            description="你的回合外，你可以将一张红色牌当【桃】使用。",
        ),
    ),
)

GENERAL_POOL: tuple[GeneralDefinition, ...] = (
    GUAN_YU,
    ZHANG_FEI,
    HUANG_YUEYING,
    HUA_TUO,
)


def get_general_by_name(name: str) -> GeneralDefinition:
    for general in GENERAL_POOL:
        if general.name == name:
            return general
    raise ValueError(f"未知武将：{name}")
