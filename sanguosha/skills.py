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
    choices = [p for p in (actor, target) if p.alive and p.hp < p.max_hp]
    if not choices:
        return game.make_action_result(False, "【青囊】发动失败：没有受伤角色。")

    discard_idx = 0
    chosen = choices[0]
    if actor.is_ai:
        if actor.hp <= 2:
            chosen = actor
        elif target.hp < target.max_hp:
            chosen = target
    else:
        hand_list = " ".join(f"[{i}] {c.name} {c.suit}{c.rank}" for i, c in enumerate(actor.hand))
        ans_card = game.input(f"技能选牌-青囊：请选择要弃置的手牌编号 {hand_list}: ").strip()
        if not ans_card.isdigit() or not (0 <= int(ans_card) < len(actor.hand)):
            return game.make_action_result(False, "【青囊】发动失败：弃牌选择无效。")
        discard_idx = int(ans_card)
        if len(choices) > 1:
            ans_target = game.input(f"技能目标-青囊：选择回复目标 [0]{actor.name} [1]{target.name}: ").strip()
            if ans_target == "1":
                chosen = target
            else:
                chosen = actor
        else:
            chosen = choices[0]

    card = actor.hand.pop(discard_idx)
    game.discard(card)
    chosen.heal(1)
    actor.qingnang_used_this_turn = True
    game.output(f"[结算] {actor.name} 发动【青囊】，弃置【{card.name}】，令 {chosen.name} 回复1点体力。")
    return game.make_action_result(True, "")
