import pytest

from sanguosha.cards import Card, CardName, build_deck, load_card_definitions
from sanguosha.generals import GENERAL_POOL
from sanguosha.game import AIStrategyConfig, Game
from sanguosha.player import Player


def make_game() -> Game:
    p1 = Player(name="A", is_ai=True)
    p2 = Player(name="B", is_ai=True)
    return Game(p1, p2, seed=1, output_func=lambda _: None)


def test_sha_can_be_dodged_by_shan() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA)]
    b.hand = [Card(CardName.SHAN)]
    game.play_card(a, b, 0)
    assert b.hp == 4


def test_sha_deals_damage_without_shan() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA)]
    b.hand = []
    game.play_card(a, b, 0)
    assert b.hp == 3


def test_tao_heals_self() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hp = 2
    a.hand = [Card(CardName.TAO)]
    res = game.play_card(a, b, 0)
    assert res.ok is True
    assert a.hp == 3


def test_weapon_allows_two_sha_in_turn() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.ZHUGE_CROSSBOW), Card(CardName.SHA), Card(CardName.SHA), Card(CardName.SHA)]
    b.hand = []
    game.play_card(a, b, 0)
    game.play_card(a, b, 0)
    game.play_card(a, b, 0)
    res = game.play_card(a, b, 0)
    assert res.ok is True
    assert b.hp == 1


def test_duel_resolution() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.DUEL), Card(CardName.SHA)]
    b.hand = [Card(CardName.SHA)]
    game.play_card(a, b, 0)
    # 决斗流程：B先出杀，A再出杀，B无杀受伤
    assert b.hp == 3


def test_duel_damage_chain_enemy_should_lose_hp_when_cannot_follow_sha() -> None:
    answers = iter(["y", "n"])
    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=False),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA)]
    b.hand = [Card(CardName.DUEL)]
    res = game.play_card(b, a, 0)
    assert res.ok is True
    assert b.hp == 3
    assert a.hp == 4


def test_duel_response_sha_does_not_count_into_sha_limit() -> None:
    answers = iter(["y", "n"])
    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=False),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA)]
    b.hand = [Card(CardName.DUEL)]
    game.play_card(b, a, 0)
    assert a.sha_used_this_turn == 0


def test_default_sha_limit_is_one_per_turn() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA), Card(CardName.SHA)]
    b.hand = []
    first = game.play_card(a, b, 0)
    second = game.play_card(a, b, 0)
    assert first.ok is True
    assert second.ok is False
    assert "已达上限" in second.message


def test_dismantle_discards_target_card() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.DISMANTLE)]
    b.hand = [Card(CardName.SHA)]
    game.play_card(a, b, 0)
    assert b.hand == []


def test_win_when_target_dies_without_tao() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    b.hp = 1
    a.hand = [Card(CardName.SHA)]
    b.hand = []
    game.play_card(a, b, 0)
    assert game.winner is a


def test_has_at_least_four_generals() -> None:
    assert len(GENERAL_POOL) >= 4


