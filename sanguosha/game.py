from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterable

from .cards import Card, CardConfig, CardDefinition, CardName, build_deck, load_card_definitions
from .generals import GENERAL_POOL, GeneralDefinition, get_general_by_name
from .player import Player, Role
from .skills import ACTIVE_SKILL_HANDLERS, PASSIVE_SKILL_HANDLERS


@dataclass
class ActionResult:
    ok: bool
    message: str


PassiveSkillHandler = Callable[..., object | None]
ActiveSkillHandler = Callable[["Game", Player, Player], ActionResult]
CardEffectHandler = Callable[[Player, Player, Card, CardDefinition], ActionResult]
CardValidator = Callable[[Player, Player, Card, CardDefinition], ActionResult | None]


@dataclass(frozen=True)
class AIStrategyConfig:
    tao_play_hp_threshold: int = 3
    low_hp_risk_threshold: int = 2
    shan_response_hp_threshold: int = 4
    shan_min_reserve: int = 0
    duel_sha_response_hp_threshold: int = 2
    duel_sha_min_reserve: int = 1
    kill_window_hp_threshold: int = 1


@dataclass(frozen=True)
class AIEvaluation:
    threat_value: float
    hand_value: float
    hp_risk: float
    kill_chance: float
    aggression: float


class Game:
    def __init__(
        self,
        player: Player,
        enemy: Player,
        *,
        seed: int | None = None,
        ai_config: AIStrategyConfig | None = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
        available_generals: tuple[GeneralDefinition, ...] = GENERAL_POOL,
        card_configs: Iterable[CardConfig] | None = None,
    ) -> None:
        self.player = player
        self.enemy = enemy
        self.players = [player, enemy]
        self._assign_default_roles()
        self.rng = random.Random(seed)
        self.ai_config = ai_config or AIStrategyConfig()
        self.input = input_func
        self.output = output_func
        self.general_pool = available_generals
        self.turn_index = 0
        self.winner: Player | None = None
        self.passive_skill_registry: dict[str, list[tuple[Player, str, PassiveSkillHandler]]] = {}
        self.active_skill_registry: dict[int, list[tuple[str, ActiveSkillHandler]]] = {}
        if card_configs is None:
            self.card_definitions = load_card_definitions()
        else:
            self.card_definitions = load_card_definitions(card_configs)
        self.draw_pile = build_deck(seed=seed, card_definitions=self.card_definitions)
        self.discard_pile: list[Card] = []
        self.effect_registry: dict[str, CardEffectHandler] = {
            "sha_attack": self._effect_sha_attack,
            "cannot_play_active": self._effect_cannot_play_active,
            "tao_heal": self._effect_tao_heal,
            "equip_zhuge_crossbow": self._effect_equip_weapon,
            "equip_qinggang_sword": self._effect_equip_weapon,
            "equip_bagua_shield": self._effect_equip_armor,
            "equip_chitu": self._effect_equip_minus_horse,
            "equip_zixing": self._effect_equip_plus_horse,
            "equip_dilu": self._effect_equip_plus_horse,
            "duel": self._effect_duel,
            "dismantle": self._effect_dismantle,
            "snatch": self._effect_snatch,
            "ex_nihilo": self._effect_ex_nihilo,
            "borrowed_sword": self._effect_borrowed_sword,
            "barbarian_invasion": self._effect_barbarian_invasion,
            "archer_attack": self._effect_archer_attack,
            "peach_garden": self._effect_peach_garden,
            "harvest": self._effect_harvest,
            "delayed_indulgence": self._effect_delayed_indulgence,
            "delayed_supply_shortage": self._effect_delayed_supply_shortage,
            "delayed_lightning": self._effect_delayed_lightning,
            "direct_damage_1": self._effect_direct_damage_1,
        }
        self.play_validator_registry: dict[str, CardValidator] = {
            "default": self._validate_default,
            "sha_limit": self._validate_sha_limit,
            "not_playable": self._validate_not_playable,
            "injured_only": self._validate_injured_only,
        }

    def setup(self) -> None:
        self._choose_generals()
        self._register_generals_skills()
        self.rng.shuffle(self.players)
        for p in self.players:
            self.draw_cards(p, 4)
            self.output(f"{p.name} 选择武将：{p.general}（体力上限{p.max_hp}）")
        self.output(f"先手：{self.current_player().name}")

    def _assign_default_roles(self) -> None:
        if len(self.players) == 2:
            self.player.role = Role.LORD
            self.enemy.role = Role.REBEL

    def _alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def _index_of_player(self, p: Player) -> int:
        return self.players.index(p)

    def _iter_ccw_alive(self, start: Player) -> list[Player]:
        alive = [p for p in self.players if p.alive]
        if not alive:
            return []
        start_idx = self._index_of_player(start)
        res: list[Player] = []
        n = len(self.players)
        i = start_idx
        visited = 0
        while visited < n:
            cur = self.players[i]
            if cur.alive:
                res.append(cur)
            i = (i - 1) % n
            visited += 1
        return res

    def _human_player(self) -> Player:
        for p in self.players:
            if not p.is_ai:
                return p
        return self.players[0]

    def make_action_result(self, ok: bool, message: str) -> ActionResult:
        return ActionResult(ok=ok, message=message)

    def current_player(self) -> Player:
        return self.players[self.turn_index % 2]

    def other_player(self, p: Player) -> Player:
        return self.enemy if p is self.player else self.player

    def draw_cards(self, p: Player, n: int) -> None:
        for _ in range(n):
            if not self.draw_pile:
                if not self.discard_pile:
                    return
                self.draw_pile = self.discard_pile[:]
                self.discard_pile.clear()
                self.rng.shuffle(self.draw_pile)
            p.hand.append(self.draw_pile.pop())

    def draw_judge_card(self) -> Card | None:
        if not self.draw_pile and self.discard_pile:
            self.draw_pile = self.discard_pile[:]
            self.discard_pile.clear()
            self.rng.shuffle(self.draw_pile)
        if not self.draw_pile:
            return None
        return self.draw_pile.pop()

    def discard(self, card: Card) -> None:
        self.discard_pile.append(card)

    def _format_card_short(self, card: Card) -> str:
        suit_map = {"heart": "♥", "diamond": "♦", "club": "♣", "spade": "♠"}
        symbol = suit_map.get(card.suit, card.suit)
        return f"{card.name} {symbol}{card.rank}"

    def lose_hp(self, victim: Player, amount: int = 1) -> None:
        victim.hp -= amount
        if victim.alive and victim.hp <= 0:
            self._enter_dying(victim, self.other_player(victim))

    def deal_damage(
        self,
        source: Player | None,
        victim: Player,
        amount: int = 1,
        *,
        card: Card | None = None,
        reason: str = "",
    ) -> None:
        self._deal_damage(source, victim, amount, card=card, reason=reason)

    def run_judgment(self, judge_owner: Player, *, reason_card: Card | None = None, reason_text: str = "") -> Card | None:
        return self._run_judgment(judge_owner, reason_card=reason_card, reason_text=reason_text)

    def _deal_damage(
        self,
        source: Player | None,
        victim: Player,
        amount: int,
        *,
        card: Card | None = None,
        reason: str = "",
    ) -> None:
        victim.take_damage(amount)
        if victim.alive and victim.hp <= 0:
            attacker = source if source is not None else self.other_player(victim)
            survived = self._enter_dying(victim, attacker)
            if not survived:
                return
        self._trigger_event("after_damage", victim=victim, source=source, amount=amount, card=card, reason=reason)

    def _run_judgment(self, judge_owner: Player, *, reason_card: Card | None = None, reason_text: str = "") -> Card | None:
        judge = self.draw_judge_card()
        if judge is None:
            return None
        self.output(f"[判定] {judge_owner.name} 判定牌：{self._format_card_short(judge)}")
        final = judge
        for owner, _, handler in self.passive_skill_registry.get("before_judge", []):
            if not owner.alive:
                continue
            replaced = handler(self, owner, judge_owner=judge_owner, judge_card=final, reason_card=reason_card, reason_text=reason_text)
            if isinstance(replaced, Card):
                owner.hand.append(final)
                self.output(f"[结算] {owner.name} 获得判定牌：{self._format_card_short(final)}")
                final = replaced
                self.output(f"[判定] {judge_owner.name} 判定牌被替换为：{self._format_card_short(final)}")
        taken = False
        for owner, _, handler in self.passive_skill_registry.get("after_judge", []):
            if not owner.alive:
                continue
            res = handler(self, owner, judge_owner=judge_owner, judge_card=final, reason_card=reason_card, reason_text=reason_text)
            if res is True and owner is judge_owner:
                owner.hand.append(final)
                taken = True
        if not taken:
            self.discard(final)
        return final

    def run(self, max_rounds: int = 200) -> Player | None:
        self.setup()
        rounds = 0
        while self.winner is None and rounds < max_rounds:
            self.run_turn(self.current_player())
            if self.winner is None:
                self.turn_index += 1
            rounds += 1
        return self.winner

    def run_turn(self, actor: Player) -> None:
        if not actor.alive or self.winner is not None:
            return
        target = self.other_player(actor)
        actor.reset_for_turn()
        self._trigger_event("turn_start", actor=actor, target=target)
        self.output(f"\n== {actor.name} 的回合 ==")
        self._resolve_judgment_area(actor)
        if actor.skip_draw_phase:
            self.output(f"{actor.name} 受【兵粮寸断】影响，跳过摸牌阶段。")
        else:
            bonus = 0
            for owner, _, handler in self.passive_skill_registry.get("draw_phase", []):
                if owner is actor and owner.alive:
                    res = handler(self, owner, actor=actor)
                    if isinstance(res, int):
                        bonus += res
            draw_n = 2 + max(0, bonus)
            self.draw_cards(actor, draw_n)
            self.output(f"{actor.name} 摸{draw_n}张，当前手牌 {len(actor.hand)}")
        if actor.skip_play_phase:
            self.output(f"{actor.name} 受【乐不思蜀】影响，跳过出牌阶段。")
        else:
            if actor.is_ai:
                self._ai_play_phase(actor, target)
            else:
                self._human_play_phase(actor, target)
        self.output(f"{actor.name} 进入弃牌阶段（当前体力={actor.hp}，手牌上限={max(actor.hp, 0)}）。")
        self._discard_to_limit(actor)
        self._check_death(target, actor)
        self._check_death(actor, target)

    def _resolve_judgment_area(self, actor: Player) -> None:
        if not actor.judgment_area:
            return
        pending = actor.judgment_area[:]
        actor.judgment_area.clear()
        for delayed in pending:
            if self._is_delayed_trick_countered(actor, delayed):
                self.output(f"[结算] {actor.name} 判定区的【{delayed.name}】被无懈可击抵消。")
                if delayed.name == CardName.LIGHTNING:
                    next_player = self.other_player(actor)
                    if not self._has_delayed(next_player, CardName.LIGHTNING):
                        next_player.judgment_area.append(delayed)
                        self.output(f"【闪电】被无懈可击抵消，转移给 {next_player.name}。")
                    else:
                        self.discard(delayed)
                else:
                    self.discard(delayed)
                continue
            judge = self._run_judgment(actor, reason_card=delayed, reason_text=delayed.name)
            if judge is None:
                self.discard(delayed)
                continue
            self.output(f"{actor.name} 判定【{delayed.name}】：{self._format_card_short(judge)}")
            if delayed.name == CardName.INDULGENCE and judge.suit != "heart":
                actor.skip_play_phase = True
            elif delayed.name == CardName.SUPPLY_SHORTAGE and judge.suit != "club":
                actor.skip_draw_phase = True
            elif delayed.name == CardName.LIGHTNING:
                if judge.suit == "spade" and 2 <= judge.rank <= 9:
                    self._deal_damage(None, actor, 3, card=delayed, reason="闪电")
                    self.output(f"{actor.name} 受到【闪电】3点伤害（剩余{actor.hp}）。")
                else:
                    next_player = self.other_player(actor)
                    if not self._has_delayed(next_player, CardName.LIGHTNING):
                        next_player.judgment_area.append(delayed)
                        self.output(f"【闪电】转移给 {next_player.name}。")
                        continue
            self.discard(delayed)

    def _discard_to_limit(self, p: Player) -> None:
        limit = max(p.hp, 0)
        discarded = 0
        need = len(p.hand) - limit
        if need <= 0:
            self.output(f"[结算] {p.name} 弃牌阶段结束：弃置0张，剩余手牌{len(p.hand)}。")
            return
        if p.is_ai:
            while len(p.hand) > limit:
                idx = self._choose_ai_discard_index(p)
                card = p.hand.pop(idx)
                self.discard(card)
                discarded += 1
                self.output(f"[结算] {p.name} 弃置 {card.name}")
        else:
            indexes = self._ask_discard_indexes(p, need)
            for idx in sorted(indexes, reverse=True):
                card = p.hand.pop(idx)
                self.discard(card)
                discarded += 1
                self.output(f"[结算] {p.name} 弃置 {card.name}")
        self.output(f"[结算] {p.name} 弃牌阶段结束：弃置{discarded}张，剩余手牌{len(p.hand)}。")

    def _ask_discard_indexes(self, player: Player, need_count: int) -> list[int]:
        while True:
            hand_info = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(player.hand))
            ans = self.input(f"弃牌选择：需弃{need_count}张，请选择编号（空格分隔） {hand_info}: ").strip()
            parts = [p for p in ans.split() if p]
            if len(parts) != need_count:
                self.output("[信息] 选择数量不正确，请重试。")
                continue
            if not all(p.isdigit() for p in parts):
                self.output("[信息] 编号格式错误，请重试。")
                continue
            indexes = [int(p) for p in parts]
            if len(set(indexes)) != need_count:
                self.output("[信息] 不能重复选择同一张牌。")
                continue
            if all(0 <= idx < len(player.hand) for idx in indexes):
                return indexes
            self.output("[信息] 选择无效，请重试。")

    def _choose_ai_discard_index(self, player: Player) -> int:
        weights = {
            CardName.TAO: 100,
            CardName.SHAN: 50,
            CardName.SHA: 20,
        }
        best_idx = 0
        best_score = 10**9
        for idx, card in enumerate(player.hand):
            score = weights.get(card.name, 10)
            if score < best_score:
                best_score = score
                best_idx = idx
        return best_idx

    def _choose_ai_discard_indexes(self, player: Player, need_count: int) -> list[int]:
        chosen: list[int] = []
        for _ in range(need_count):
            idx = self._choose_ai_discard_index(player)
            while idx in chosen and len(chosen) < len(player.hand):
                idx = (idx + 1) % len(player.hand)
            chosen.append(idx)
        return sorted(set(chosen))[:need_count]

    def _distance(self, actor: Player, target: Player) -> int:
        base = 1
        mod = target.defense_distance_mod() - actor.offense_distance_mod()
        return max(1, base + mod)

    def _in_attack_range(self, actor: Player, target: Player) -> bool:
        return self._distance(actor, target) <= actor.attack_range()

    def _human_play_phase(self, actor: Player, target: Player) -> None:
        while True:
            if self.winner is not None:
                return
            active_skills = self.active_skill_registry.get(id(actor), [])
            if active_skills:
                skills_msg = " ".join(f"[s{i}] {name}" for i, (name, _) in enumerate(active_skills))
                self.output(f"[信息] 可用主动技能：{skills_msg}")
            cmd = self.input("输入牌序号出牌，输入 s序号 发动技能，或输入 p 结束出牌阶段: ").strip()
            if cmd.lower() == "p":
                return
            if cmd.lower().startswith("s") and cmd[1:].isdigit():
                res = self._use_active_skill(actor, target, int(cmd[1:]))
                if res.message:
                    self.output(res.message)
                continue
            if not cmd.isdigit():
                self.output("[信息] 输入无效。")
                continue
            idx = int(cmd)
            res = self.play_card(actor, target, idx)
            if res.message:
                self.output(res.message)

    def _ai_play_phase(self, actor: Player, target: Player) -> None:
        while self.winner is None:
            if self._ai_use_active_skill(actor, target):
                continue
            idx = self._choose_ai_action(actor, target)
            if idx is None:
                return
            res = self.play_card(actor, target, idx)
            if res.message:
                self.output(res.message)
            if not res.ok:
                return

    def _evaluate_ai_state(self, actor: Player, target: Player) -> AIEvaluation:
        hand_weights = {
            CardName.SHA: 1.2,
            CardName.SHAN: 1.5,
            CardName.TAO: 2.5,
            CardName.ZHUGE_CROSSBOW: 1.2,
            CardName.QINGGANG_SWORD: 1.2,
            CardName.BAGUA_SHIELD: 1.3,
            CardName.DUEL: 1.3,
            CardName.DISMANTLE: 1.1,
            CardName.SNATCH: 1.1,
            CardName.EX_NIHILO: 1.6,
        }
        hand_value = sum(hand_weights.get(card.name, 1.0) for card in actor.hand)
        threat_value = float(len(target.hand)) * 0.4 + float(target.hp) * 0.8 + (0.8 if target.weapon else 0.0)
        hp_risk = max(0.0, float(self.ai_config.low_hp_risk_threshold - actor.hp))
        attack_left = max(0, actor.attack_limit() - actor.sha_used_this_turn)
        sha_count = sum(1 for c in actor.hand if c.name == CardName.SHA)
        has_duel = any(c.name == CardName.DUEL for c in actor.hand)
        potential_damage = min(attack_left, sha_count) + (1 if has_duel else 0)
        kill_chance = 1.0 if target.hp <= potential_damage else 0.0
        aggression = threat_value + kill_chance * 2.0 - hp_risk * 1.5
        return AIEvaluation(threat_value, hand_value, hp_risk, kill_chance, aggression)

    def _choose_ai_action(self, actor: Player, target: Player) -> int | None:
        eval_state = self._evaluate_ai_state(actor, target)
        best_idx: int | None = None
        best_score = float("-inf")
        for idx, card in enumerate(actor.hand):
            score: float | None = None
            if card.name == CardName.TAO:
                if actor.hp >= actor.max_hp or actor.hp > self.ai_config.tao_play_hp_threshold:
                    continue
                score = 9.0 + eval_state.hp_risk * 2.0
            elif card.name == CardName.SHA:
                if not self._can_use_sha(actor) or not self._in_attack_range(actor, target):
                    continue
                score = 5.0 + eval_state.aggression * 0.4
            elif card.name in (CardName.ZHUGE_CROSSBOW, CardName.QINGGANG_SWORD):
                if actor.weapon is not None and actor.weapon.name == card.name:
                    continue
                score = 5.2
            elif card.name == CardName.BAGUA_SHIELD:
                if actor.armor is not None:
                    continue
                score = 5.0
            elif card.name in (CardName.CHITU, CardName.ZIXING, CardName.DILU):
                score = 4.6
            elif card.name in (CardName.DISMANTLE, CardName.SNATCH):
                score = 6.0 + eval_state.threat_value * 0.3
            elif card.name == CardName.EX_NIHILO:
                score = 7.0
            elif card.name in (CardName.DUEL, CardName.BARBARIAN_INVASION, CardName.ARCHER_ATTACK):
                score = 5.6 + eval_state.kill_chance * 3.0
            elif card.name in (CardName.INDULGENCE, CardName.SUPPLY_SHORTAGE):
                score = 5.4
            elif card.name == CardName.LIGHTNING:
                score = 4.5 if not self._has_delayed(actor, CardName.LIGHTNING) else -1.0
            if score is not None and score > best_score:
                best_score = score
                best_idx = idx
        return best_idx

    def _first_index(self, p: Player, name: str) -> int | None:
        for idx, card in enumerate(p.hand):
            if card.name == name:
                return idx
        return None

    def play_card(self, actor: Player, target: Player, hand_index: int) -> ActionResult:
        if hand_index < 0 or hand_index >= len(actor.hand):
            return ActionResult(False, "索引越界。")
        card = actor.hand[hand_index]
        target = self._resolve_effective_target(actor, target, card.name)
        definition = self.card_definitions.get(card.name)
        if definition is None:
            return ActionResult(False, f"未知卡牌：{card.name}")
        validator = self.play_validator_registry.get(definition.play_validator)
        if validator is None:
            return ActionResult(False, f"卡牌【{card.name}】未注册合法性校验：{definition.play_validator}")
        validation = validator(actor, target, card, definition)
        if validation is not None:
            return validation
        extra_validation = self._validate_card_target(actor, target, card)
        if extra_validation is not None:
            return extra_validation
        handler = self.effect_registry.get(definition.effect_type)
        if handler is None:
            return ActionResult(False, f"卡牌【{card.name}】未注册效果处理器：{definition.effect_type}")
        actor.hand.pop(hand_index)
        result = handler(actor, target, card, definition)
        if result.ok and definition.category == "trick":
            self._trigger_event("after_use_trick", actor=actor, target=target, card=card)
        return result

    def _resolve_effective_target(self, actor: Player, target: Player, card_name: str) -> Player:
        self_target_cards = {
            CardName.TAO,
            CardName.ZHUGE_CROSSBOW,
            CardName.QINGGANG_SWORD,
            CardName.BAGUA_SHIELD,
            CardName.CHITU,
            CardName.ZIXING,
            CardName.DILU,
            CardName.EX_NIHILO,
            CardName.PEACH_GARDEN,
            CardName.HARVEST,
            CardName.LIGHTNING,
        }
        if card_name in self_target_cards:
            return actor
        return target

    def _validate_card_target(self, actor: Player, target: Player, card: Card) -> ActionResult | None:
        if card.name == CardName.SHA and not self._in_attack_range(actor, target):
            return ActionResult(False, "目标不在你的攻击范围内。")
        if card.name == CardName.SNATCH and actor.general != "黄月英" and self._distance(actor, target) > 1:
            return ActionResult(False, "【顺手牵羊】距离不足。")
        if card.name == CardName.BORROWED_SWORD and target.weapon is None:
            return ActionResult(False, "【借刀杀人】目标没有武器。")
        return None

    def _validate_default(self, __: Player, ___: Player, ____: Card, _____: CardDefinition) -> ActionResult | None:
        return None

    def _can_use_sha(self, actor: Player) -> bool:
        if actor.general == "张飞":
            return True
        if actor.weapon is not None and actor.weapon.name == CardName.ZHUGE_CROSSBOW:
            return True
        return actor.sha_used_this_turn < actor.attack_limit()

    def _validate_sha_limit(self, actor: Player, __: Player, ___: Card, ____: CardDefinition) -> ActionResult | None:
        if not self._can_use_sha(actor):
            return ActionResult(False, "本回合使用【杀】次数已达上限。")
        return None

    def _validate_not_playable(self, __: Player, ___: Player, card: Card, ____: CardDefinition) -> ActionResult | None:
        return ActionResult(False, f"【{card.name}】不能主动使用。")

    def _validate_injured_only(self, actor: Player, __: Player, ___: Card, ____: CardDefinition) -> ActionResult | None:
        if actor.hp >= actor.max_hp:
            return ActionResult(False, "满血时不能使用【桃】。")
        return None

    def _effect_sha_attack(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        actor.sha_used_this_turn += 1
        actor.ignore_armor_on_sha = actor.weapon is not None and actor.weapon.name == CardName.QINGGANG_SWORD
        self.discard(card)
        self.output(f"[声明] {actor.name} 使用【{card.name}】。")
        self.resolve_sha(actor, target)
        actor.ignore_armor_on_sha = False
        return ActionResult(True, "")

    def _effect_cannot_play_active(self, __: Player, ___: Player, card: Card, ____: CardDefinition) -> ActionResult:
        self.discard(card)
        return ActionResult(False, f"【{card.name}】不能主动使用。")

    def _effect_tao_heal(self, actor: Player, __: Player, card: Card, ___: CardDefinition) -> ActionResult:
        self.discard(card)
        self.output(f"[声明] {actor.name} 使用【{card.name}】。")
        actor.heal(1)
        self.output(f"[结算] {actor.name} 回复1点体力。")
        return ActionResult(True, "")

    def _effect_equip_weapon(self, actor: Player, __: Player, card: Card, ___: CardDefinition) -> ActionResult:
        if actor.weapon is not None:
            self.discard(actor.weapon)
        actor.weapon = card
        return ActionResult(True, f"{actor.name} 装备了【{card.name}】。")

    def _effect_equip_armor(self, actor: Player, __: Player, card: Card, ___: CardDefinition) -> ActionResult:
        if actor.armor is not None:
            self.discard(actor.armor)
        actor.armor = card
        return ActionResult(True, f"{actor.name} 装备了【{card.name}】。")

    def _effect_equip_plus_horse(self, actor: Player, __: Player, card: Card, ___: CardDefinition) -> ActionResult:
        if actor.plus_horse is not None:
            self.discard(actor.plus_horse)
        actor.plus_horse = card
        return ActionResult(True, f"{actor.name} 装备了【{card.name}】。")

    def _effect_equip_minus_horse(self, actor: Player, __: Player, card: Card, ___: CardDefinition) -> ActionResult:
        if actor.minus_horse is not None:
            self.discard(actor.minus_horse)
        actor.minus_horse = card
        return ActionResult(True, f"{actor.name} 装备了【{card.name}】。")

    def _effect_duel(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        self.output(f"[声明] {actor.name} 使用【{card.name}】。")
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"[结算] {actor.name} 的【{card.name}】被无懈可击抵消。")
        self._resolve_duel(actor, target)
        return ActionResult(True, "")

    def _effect_dismantle(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        self.output(f"[声明] {actor.name} 使用【{card.name}】。")
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"[结算] {actor.name} 的【{card.name}】被无懈可击抵消。")
        self._resolve_dismantle(actor, target, gained=False)
        return ActionResult(True, "")

    def _effect_snatch(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        self.output(f"[声明] {actor.name} 使用【{card.name}】。")
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"[结算] {actor.name} 的【{card.name}】被无懈可击抵消。")
        self._resolve_dismantle(actor, target, gained=True)
        return ActionResult(True, "")

    def _effect_ex_nihilo(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"{actor.name} 的【{card.name}】被无懈可击抵消。")
        self.draw_cards(actor, 2)
        return ActionResult(True, f"{actor.name} 使用【无中生有】，摸2张牌。")

    def _effect_borrowed_sword(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"{actor.name} 的【{card.name}】被无懈可击抵消。")
        if self._ask_for_sha(target, duel=False, prompt=f"{target.name} 是否打出【杀】响应【借刀杀人】？(y/n): "):
            self.resolve_sha(target, actor)
            return ActionResult(True, f"{actor.name} 使用【借刀杀人】成功逼出【杀】。")
        if target.weapon is not None:
            stolen = target.weapon
            target.weapon = None
            actor.hand.append(stolen)
            self.output(f"{actor.name} 获得了 {target.name} 的武器【{stolen.name}】。")
        return ActionResult(True, f"{actor.name} 使用【借刀杀人】。")

    def _effect_barbarian_invasion(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"{actor.name} 的【{card.name}】被无懈可击抵消。")
        if self._ask_for_sha(target, duel=False, prompt=f"{target.name} 是否打出【杀】响应【南蛮入侵】？(y/n): "):
            return ActionResult(True, f"{target.name} 打出【杀】响应【南蛮入侵】。")
        self._deal_damage(actor, target, 1, card=card, reason="南蛮入侵")
        self.output(f"{target.name} 未出【杀】，受到1点伤害（剩余{target.hp}）。")
        return ActionResult(True, f"{actor.name} 使用【南蛮入侵】。")

    def _effect_archer_attack(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        if self._is_trick_countered(actor, target, card):
            return ActionResult(True, f"{actor.name} 的【{card.name}】被无懈可击抵消。")
        if self._ask_for_shan(target, prompt=f"{target.name} 是否打出【闪】响应【万箭齐发】？(y/n): ", attacker=actor):
            return ActionResult(True, f"{target.name} 打出【闪】响应【万箭齐发】。")
        self._deal_damage(actor, target, 1, card=card, reason="万箭齐发")
        self.output(f"{target.name} 未出【闪】，受到1点伤害（剩余{target.hp}）。")
        return ActionResult(True, f"{actor.name} 使用【万箭齐发】。")

    def _effect_peach_garden(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        for p in self._iter_ccw_alive(actor):
            effective = self._resolve_nullify_chain(
                starter=actor,
                trick_user=actor,
                trick_name=card.name,
                target=p,
                effective=True,
            )
            if not effective:
                self.output(f"[结算] {p.name} 受到的【{card.name}】效果被无懈可击抵消。")
                continue
            if p.alive:
                p.heal(1)
        return ActionResult(True, f"{actor.name} 使用【桃园结义】。")

    def _effect_harvest(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        self.output(f"[声明] {actor.name} 使用【{card.name}】。")
        pool: list[Card] = []
        for _ in range(sum(1 for p in self.players if p.alive)):
            drawn = self.draw_judge_card()
            if drawn is not None:
                pool.append(drawn)
        if not pool:
            return ActionResult(True, "[结算] 【五谷丰登】无牌可分。")
        self.output("[信息] 五谷展示：" + " ".join(f"[{i}] {self._format_card_short(c)}" for i, c in enumerate(pool)))
        pickers = self._iter_ccw_alive(actor)
        last_picker = pickers[-1] if pickers else actor
        for picker in pickers:
            if not pool:
                break
            effective = self._resolve_nullify_chain(
                starter=actor,
                trick_user=actor,
                trick_name=card.name,
                target=picker,
                effective=True,
            )
            if not effective:
                self.output(f"[结算] {picker.name} 受到的【{card.name}】效果被无懈可击抵消，跳过选牌。")
                continue
            if picker is last_picker and len(pool) == 1:
                card_got = pool.pop(0)
                picker.hand.append(card_got)
                self.output(f"[结算] {picker.name} 直接获得【{card_got.name}】。")
                continue
            idx = self._choose_harvest_index(picker, pool)
            card_got = pool.pop(idx)
            picker.hand.append(card_got)
            self.output(f"[结算] {picker.name} 获得【{card_got.name}】。")
        for remain in pool:
            self.discard(remain)
        return ActionResult(True, "")

    def _choose_harvest_index(self, actor: Player, pool: list[Card]) -> int:
        if len(pool) == 1:
            return 0
        if actor.is_ai:
            return self._score_harvest_for_ai(actor, pool)
        options = " ".join(f"[{i}] {self._format_card_short(c)}" for i, c in enumerate(pool))
        while True:
            ans = self.input(f"五谷选择：{actor.name}请选择1张获得 {options}: ").strip()
            if ans.isdigit() and 0 <= int(ans) < len(pool):
                return int(ans)
            self.output("[信息] 五谷选择无效，请重试。")

    def _score_harvest_for_ai(self, actor: Player, pool: list[Card]) -> int:
        scores: list[float] = []
        for card in pool:
            value = 0.0
            if card.name == CardName.TAO:
                value = 10.0 - actor.hp
            elif card.name == CardName.SHAN:
                value = 7.0
            elif card.name == CardName.NULLIFY:
                value = 6.0
            elif card.name in (CardName.SHA, CardName.DUEL, CardName.BARBARIAN_INVASION, CardName.ARCHER_ATTACK):
                value = 5.0
            elif card.is_equip:
                value = 4.0
            else:
                value = 3.5
            value += 0.5 if actor.hp <= 2 and card.name in (CardName.SHAN, CardName.TAO) else 0.0
            scores.append(value)
        best = max(range(len(pool)), key=lambda i: scores[i])
        return best

    def _effect_delayed_indulgence(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self._place_delayed(target, card)
        return ActionResult(True, f"{actor.name} 对 {target.name} 使用【乐不思蜀】。")

    def _effect_delayed_supply_shortage(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self._place_delayed(target, card)
        return ActionResult(True, f"{actor.name} 对 {target.name} 使用【兵粮寸断】。")

    def _effect_delayed_lightning(self, actor: Player, __: Player, card: Card, ___: CardDefinition) -> ActionResult:
        self._place_delayed(actor, card)
        return ActionResult(True, f"{actor.name} 使用【闪电】。")

    def _effect_direct_damage_1(self, actor: Player, target: Player, card: Card, __: CardDefinition) -> ActionResult:
        self.discard(card)
        self._deal_damage(actor, target, 1, card=card, reason=card.name)
        self.output(f"{target.name} 受到【{card.name}】1点伤害（剩余{target.hp}）。")
        return ActionResult(True, f"{actor.name} 使用【{card.name}】。")

    def _place_delayed(self, target: Player, card: Card) -> None:
        for idx, old in enumerate(target.judgment_area):
            if old.name == card.name:
                self.discard(old)
                target.judgment_area[idx] = card
                return
        target.judgment_area.append(card)

    def _has_delayed(self, target: Player, card_name: str) -> bool:
        return any(card.name == card_name for card in target.judgment_area)

    def resolve_sha(self, actor: Player, target: Player) -> None:
        old_ignore = actor.ignore_armor_on_sha
        actor.ignore_armor_on_sha = actor.weapon is not None and actor.weapon.name == CardName.QINGGANG_SWORD
        try:
            if self._ask_for_shan(target, attacker=actor):
                self.output(f"[响应] {target.name} 打出【闪】，抵消【杀】。")
                return
            self._deal_damage(actor, target, 1, reason="杀")
            self.output(f"[结算] {target.name} 未打出【闪】，受到1点伤害（剩余{target.hp}）。")
        finally:
            actor.ignore_armor_on_sha = old_ignore

    def _resolve_duel(self, actor: Player, target: Player) -> None:
        current = target
        other = actor
        self.output(f"[结算] {actor.name} 与 {target.name} 进入【决斗】。")
        while self.winner is None:
            if self._ask_for_sha(current, duel=True):
                self.output(f"[响应] {current.name} 打出【杀】响应决斗。")
                current, other = other, current
                continue
            self._deal_damage(other, current, 1, reason="决斗")
            self.output(f"[结算] {current.name} 未能打出【杀】，决斗伤害1（剩余{current.hp}）。")
            return

    def _pop_target_asset(self, target: Player, zone: str) -> tuple[str, Card] | None:
        if zone == "h":
            if not target.hand:
                return None
            idx = self.rng.randrange(len(target.hand))
            return "手牌", target.hand.pop(idx)
        if zone == "w" and target.weapon is not None:
            card = target.weapon
            target.weapon = None
            return "武器", card
        if zone == "a" and target.armor is not None:
            card = target.armor
            target.armor = None
            return "防具", card
        if zone == "p" and target.plus_horse is not None:
            card = target.plus_horse
            target.plus_horse = None
            return "+1马", card
        if zone == "m" and target.minus_horse is not None:
            card = target.minus_horse
            target.minus_horse = None
            return "-1马", card
        if zone == "j" and target.judgment_area:
            return "判定区", target.judgment_area.pop(0)
        return None

    def _choose_target_zone(self, actor: Player, target: Player) -> str | None:
        candidates: list[str] = []
        if target.hand:
            candidates.append("h")
        if target.weapon is not None:
            candidates.append("w")
        if target.armor is not None:
            candidates.append("a")
        if target.plus_horse is not None:
            candidates.append("p")
        if target.minus_horse is not None:
            candidates.append("m")
        if target.judgment_area:
            candidates.append("j")
        if not candidates:
            return None
        if actor.is_ai:
            priority = ["w", "a", "p", "m", "h", "j"]
            for code in priority:
                if code in candidates:
                    return code
            return candidates[0]
        while True:
            self.output("[信息] 可选区域：" + " ".join(
                f"[{c}]"
                + {"h": "手牌", "w": "武器", "a": "防具", "p": "+1马", "m": "-1马", "j": "判定区"}[c]
                for c in candidates
            ))
            ans = self.input("区域选择：请选择目标区域代码(h/w/a/p/m/j): ").strip().lower()
            if ans in candidates:
                return ans
            self.output("[信息] 区域选择无效，请重试。")

    def _resolve_dismantle(self, actor: Player, target: Player, *, gained: bool) -> None:
        zone = self._choose_target_zone(actor, target)
        if zone is None:
            self.output(f"[结算] {target.name} 没有可操作的区域。")
            return
        removed = self._pop_target_asset(target, zone)
        if removed is None:
            self.output(f"[结算] {target.name} 目标区域无可用牌。")
            return
        source, card = removed
        if gained:
            actor.hand.append(card)
            self.output(f"[结算] {actor.name} 牵走了 {target.name} 的{source}牌【{card.name}】。")
            return
        self.discard(card)
        self.output(f"[结算] {actor.name} 拆掉了 {target.name} 的{source}牌【{card.name}】。")

    def _resolve_nullify_chain(
        self,
        *,
        starter: Player,
        trick_user: Player | None,
        trick_name: str,
        target: Player,
        effective: bool = True,
    ) -> bool:
        while True:
            played = False
            for p in self._iter_ccw_alive(starter):
                if not p.has_card(CardName.NULLIFY):
                    continue
                if trick_user is not None:
                    if effective:
                        prompt = (
                            f"{trick_user.name} 的 {trick_name} 锦囊即将对 {target.name} 生效，"
                            "是否使用【无懈可击】使其失效？(y/n): "
                        )
                    else:
                        prompt = (
                            f"{trick_user.name} 的 {trick_name} 锦囊即将对 {target.name} 失效，"
                            "是否使用【无懈可击】使其生效？(y/n): "
                        )
                else:
                    if effective:
                        prompt = f"{trick_name} 锦囊即将对 {target.name} 生效，是否使用【无懈可击】使其失效？(y/n): "
                    else:
                        prompt = f"{trick_name} 锦囊即将对 {target.name} 失效，是否使用【无懈可击】使其生效？(y/n): "
                if p.is_ai:
                    want_effective = p.is_enemy_of(target)
                    should_play = (effective and not want_effective) or ((not effective) and want_effective)
                    if not should_play:
                        continue
                    card = p.remove_one(CardName.NULLIFY)
                    if card is None:
                        continue
                    self.discard(card)
                    self.output(f"[响应] {p.name} 打出【无懈可击】。")
                else:
                    if not self._ask_for_specific_card(p, CardName.NULLIFY, prompt):
                        continue
                effective = not effective
                played = True
                break
            if not played:
                return effective

    def _is_trick_countered(self, actor: Player, target: Player, card: Card) -> bool:
        effective = self._resolve_nullify_chain(
            starter=actor,
            trick_user=actor,
            trick_name=card.name,
            target=target,
            effective=True,
        )
        return not effective

    def _is_delayed_trick_countered(self, target: Player, card: Card) -> bool:
        effective = self._resolve_nullify_chain(
            starter=target,
            trick_user=None,
            trick_name=card.name,
            target=target,
            effective=True,
        )
        return not effective

    def _ask_for_specific_card(self, p: Player, card_name: str, prompt: str) -> bool:
        if not p.has_card(card_name):
            return False
        if p.is_ai:
            if card_name == CardName.NULLIFY:
                enemy = self.other_player(p)
                if enemy.hp > p.hp:
                    return False
            card = p.remove_one(card_name)
            if card is None:
                return False
            self.discard(card)
            return True
        ans = self.input(prompt).strip().lower()
        if ans != "y":
            return False
        card = p.remove_one(card_name)
        if card is None:
            return False
        self.discard(card)
        return True

    def _ask_for_shan(self, p: Player, *, prompt: str | None = None, attacker: Player | None = None) -> bool:
        if p.armor is not None and p.armor.name == CardName.BAGUA_SHIELD:
            if attacker is None or not attacker.ignore_armor_on_sha:
                judge = self._run_judgment(p, reason_card=p.armor, reason_text="八卦阵")
                if judge is not None:
                    self.output(f"[响应] {p.name} 的【八卦阵】判定：{self._format_card_short(judge)}")
                    if judge.is_red:
                        self.output(f"[响应] {p.name} 通过【八卦阵】视为打出【闪】。")
                        return True
        if not p.has_card(CardName.SHAN):
            return False
        if p.is_ai:
            shan_count = sum(1 for c in p.hand if c.name == CardName.SHAN)
            should_keep = p.hp > self.ai_config.shan_response_hp_threshold and shan_count <= self.ai_config.shan_min_reserve
            if should_keep:
                return False
            card = p.remove_one(CardName.SHAN)
            if card is None:
                return False
            self.discard(card)
            return True
        ask = prompt or f"{p.name} 是否打出【闪】？(y/n): "
        ans = self.input(ask).strip().lower()
        if ans != "y":
            return False
        card = p.remove_one(CardName.SHAN)
        if card is None:
            return False
        self.discard(card)
        return True

    def _ask_for_sha(self, p: Player, *, duel: bool = False, prompt: str | None = None) -> bool:
        def _remove_sha_or_wusheng(owner: Player) -> Card | None:
            card = owner.remove_one(CardName.SHA)
            if card is not None:
                return card
            if owner.general == "关羽":
                for i, c in enumerate(owner.hand):
                    if c.is_red:
                        return owner.hand.pop(i)
            return None

        if not p.has_card(CardName.SHA) and not (p.general == "关羽" and any(c.is_red for c in p.hand)):
            return False
        if p.is_ai:
            sha_count = sum(1 for c in p.hand if c.name == CardName.SHA)
            if not duel:
                card = _remove_sha_or_wusheng(p)
                if card is None:
                    return False
                self.discard(card)
                return True
            should_keep = p.hp > self.ai_config.duel_sha_response_hp_threshold and sha_count <= self.ai_config.duel_sha_min_reserve
            if should_keep:
                return False
            card = _remove_sha_or_wusheng(p)
            if card is None:
                return False
            self.discard(card)
            return True
        ask = prompt or f"{p.name} 是否打出【杀】响应？(y/n): "
        ans = self.input(ask).strip().lower()
        if ans != "y":
            return False
        card = _remove_sha_or_wusheng(p)
        if card is None:
            return False
        self.discard(card)
        return True

    def _check_death(self, victim: Player, attacker: Player) -> None:
        if not victim.alive:
            return
        if victim.hp <= 0:
            self._enter_dying(victim, attacker)

    def _enter_dying(self, victim: Player, attacker: Player) -> bool:
        if not victim.alive:
            return False
        self.output(f"[濒死] {victim.name} 进入濒死（HP={victim.hp}）。")
        order = self._iter_ccw_alive(self._human_player())
        while victim.hp <= 0 and victim.alive:
            rescued = False
            for rescuer in order:
                if victim.hp > 0 or not victim.alive:
                    break
                can_tao = rescuer.has_card(CardName.TAO)
                can_jijiu = rescuer.general == "华佗" and self.current_player() is not rescuer and any(c.is_red for c in rescuer.hand)
                if not can_tao and not can_jijiu:
                    continue
                if rescuer.is_ai:
                    if not (rescuer is victim or rescuer.is_ally_of(victim)):
                        continue
                    tao_card = rescuer.remove_one(CardName.TAO)
                    used_jijiu = False
                    if tao_card is None and can_jijiu:
                        for i, c in enumerate(rescuer.hand):
                            if c.is_red:
                                tao_card = rescuer.hand.pop(i)
                                used_jijiu = True
                                break
                    if tao_card is None:
                        continue
                    self.discard(tao_card)
                    victim.heal(1)
                    rescued = True
                    if used_jijiu:
                        self.output(f"[结算] {rescuer.name} 发动【急救】，救援 {victim.name}，体力回到 {victim.hp}。")
                    else:
                        self.output(f"[结算] {rescuer.name} 使用【桃】救援 {victim.name}，体力回到 {victim.hp}。")
                    continue
                ans = self.input(
                    f"濒死求桃：{victim.name} 濒死（HP={victim.hp}），{rescuer.name} 是否使用【桃】/【急救】救援？(y/n): "
                ).strip().lower()
                if ans != "y":
                    continue
                tao_card = rescuer.remove_one(CardName.TAO)
                used_jijiu = False
                if tao_card is None and can_jijiu:
                    listing = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(rescuer.hand) if c.is_red)
                    while True:
                        ans_idx = self.input(f"技能选牌-急救：请选择一张红色手牌当【桃】使用 {listing}: ").strip()
                        if not ans_idx.isdigit():
                            continue
                        idx = int(ans_idx)
                        if 0 <= idx < len(rescuer.hand) and rescuer.hand[idx].is_red:
                            tao_card = rescuer.hand.pop(idx)
                            used_jijiu = True
                            break
                if tao_card is None:
                    continue
                self.discard(tao_card)
                victim.heal(1)
                rescued = True
                if used_jijiu:
                    self.output(f"[结算] {rescuer.name} 发动【急救】，救援 {victim.name}，体力回到 {victim.hp}。")
                else:
                    self.output(f"[结算] {rescuer.name} 使用【桃】救援 {victim.name}，体力回到 {victim.hp}。")
            if not rescued:
                break
        if victim.hp <= 0:
            victim.alive = False
            self.winner = attacker
            self.output(f"[结算] {victim.name} 阵亡，{attacker.name} 获胜！")
            return False
        self.output(f"[濒死] {victim.name} 脱离濒死（HP={victim.hp}）。")
        return True

    def register_passive_skill(self, event: str, owner: Player, skill_name: str, handler: PassiveSkillHandler) -> None:
        self.passive_skill_registry.setdefault(event, []).append((owner, skill_name, handler))

    def register_active_skill(self, owner: Player, skill_name: str, handler: ActiveSkillHandler) -> None:
        self.active_skill_registry.setdefault(id(owner), []).append((skill_name, handler))

    def _trigger_event(self, event: str, **kwargs: object) -> None:
        for owner, _, handler in self.passive_skill_registry.get(event, []):
            if owner.alive:
                handler(self, owner, **kwargs)

    def _use_active_skill(self, actor: Player, target: Player, skill_index: int) -> ActionResult:
        skills = self.active_skill_registry.get(id(actor), [])
        if skill_index < 0 or skill_index >= len(skills):
            return ActionResult(False, "技能索引越界。")
        _, handler = skills[skill_index]
        return handler(self, actor, target)

    def _ai_use_active_skill(self, actor: Player, target: Player) -> bool:
        for _, handler in self.active_skill_registry.get(id(actor), []):
            res = handler(self, actor, target)
            if res.ok:
                return True
        return False

    def _choose_generals(self) -> None:
        available = list(self.general_pool)
        for p in self.players:
            if p.general is not None:
                general = get_general_by_name(p.general)
                self._apply_general(p, general)
                available = [g for g in available if g.name != general.name]
                continue
            general = self._choose_general_for_player(p, available)
            self._apply_general(p, general)
            available = [g for g in available if g.name != general.name]

    def _choose_general_for_player(self, p: Player, available: list[GeneralDefinition]) -> GeneralDefinition:
        if not available:
            raise RuntimeError("没有可选武将。")
        if p.is_ai:
            return self.rng.choice(available)
        while True:
            self.output("可选武将：")
            for i, g in enumerate(available):
                skills = "，".join(s.name for s in g.skills)
                self.output(f"[{i}] {g.name}（体力上限{g.max_hp}，技能：{skills}）")
            ans = self.input(f"{p.name} 请选择武将编号: ").strip()
            if ans.isdigit():
                idx = int(ans)
                if 0 <= idx < len(available):
                    return available[idx]
            self.output("输入无效，请重试。")

    def _apply_general(self, p: Player, general: GeneralDefinition) -> None:
        p.general = general.name
        p.max_hp = general.max_hp
        p.hp = general.max_hp
        p.extra_attack_limit = 0

    def _register_generals_skills(self) -> None:
        for p in self.players:
            if p.general is None:
                continue
            general = get_general_by_name(p.general)
            for skill in general.skills:
                if skill.name == "咆哮":
                    p.extra_attack_limit = 99
                elif skill.kind == "active" and skill.name in ACTIVE_SKILL_HANDLERS:
                    handler = ACTIVE_SKILL_HANDLERS[skill.name]
                    self.register_active_skill(p, skill.name, handler)
                elif skill.kind == "passive" and skill.name in PASSIVE_SKILL_HANDLERS:
                    event, handler = PASSIVE_SKILL_HANDLERS[skill.name]
                    self.register_passive_skill(event, p, skill.name, handler)
