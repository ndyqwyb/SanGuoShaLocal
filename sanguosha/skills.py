from __future__ import annotations

from typing import TYPE_CHECKING

from .cards import CardName

if TYPE_CHECKING:
    from .game import ActionResult, Game
    from .player import Player


def jizhi_after_use_trick(game: "Game", owner: "Player", *, actor: "Player", **_: object) -> None:
    if owner is not actor:
        return
    card = _.get("card")
    delayed = {CardName.INDULGENCE, CardName.SUPPLY_SHORTAGE, CardName.LIGHTNING}
    if card is not None and getattr(card, "name", None) in delayed:
        return
    game.draw_cards(owner, 1)
    game.output(f"[结算] {owner.name} 触发【集智】，摸1张牌。")


def wusheng_active(game: "Game", actor: "Player", target: "Player") -> "ActionResult":
    if not game._can_use_sha(actor):
        return game.make_action_result(False, "【武圣】发动失败：本回合【杀】次数已达上限。")
    red_indexes = [i for i, c in enumerate(actor.hand) if c.is_red]
    if not red_indexes:
        return game.make_action_result(False, "【武圣】发动失败：没有可用红色手牌。")
    idx = red_indexes[0]
    if not actor.is_ai:
        listing = " ".join(f"[{i}] {actor.hand[i].name} {actor.hand[i].suit}{actor.hand[i].rank}" for i in red_indexes)
        ans = game.input(f"技能选牌-武圣：请选择要当【杀】使用的红牌编号 {listing}: ").strip()
        if not ans.isdigit() or int(ans) not in red_indexes:
            return game.make_action_result(False, "【武圣】发动失败：选择无效。")
        idx = int(ans)
    card = actor.hand.pop(idx)
    if card is None:
        return game.make_action_result(False, "【武圣】发动失败：未选中红牌。")
    game.discard(card)
    actor.sha_used_this_turn += 1
    game.output(f"[声明] {actor.name} 发动【武圣】，将【{card.name}】当【杀】使用。")
    game.resolve_sha(actor, target)
    return game.make_action_result(True, "")


def qingnang_active(game: "Game", actor: "Player", target: "Player") -> "ActionResult":
    if actor.qingnang_used_this_turn:
        return game.make_action_result(False, "【青囊】本回合已使用。")
    if not actor.hand:
        return game.make_action_result(False, "【青囊】发动失败：没有可弃置的手牌。")
    choices = [p for p in game.players if p.alive and p.hp < p.max_hp]
    if not choices:
        return game.make_action_result(False, "【青囊】发动失败：没有受伤角色。")

    discard_idx = 0
    chosen = choices[0]
    if actor.is_ai:
        if actor in choices and actor.hp <= 2:
            chosen = actor
        else:
            chosen = min(choices, key=lambda p: (p.hp, 0 if p is actor else 1))
    else:
        hand_list = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(actor.hand))
        ans_card = game.input(f"技能选牌-青囊：请选择要弃置的手牌编号 {hand_list}: ").strip()
        if not ans_card.isdigit() or not (0 <= int(ans_card) < len(actor.hand)):
            return game.make_action_result(False, "【青囊】发动失败：弃牌选择无效。")
        discard_idx = int(ans_card)
        if len(choices) > 1:
            target_options = " ".join(f"[{i}]{p.name}" for i, p in enumerate(choices))
            ans_target = game.input(f"技能目标-青囊：请选择回复目标 {target_options}: ").strip()
            if not ans_target.isdigit() or not (0 <= int(ans_target) < len(choices)):
                return game.make_action_result(False, "【青囊】发动失败：目标选择无效。")
            chosen = choices[int(ans_target)]
        else:
            chosen = choices[0]

    card = actor.hand.pop(discard_idx)
    game.discard(card)
    chosen.heal(1)
    actor.qingnang_used_this_turn = True
    game.output(f"[结算] {actor.name} 发动【青囊】，弃置【{card.name}】，令 {chosen.name} 回复1点体力。")
    return game.make_action_result(True, "")


def kurou_active(game: "Game", actor: "Player", __: "Player") -> "ActionResult":
    if actor.hp <= 0:
        return game.make_action_result(False, "【苦肉】发动失败：体力不足。")
    if actor.is_ai and actor.hp <= 2:
        return game.make_action_result(False, "【苦肉】发动失败：AI保守策略。")
    game.output(f"[声明] {actor.name} 发动【苦肉】，失去1点体力。")
    game.lose_hp(actor, 1)
    game.draw_cards(actor, 2)
    game.output(f"[结算] {actor.name} 摸2张牌。")
    return game.make_action_result(True, "")


