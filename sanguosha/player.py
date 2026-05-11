from __future__ import annotations

from dataclasses import dataclass, field

from .cards import Card


@dataclass
class Player:
    name: str
    is_ai: bool = False
    general: str | None = None
    max_hp: int = 4
    hp: int = 4
    hand: list[Card] = field(default_factory=list)
    weapon: Card | None = None
    armor: Card | None = None
    plus_horse: Card | None = None
    minus_horse: Card | None = None
    judgment_area: list[Card] = field(default_factory=list)
    sha_used_this_turn: int = 0
    extra_attack_limit: int = 0
    alive: bool = True
    skip_play_phase: bool = False
    skip_draw_phase: bool = False
    ignore_armor_on_sha: bool = False
    qingnang_used_this_turn: bool = False
    fanjian_used_this_turn: bool = False

    def reset_for_turn(self) -> None:
        self.sha_used_this_turn = 0
        self.skip_play_phase = False
        self.skip_draw_phase = False
        self.ignore_armor_on_sha = False
        self.qingnang_used_this_turn = False
        self.fanjian_used_this_turn = False

    def attack_limit(self) -> int:
        return 1 + self.extra_attack_limit

    def attack_range(self) -> int:
        if self.weapon is None:
            return 1
        if self.weapon.name == "青釭剑":
            return 2
        return 1

    def offense_distance_mod(self) -> int:
        return 1 if self.minus_horse is not None else 0

    def defense_distance_mod(self) -> int:
        return 1 if self.plus_horse is not None else 0

    def draw(self, cards: list[Card]) -> None:
        self.hand.extend(cards)

    def has_card(self, name: str) -> bool:
        return any(card.name == name for card in self.hand)

    def remove_one(self, name: str) -> Card | None:
        for idx, card in enumerate(self.hand):
            if card.name == name:
                return self.hand.pop(idx)
        return None

    def heal(self, amount: int = 1) -> None:
        self.hp = min(self.max_hp, self.hp + amount)

    def take_damage(self, amount: int = 1) -> None:
        self.hp -= amount

    def hand_limit(self) -> int:
        return max(self.hp, 0)