def test_setup_selects_generals_for_human_and_ai() -> None:
    answers = iter(["0"])
    game = Game(
        Player(name="玩家", is_ai=False),
        Player(name="电脑", is_ai=True),
        seed=2,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    game.setup()
    assert game.player.general is not None
    assert game.enemy.general is not None
    assert game.player.general != game.enemy.general


def test_qingnang_active_discards_and_heals() -> None:
    game = Game(
        Player(name="A", is_ai=False, general="华佗"),
        Player(name="B", is_ai=True, general="关羽"),
        seed=3,
        input_func=lambda _: "0",
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    a.hp = 2
    a.hand = [Card(CardName.SHA)]
    res = game._use_active_skill(a, b, 0)
    assert res.ok is True
    assert a.hp == 3
    assert len(a.hand) == 0


def test_qingnang_target_prompt_lists_wounded_players_with_indexes() -> None:
    prompts: list[str] = []
    answers = iter(["0", "1"])

    def _input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    game = Game(
        Player(name="A", is_ai=False, general="华佗"),
        Player(name="B", is_ai=False, general="关羽"),
        seed=7,
        input_func=_input,
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    a.hp = 2
    b.hp = 2
    a.hand = [Card(CardName.SHA)]
    res = game._use_active_skill(a, b, 0)
    assert res.ok is True
    assert b.hp == 3
    target_prompt = next(p for p in prompts if p.startswith("技能目标-青囊"))
    assert "[0]A" in target_prompt
    assert "[1]B" in target_prompt


def test_jizhi_draws_after_trick() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.general = "黄月英"
    b.general = "关羽"
    game.setup()
    a.hand = [Card(CardName.DISMANTLE)]
    b.hand = [Card(CardName.SHA)]
    game.draw_pile = [Card(CardName.SHA)]
    game.play_card(a, b, 0)
    assert len(a.hand) == 1


def test_wusheng_active_skill_as_sha() -> None:
    answers = iter(["0", "s0", "0", "p"])
    game = Game(
        Player(name="玩家", is_ai=False),
        Player(name="电脑", is_ai=True, general="华佗"),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    game.setup()
    game.turn_index = game.players.index(game.player)
    game.player.hand = [Card(CardName.SHAN, suit="heart", rank=7)]
    game.enemy.hand = []
    game.draw_pile = []
    game.run_turn(game.player)
    assert game.enemy.hp == game.enemy.max_hp - 1


def test_paoxiao_increases_sha_limit() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.general = "张飞"
    b.general = "关羽"
    game.setup()
    a.hand = [Card(CardName.SHA), Card(CardName.SHA)]
    b.hand = []
    first = game.play_card(a, b, 0)
    second = game.play_card(a, b, 0)
    assert first.ok is True
    assert second.ok is True


def test_ai_evaluation_reports_kill_window() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA)]
    a.sha_used_this_turn = 0
    b.hp = 1
    eval_state = game._evaluate_ai_state(a, b)
    assert eval_state.kill_chance == 1.0
    assert eval_state.threat_value > 0


def test_ai_tao_threshold_parameter_affects_play_phase() -> None:
    p1 = Player(name="A", is_ai=True)
    p2 = Player(name="B", is_ai=True)
    game = Game(
        p1,
        p2,
        seed=1,
        ai_config=AIStrategyConfig(tao_play_hp_threshold=1),
        output_func=lambda _: None,
    )
    p1.hp = 3
    p1.hand = [Card(CardName.TAO), Card(CardName.SHA)]
    p2.hand = []
    game._ai_play_phase(p1, p2)
    assert p1.hp == 3
    assert p2.hp == 3


def test_ai_shan_response_parameter_can_reserve_shan() -> None:
    p1 = Player(name="A", is_ai=True)
    p2 = Player(name="B", is_ai=True)
    game = Game(
        p1,
        p2,
        seed=1,
        ai_config=AIStrategyConfig(shan_response_hp_threshold=1, shan_min_reserve=1),
        output_func=lambda _: None,
    )
    p1.hand = [Card(CardName.SHA)]
    p2.hp = 4
    p2.hand = [Card(CardName.SHAN)]
    game.play_card(p1, p2, 0)
    assert p2.hp == 3
    assert len(p2.hand) == 1


def test_load_card_definitions_rejects_invalid_category() -> None:
    with pytest.raises(ValueError, match="类别非法"):
        load_card_definitions(
            [
                {
                    "name": "测试牌",
                    "category": "invalid",  # type: ignore[typeddict-item]
                    "effect_type": "direct_damage_1",
                    "play_validator": "default",
                    "deck_count": 1,
                }
            ]
        )


def test_custom_config_card_works_with_registry_and_unified_play_entry() -> None:
    custom_card_name = "火攻"
    custom_configs = (
        {
            "name": custom_card_name,
            "category": "trick",
            "effect_type": "direct_damage_1",
            "play_validator": "default",
            "deck_count": 0,
        },
    )
    game = Game(
        Player(name="A", is_ai=True),
        Player(name="B", is_ai=True),
        seed=1,
        card_configs=custom_configs,
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(custom_card_name)]
    b.hp = 2
    b.hand = []
    res = game.play_card(a, b, 0)
    assert res.ok is True
    assert b.hp == 1
    assert len(game.discard_pile) == 1
    assert game.discard_pile[0].name == custom_card_name


def test_discard_phase_uses_current_hp_limit_and_logs() -> None:
    answers = iter(["p", "0 1"])
    outputs: list[str] = []
    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=True),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=outputs.append,
    )
    a, b = game.player, game.enemy
    a.hp = 2
    a.hand = [Card(CardName.SHA), Card(CardName.SHAN), Card(CardName.TAO), Card(CardName.DUEL)]
    b.hand = []
    game.draw_pile = []
    game.run_turn(a)
    assert len(a.hand) == 2
    assert any("进入弃牌阶段" in msg and "当前体力=2" in msg for msg in outputs)
    assert any("弃牌阶段结束" in msg for msg in outputs)


def test_dismantle_can_choose_zone_hand_or_weapon() -> None:
    answers = iter(["w"])
    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=True),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.DISMANTLE)]
    b.hand = [Card(CardName.SHA)]
    b.weapon = Card(CardName.ZHUGE_CROSSBOW)
    game.play_card(a, b, 0)
    assert b.weapon is None