def fanjian_active(game: "Game", actor: "Player", __: "Player") -> "ActionResult":
    if getattr(actor, "fanjian_used_this_turn", False):
        return game.make_action_result(False, "【反间】本回合已使用。")
    if not actor.hand:
        return game.make_action_result(False, "【反间】发动失败：没有可用手牌。")
    targets = [p for p in game.players if p.alive and p is not actor]
    if not targets:
        return game.make_action_result(False, "【反间】发动失败：没有可选目标。")
    target = targets[0]
    suit_choice = "spade"
    card_idx = 0
    if actor.is_ai:
        target = next((p for p in targets if not p.is_ai), targets[0])
        card_idx = 0
    else:
        target_options = " ".join(f"[{i}]{p.name}" for i, p in enumerate(targets))
        ans_target = game.input(f"技能目标-反间：请选择目标 {target_options}: ").strip()
        if not ans_target.isdigit() or not (0 <= int(ans_target) < len(targets)):
            return game.make_action_result(False, "【反间】发动失败：目标选择无效。")
        target = targets[int(ans_target)]
        listing = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(actor.hand))
        ans_card = game.input(f"技能选牌-反间：请选择要交给对方的手牌编号 {listing}: ").strip()
        if not ans_card.isdigit() or not (0 <= int(ans_card) < len(actor.hand)):
            return game.make_action_result(False, "【反间】发动失败：选牌无效。")
        card_idx = int(ans_card)
    suits = [("spade", "♠"), ("heart", "♥"), ("club", "♣"), ("diamond", "♦")]
    if target.is_ai:
        suit_choice = suits[0][0]
    else:
        suit_options = " ".join(f"[{i}]{label}" for i, (_, label) in enumerate(suits))
        ans_suit = game.input(f"技能目标-反间花色：请选择花色 {suit_options}: ").strip()
        if not ans_suit.isdigit() or not (0 <= int(ans_suit) < len(suits)):
            return game.make_action_result(False, "【反间】发动失败：花色选择无效。")
        suit_choice = suits[int(ans_suit)][0]
    card = actor.hand.pop(card_idx)
    target.hand.append(card)
    actor.fanjian_used_this_turn = True
    game.output(f"[声明] {actor.name} 对 {target.name} 发动【反间】，交给其【{card.name}】。")
    if card.suit != suit_choice:
        game.output(f"[结算] {target.name} 所选花色不符，受到1点伤害。")
        game.deal_damage(actor, target, 1, card=card, reason="反间")
    else:
        game.output(f"[结算] {target.name} 所选花色相符，不受伤害。")
    return game.make_action_result(True, "")


def yingzi_draw_phase(game: "Game", owner: "Player", *, actor: "Player", **_: object) -> int:
    if owner is not actor:
        return 0
    return 1


def feedback_after_damage(game: "Game", owner: "Player", *, victim: "Player", source: "Player | None", **_: object) -> None:
    if owner is not victim:
        return
    if source is None or not source.alive:
        return
    if not (source.hand or source.weapon or source.armor or source.plus_horse or source.minus_horse or source.judgment_area):
        return
    if not owner.is_ai:
        ans = game.input(f"{owner.name} 是否发动【反馈】？(y/n): ").strip().lower()
        if ans != "y":
            return
    zone = game._choose_target_zone(owner, source)
    if zone is None:
        return
    removed = game._pop_target_asset(source, zone)
    if removed is None:
        return
    _, card = removed
    owner.hand.append(card)
    game.output(f"[结算] {owner.name} 发动【反馈】，获得了 {source.name} 的【{card.name}】。")


def guicai_before_judge(
    game: "Game",
    owner: "Player",
    *,
    judge_owner: "Player",
    judge_card: object,
    **_: object,
) -> object | None:
    if not owner.alive or not owner.hand:
        return None
    if owner.is_ai:
        replace = owner.hand.pop(0)
        game.output(f"[响应] {owner.name} 发动【鬼才】，替换判定牌。")
        return replace
    prompt_card = ""
    if hasattr(judge_card, "name") and hasattr(judge_card, "suit") and hasattr(judge_card, "rank"):
        suit_map = {"heart": "♥", "diamond": "♦", "club": "♣", "spade": "♠"}
        symbol = suit_map.get(getattr(judge_card, "suit"), getattr(judge_card, "suit"))
        prompt_card = f"（当前判定：{getattr(judge_card, 'name')} {symbol}{getattr(judge_card, 'rank')}）"
    ans = game.input(f"{owner.name} 是否发动【鬼才】替换判定牌{prompt_card}？(y/n): ").strip().lower()
    if ans != "y":
        return None
    listing = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(owner.hand))
    ans_card = game.input(f"技能选牌-鬼才：请选择要替换的手牌编号 {listing}: ").strip()
    if not ans_card.isdigit() or not (0 <= int(ans_card) < len(owner.hand)):
        return None
    replace = owner.hand.pop(int(ans_card))
    game.output(f"[响应] {owner.name} 发动【鬼才】，替换判定牌。")
    return replace


