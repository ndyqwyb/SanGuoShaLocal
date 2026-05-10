from __future__ import annotations

from dataclasses import dataclass
from random import shuffle
from typing import Iterable, Literal, TypedDict


class CardName:
    SHA = "杀"
    SHAN = "闪"
    TAO = "桃"
    ZHUGE_CROSSBOW = "诸葛连弩"
    QINGGANG_SWORD = "青釭剑"
    BAGUA_SHIELD = "八卦阵"
    CHITU = "赤兔"
    ZIXING = "紫骍"
    DILU = "的卢"
    DUEL = "决斗"
    DISMANTLE = "过河拆桥"
    SNATCH = "顺手牵羊"
    EX_NIHILO = "无中生有"
    BORROWED_SWORD = "借刀杀人"
    BARBARIAN_INVASION = "南蛮入侵"
    ARCHER_ATTACK = "万箭齐发"
    PEACH_GARDEN = "桃园结义"
    HARVEST = "五谷丰登"
    NULLIFY = "无懈可击"
    INDULGENCE = "乐不思蜀"
    SUPPLY_SHORTAGE = "兵粮寸断"
    LIGHTNING = "闪电"


CardCategory = Literal["basic", "equip", "trick"]


class CardConfig(TypedDict):
    name: str
    category: CardCategory
    effect_type: str
    play_validator: str
    deck_count: int


DEFAULT_CARD_CONFIGS: tuple[CardConfig, ...] = (
    {
        "name": CardName.SHA,
        "category": "basic",
        "effect_type": "sha_attack",
        "play_validator": "sha_limit",
        "deck_count": 24,
    },
    {
        "name": CardName.SHAN,
        "category": "basic",
        "effect_type": "cannot_play_active",
        "play_validator": "not_playable",
        "deck_count": 14,
    },
    {
        "name": CardName.TAO,
        "category": "basic",
        "effect_type": "tao_heal",
        "play_validator": "injured_only",
        "deck_count": 8,
    },
    {
        "name": CardName.ZHUGE_CROSSBOW,
        "category": "equip",
        "effect_type": "equip_zhuge_crossbow",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.QINGGANG_SWORD,
        "category": "equip",
        "effect_type": "equip_qinggang_sword",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.BAGUA_SHIELD,
        "category": "equip",
        "effect_type": "equip_bagua_shield",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.CHITU,
        "category": "equip",
        "effect_type": "equip_chitu",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.ZIXING,
        "category": "equip",
        "effect_type": "equip_zixing",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.DILU,
        "category": "equip",
        "effect_type": "equip_dilu",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.DUEL,
        "category": "trick",
        "effect_type": "duel",
        "play_validator": "default",
        "deck_count": 4,
    },
    {
        "name": CardName.DISMANTLE,
        "category": "trick",
        "effect_type": "dismantle",
        "play_validator": "default",
        "deck_count": 4,
    },
    {
        "name": CardName.SNATCH,
        "category": "trick",
        "effect_type": "snatch",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.EX_NIHILO,
        "category": "trick",
        "effect_type": "ex_nihilo",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.BORROWED_SWORD,
        "category": "trick",
        "effect_type": "borrowed_sword",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.BARBARIAN_INVASION,
        "category": "trick",
        "effect_type": "barbarian_invasion",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.ARCHER_ATTACK,
        "category": "trick",
        "effect_type": "archer_attack",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.PEACH_GARDEN,
        "category": "trick",
        "effect_type": "peach_garden",
        "play_validator": "default",
        "deck_count": 1,
    },
    {
        "name": CardName.HARVEST,
        "category": "trick",
        "effect_type": "harvest",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.NULLIFY,
        "category": "trick",
        "effect_type": "cannot_play_active",
        "play_validator": "not_playable",
        "deck_count": 2,
    },
    {
        "name": CardName.INDULGENCE,
        "category": "trick",
        "effect_type": "delayed_indulgence",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.SUPPLY_SHORTAGE,
        "category": "trick",
        "effect_type": "delayed_supply_shortage",
        "play_validator": "default",
        "deck_count": 2,
    },
    {
        "name": CardName.LIGHTNING,
        "category": "trick",
        "effect_type": "delayed_lightning",
        "play_validator": "default",
        "deck_count": 1,
    },
)


@dataclass(frozen=True)
class CardDefinition:
    name: str
    category: CardCategory
    effect_type: str
    play_validator: str
    deck_count: int


@dataclass(frozen=True)
class Card:
    name: str
    suit: str = "spade"
    rank: int = 1

    @property
    def is_basic(self) -> bool:
        definition = CARD_DEFINITIONS.get(self.name)
        return definition is not None and definition.category == "basic"

    @property
    def is_equip(self) -> bool:
        definition = CARD_DEFINITIONS.get(self.name)
        return definition is not None and definition.category == "equip"

    @property
    def is_trick(self) -> bool:
        definition = CARD_DEFINITIONS.get(self.name)
        return definition is not None and definition.category == "trick"

    @property
    def is_red(self) -> bool:
        return self.suit in {"heart", "diamond"}


def load_card_definitions(card_configs: Iterable[CardConfig] = DEFAULT_CARD_CONFIGS) -> dict[str, CardDefinition]:
    definitions: dict[str, CardDefinition] = {}
    for item in card_configs:
        name = item["name"].strip()
        effect_type = item["effect_type"].strip()
        play_validator = item["play_validator"].strip()
        deck_count = item["deck_count"]
        if not name:
            raise ValueError("卡牌配置 name 不能为空。")
        if item["category"] not in {"basic", "equip", "trick"}:
            raise ValueError(f"卡牌 {name} 的类别非法：{item['category']}")
        if not effect_type:
            raise ValueError(f"卡牌 {name} 的 effect_type 不能为空。")
        if not play_validator:
            raise ValueError(f"卡牌 {name} 的 play_validator 不能为空。")
        if deck_count < 0:
            raise ValueError(f"卡牌 {name} 的 deck_count 不能为负数。")
        definitions[name] = CardDefinition(
            name=name,
            category=item["category"],
            effect_type=effect_type,
            play_validator=play_validator,
            deck_count=deck_count,
        )
    return definitions


CARD_DEFINITIONS = load_card_definitions()


def build_deck(seed: int | None = None, *, card_definitions: dict[str, CardDefinition] | None = None) -> list[Card]:
    """根据配置构建最小可玩卡堆。"""
    deck: list[Card] = []
    definitions = card_definitions or CARD_DEFINITIONS
    suits = ("spade", "heart", "club", "diamond")
    rank = 1
    for definition in definitions.values():
        for idx in range(definition.deck_count):
            deck.append(Card(definition.name, suit=suits[idx % len(suits)], rank=((rank + idx - 1) % 13) + 1))
        rank = (rank + definition.deck_count) % 13
    if seed is not None:
        import random

        rng = random.Random(seed)
        rng.shuffle(deck)
    else:
        shuffle(deck)
    return deck
