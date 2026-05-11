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

SI_MA_YI = GeneralDefinition(
    name="司马懿",
    max_hp=3,
    skills=(
        SkillDefinition(
            name="反馈",
            kind="passive",
            trigger="after_damage",
            description="当你受到1点伤害后，你可以获得伤害来源的一张牌。",
        ),
        SkillDefinition(
            name="鬼才",
            kind="passive",
            trigger="before_judge",
            description="在任意角色的判定牌生效前，你可以打出一张手牌代替之。",
        ),
    ),
)

GUO_JIA = GeneralDefinition(
    name="郭嘉",
    max_hp=3,
    skills=(
        SkillDefinition(
            name="天妒",
            kind="passive",
            trigger="after_judge",
            description="当你的判定牌生效后，你可以获得此判定牌。",
        ),
        SkillDefinition(
            name="遗计",
            kind="passive",
            trigger="after_damage",
            description="当你受到1点伤害后，你可以摸两张牌，然后可以将任意张手牌交给其他角色。",
        ),
    ),
)

XIA_HOU_DUN = GeneralDefinition(
    name="夏侯惇",
    max_hp=4,
    skills=(
        SkillDefinition(
            name="刚烈",
            kind="passive",
            trigger="after_damage",
            description="当你受到1点伤害后，你可以进行判定，若结果不为红桃，则伤害来源选择弃置两张牌或受到1点伤害。",
        ),
    ),
)

ZHOU_YU = GeneralDefinition(
    name="周瑜",
    max_hp=3,
    skills=(
        SkillDefinition(
            name="英姿",
            kind="passive",
            trigger="draw_phase",
            description="锁定技，你的摸牌阶段额外摸一张牌。",
        ),
        SkillDefinition(
            name="反间",
            kind="active",
            trigger="play_phase",
            description="出牌阶段限一次，你可以令一名其他角色选择一种花色，然后你展示并交给其一张手牌，若花色不同，则其受到1点伤害。",
        ),
    ),
)

HUANG_GAI = GeneralDefinition(
    name="黄盖",
    max_hp=4,
    skills=(
        SkillDefinition(
            name="苦肉",
            kind="active",
            trigger="play_phase",
            description="出牌阶段，你可以失去1点体力，然后摸两张牌。",
        ),
    ),
)

GENERAL_POOL: tuple[GeneralDefinition, ...] = (
    GUAN_YU,
    ZHANG_FEI,
    HUANG_YUEYING,
    HUA_TUO,
    SI_MA_YI,
    GUO_JIA,
    XIA_HOU_DUN,
    ZHOU_YU,
    HUANG_GAI,
)


def get_general_by_name(name: str) -> GeneralDefinition:
    for general in GENERAL_POOL:
        if general.name == name:
            return general
    raise ValueError(f"未知武将：{name}")