def test_harvest_actor_selects_first_then_other_gets_rest() -> None:
    answers = iter(["0"])
    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=True),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.HARVEST)]
    game.draw_pile = [Card(CardName.TAO, suit="heart", rank=9), Card(CardName.SHA, suit="spade", rank=7)]
    game.play_card(a, b, 0)
    assert len(a.hand) == 1
    assert len(b.hand) == 1


def test_qinggang_ignores_bagua() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.weapon = Card(CardName.QINGGANG_SWORD)
    a.hand = [Card(CardName.SHA)]
    b.armor = Card(CardName.BAGUA_SHIELD)
    b.hand = []
    game.draw_pile = [Card(CardName.SHA, suit="heart", rank=9)]
    game.play_card(a, b, 0)
    assert b.hp == 3


def test_plus_and_minus_horse_affects_distance() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA)]
    b.plus_horse = Card(CardName.ZIXING)
    res = game.play_card(a, b, 0)
    assert res.ok is False
    a.minus_horse = Card(CardName.CHITU)
    res2 = game.play_card(a, b, 0)
    assert res2.ok is True


def test_snatch_ex_nihilo_and_borrowed_sword() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    b.weapon = Card(CardName.ZHUGE_CROSSBOW)
    a.hand = [Card(CardName.BORROWED_SWORD), Card(CardName.SNATCH), Card(CardName.EX_NIHILO)]
    b.hand = []
    game.play_card(a, b, 0)
    assert any(c.name == CardName.ZHUGE_CROSSBOW for c in a.hand)
    game.play_card(a, b, 0)
    assert len(a.hand) >= 2
    before = len(a.hand)
    game.play_card(a, b, 0)
    assert len(a.hand) >= before + 1


def test_global_tricks_and_wuxie() -> None:
    answers = iter(["y"])
    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=False),
        seed=1,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hp = 2
    b.hp = 2
    a.hand = [Card(CardName.PEACH_GARDEN), Card(CardName.BARBARIAN_INVASION)]
    b.hand = [Card(CardName.NULLIFY)]
    game.play_card(a, b, 0)
    assert a.hp == 2 and b.hp == 2
    game.play_card(a, b, 0)
    assert b.hp == 1


def test_delayed_tricks_indulgence_supply_and_lightning() -> None:
    game = make_game()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.INDULGENCE), Card(CardName.SUPPLY_SHORTAGE)]
    game.play_card(a, b, 0)
    game.play_card(a, b, 0)
    assert len(b.judgment_area) == 2
    b.judgment_area.append(Card(CardName.LIGHTNING))
    game.draw_pile = [
        Card(CardName.SHA, suit="spade", rank=5),
        Card(CardName.SHA, suit="diamond", rank=9),
        Card(CardName.SHA, suit="diamond", rank=9),
    ]
    b.hp = 4
    game.run_turn(b)
    assert b.hp <= 1


def test_delayed_tricks_do_not_ask_nullify_on_play_but_ask_in_judgment() -> None:
    prompts: list[str] = []
    answers = iter(["y", "n", "y", "n", "y", "n"])

    def _input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    game = Game(
        Player(name="A", is_ai=False),
        Player(name="B", is_ai=False),
        seed=1,
        input_func=_input,
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.INDULGENCE), Card(CardName.SUPPLY_SHORTAGE), Card(CardName.LIGHTNING)]
    b.hand = [Card(CardName.NULLIFY), Card(CardName.NULLIFY), Card(CardName.NULLIFY)]

    game.play_card(a, b, 0)  # 乐不思蜀
    game.play_card(a, b, 0)  # 兵粮寸断
    game.play_card(a, b, 0)  # 闪电（自挂）

    assert not any("无懈可击" in p for p in prompts)

    game._resolve_judgment_area(b)
    assert any("无懈可击" in p and "乐不思蜀" in p for p in prompts)
    assert any("无懈可击" in p and "兵粮寸断" in p for p in prompts)
    assert b.skip_play_phase is False
    assert b.skip_draw_phase is False

    game._resolve_judgment_area(a)
    assert any("无懈可击" in p and "闪电" in p for p in prompts)


def test_judgment_log_contains_card_name() -> None:
    messages: list[str] = []

    def _out(msg: str) -> None:
        messages.append(msg)

    game = Game(
        Player(name="A", is_ai=True, general="关羽"),
        Player(name="B", is_ai=True, general="关羽"),
        seed=11,
        output_func=_out,
    )
    game.setup()
    b = game.enemy
    b.judgment_area.append(Card(CardName.INDULGENCE))
    game.draw_pile = [Card(CardName.SHA, suit="spade", rank=7)]
    game._resolve_judgment_area(b)
    assert any("判定牌" in m and "杀" in m for m in messages)