def tiandu_after_judge(
    game: "Game",
    owner: "Player",
    *,
    judge_owner: "Player",
    judge_card: object,
    **_: object,
) -> bool:
    if owner is not judge_owner or not owner.alive:
        return False
    if owner.is_ai:
        return True
    ans = game.input(f"{owner.name} 是否发动【天妒】获得判定牌？(y/n): ").strip().lower()
    return ans == "y"


def yiji_after_damage(
    game: "Game",
    owner: "Player",
    *,
    victim: "Player",
    amount: int = 1,
    **_: object,
) -> None:
    if owner is not victim or not owner.alive:
        return
    for _ in range(max(1, amount)):
        if not owner.is_ai:
            ans = game.input(f"{owner.name} 是否发动【遗计】？(y/n): ").strip().lower()
            if ans != "y":
                continue
        before = len(owner.hand)
        game.draw_cards(owner, 2)
        drawn = owner.hand[before:]
        suit_map = {"heart": "♥", "diamond": "♦", "club": "♣", "spade": "♠"}
        shown = " ".join(
            f"[{i}] {c.name} {suit_map.get(c.suit, c.suit)}{c.rank}" for i, c in enumerate(drawn)
        )
        game.output(f"[结算] {owner.name} 触发【遗计】，摸2张牌：{shown}")
        targets = [p for p in game.players if p.alive and p is not owner]
        if not targets or owner.is_ai:
            continue
        while True:
            ans_give = game.input(f"{owner.name} 是否将一张牌交给其他角色？(y/n): ").strip().lower()
            if ans_give != "y":
                break
            listing = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(owner.hand))
            ans_card = game.input(f"技能选牌-遗计：请选择要交出的手牌编号 {listing}: ").strip()
            if not ans_card.isdigit() or not (0 <= int(ans_card) < len(owner.hand)):
                break
            card = owner.hand.pop(int(ans_card))
            target_options = " ".join(f"[{i}]{p.name}" for i, p in enumerate(targets))
            ans_target = game.input(f"技能目标-遗计：请选择交给目标 {target_options}: ").strip()
            if not ans_target.isdigit() or not (0 <= int(ans_target) < len(targets)):
                owner.hand.append(card)
                break
            tgt = targets[int(ans_target)]
            tgt.hand.append(card)
            game.output(f"[结算] {owner.name} 将【{card.name}】交给了 {tgt.name}。")


def ganglie_after_damage(
    game: "Game",
    owner: "Player",
    *,
    victim: "Player",
    source: "Player | None",
    amount: int = 1,
    **_: object,
) -> None:
    if owner is not victim or not owner.alive:
        return
    if source is None or not source.alive:
        return
    for _ in range(max(1, amount)):
        if not owner.is_ai:
            ans = game.input(f"{owner.name} 是否发动【刚烈】？(y/n): ").strip().lower()
            if ans != "y":
                continue
        judge = game.run_judgment(owner, reason_text="刚烈")
        if judge is None:
            continue
        suit = getattr(judge, "suit", "")
        if suit == "heart":
            game.output(f"[结算] {owner.name}【刚烈】判定为红桃，无事发生。")
            continue
        if len(source.hand) < 2:
            game.output(f"[结算] {source.name} 手牌不足2张，受到1点伤害。")
            game.deal_damage(owner, source, 1, reason="刚烈")
            continue
        if source.is_ai:
            idxs = game._choose_ai_discard_indexes(source, 2)
            for idx in sorted(idxs, reverse=True):
                game.discard(source.hand.pop(idx))
            game.output(f"[结算] {source.name} 弃置2张牌响应【刚烈】。")
            continue
        ans2 = game.input(f"{source.name} 是否弃置2张牌响应【刚烈】？(y/n): ").strip().lower()
        if ans2 == "y":
            idxs = game._ask_discard_indexes(source, 2)
            for idx in sorted(idxs, reverse=True):
                game.discard(source.hand.pop(idx))
            game.output(f"[结算] {source.name} 弃置2张牌响应【刚烈】。")
            continue
        game.output(f"[结算] {source.name} 选择不弃牌，受到1点伤害。")
        game.deal_damage(owner, source, 1, reason="刚烈")


ACTIVE_SKILL_HANDLERS: dict[str, object] = {
    "武圣": wusheng_active,
    "青囊": qingnang_active,
    "反间": fanjian_active,
    "苦肉": kurou_active,
}

PASSIVE_SKILL_HANDLERS: dict[str, tuple[str, object]] = {
    "集智": ("after_use_trick", jizhi_after_use_trick),
    "英姿": ("draw_phase", yingzi_draw_phase),
    "反馈": ("after_damage", feedback_after_damage),
    "鬼才": ("before_judge", guicai_before_judge),
    "天妒": ("after_judge", tiandu_after_judge),
    "遗计": ("after_damage", yiji_after_damage),
    "刚烈": ("after_damage", ganglie_after_damage),
}