def test_nullify_chain_allows_counter_nullify() -> None:
    prompts: list[str] = []
    answers = iter(["n", "y", "y"])

    def _input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    game = Game(
        Player(name="A", is_ai=False, general="关羽"),
        Player(name="B", is_ai=False, general="关羽"),
        seed=12,
        input_func=_input,
        output_func=lambda _: None,
    )
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.EX_NIHILO), Card(CardName.NULLIFY)]
    b.hand = [Card(CardName.NULLIFY)]
    game.draw_pile = [Card(CardName.SHA), Card(CardName.SHA)]
    game.play_card(a, b, 0)
    assert len(a.hand) == 2
    assert len(game.discard_pile) == 3
    assert any("无懈可击" in p for p in prompts)


def test_dying_asks_table_peach_before_after_damage_skill() -> None:
    prompts: list[str] = []
    answers = iter(["y", "n"])

    def _input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    game = Game(
        Player(name="A", is_ai=False, general="郭嘉"),
        Player(name="B", is_ai=False, general="关羽"),
        seed=13,
        input_func=_input,
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    game.players = [a, b]
    a.hp = 1
    a.hand = []
    b.hand = [Card(CardName.TAO)]
    game.deal_damage(b, a, 1, reason="test")
    assert a.hp == 1
    assert "濒死求桃" in prompts[0]
    assert "遗计" in prompts[1]


def test_build_deck_is_random_when_seed_none() -> None:
    deck1 = build_deck(seed=None)
    deck2 = build_deck(seed=None)
    seq1 = [(c.name, c.suit, c.rank) for c in deck1]
    seq2 = [(c.name, c.suit, c.rank) for c in deck2]
    assert seq1 != seq2


def test_kurou_loses_hp_and_draws_without_after_damage_trigger() -> None:
    triggered = {"after_damage": False}

    def _after_damage(__game: Game, __owner: Player, **__: object) -> None:
        triggered["after_damage"] = True

    game = Game(
        Player(name="A", is_ai=False, general="黄盖"),
        Player(name="B", is_ai=True, general="关羽"),
        seed=2,
        input_func=lambda _: "n",
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    a.hand = []
    game.draw_pile = [Card(CardName.SHA), Card(CardName.TAO)]
    game.register_passive_skill("after_damage", a, "dummy", _after_damage)
    res = game._use_active_skill(a, b, 0)
    assert res.ok is True
    assert a.hp == a.max_hp - 1
    assert len(a.hand) == 2
    assert triggered["after_damage"] is False


def test_fanjian_target_chooses_suit_and_takes_damage_on_mismatch() -> None:
    answers = iter(["0"])
    game = Game(
        Player(name="A", is_ai=True, general="周瑜"),
        Player(name="B", is_ai=False, general="关羽"),
        seed=3,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA, suit="heart", rank=9)]
    b.hand = []
    before = b.hp
    res = game._use_active_skill(a, b, 0)
    assert res.ok is True
    assert b.hp == before - 1
    assert a.fanjian_used_this_turn is True


def test_ganglie_judges_and_forces_source_damage_when_refuse_discard() -> None:
    answers = iter(["y", "n"])
    game = Game(
        Player(name="A", is_ai=False, general="夏侯惇"),
        Player(name="B", is_ai=False, general="关羽"),
        seed=4,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    b.hand = [Card(CardName.SHA), Card(CardName.SHA)]
    game.draw_pile = [Card(CardName.SHA, suit="spade", rank=7)]
    before = b.hp
    game.deal_damage(b, a, 1, reason="test")
    assert b.hp == before - 1


def test_guicai_replaces_judgment_card() -> None:
    answers = iter(["y", "0"])
    game = Game(
        Player(name="A", is_ai=False, general="司马懿"),
        Player(name="B", is_ai=True, general="关羽"),
        seed=5,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    game.setup()
    a, b = game.player, game.enemy
    a.hand = [Card(CardName.SHA, suit="heart", rank=9)]
    game.draw_pile = [Card(CardName.SHA, suit="spade", rank=7)]
    res = game.run_judgment(b, reason_text="测试判定")
    assert isinstance(res, Card)
    assert res.suit == "heart"
    assert any(c.suit == "spade" for c in a.hand)


def test_tiandu_can_take_judgment_card() -> None:
    answers = iter(["y"])
    game = Game(
        Player(name="A", is_ai=False, general="郭嘉"),
        Player(name="B", is_ai=True, general="关羽"),
        seed=6,
        input_func=lambda _: next(answers),
        output_func=lambda _: None,
    )
    game.setup()
    a = game.player
    a.hand = []
    game.draw_pile = [Card(CardName.SHA, suit="spade", rank=7)]
    res = game.run_judgment(a, reason_text="天妒")
    assert isinstance(res, Card)
    assert len(a.hand) == 1
    assert all(c is not res for c in game.discard_pile)
