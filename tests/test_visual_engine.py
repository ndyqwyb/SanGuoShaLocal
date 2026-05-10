from __future__ import annotations

import threading
import time

from sanguosha.ui_protocol import ActionType, UIAction
from sanguosha.visual_engine import LocalVisualEngine, SkippableDelay, VisualEngineConfig


def test_skippable_delay_can_be_skipped() -> None:
    delay = SkippableDelay(2.0)
    done = {"ok": False}

    def worker() -> None:
        delay.wait()
        done["ok"] = True

    t = threading.Thread(target=worker)
    start = time.monotonic()
    t.start()
    time.sleep(0.05)
    delay.skip()
    t.join(timeout=0.2)
    elapsed = time.monotonic() - start
    assert done["ok"] is True
    assert elapsed < 0.5


def test_local_visual_engine_exposes_pending_request_and_accepts_submit_text() -> None:
    engine = LocalVisualEngine(config=VisualEngineConfig(seed=5, ai_delay_seconds=0.0, max_rounds=2))
    try:
        def discard_answer(prompt: str) -> str:
            marker = "需弃"
            if marker in prompt and "张" in prompt:
                start = prompt.index(marker) + len(marker)
                end = prompt.index("张", start)
                need = int(prompt[start:end])
                return " ".join(str(i) for i in range(need))
            return "0"

        engine.dispatch(UIAction(type=ActionType.START))
        deadline = time.monotonic() + 3.0
        saw_play_prompt = False
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            req = snap.pending_request
            if req is not None and req.kind == "play":
                saw_play_prompt = True
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="p"))
                break
            time.sleep(0.01)
        assert saw_play_prompt is True

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            req = snap.pending_request
            if req is None:
                break
            if req.kind == "yesno":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="n"))
            elif req.kind == "discard_select":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=discard_answer(req.prompt)))
            elif req.kind == "area_select":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="h"))
            elif req.kind == "harvest_select":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="0"))
            time.sleep(0.01)
        assert engine.get_snapshot().pending_request is None
    finally:
        engine.close()


def test_local_visual_engine_e2e_scripted_playthrough_reaches_winner() -> None:
    engine = LocalVisualEngine(config=VisualEngineConfig(seed=7, ai_delay_seconds=0.0, max_rounds=50))
    try:
        def discard_answer(prompt: str) -> str:
            marker = "需弃"
            if marker in prompt and "张" in prompt:
                start = prompt.index(marker) + len(marker)
                end = prompt.index("张", start)
                need = int(prompt[start:end])
                return " ".join(str(i) for i in range(need))
            return "0"

        engine.dispatch(UIAction(type=ActionType.START))
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            if snap.winner is not None:
                break
            req = snap.pending_request
            if req is not None:
                if req.kind == "play":
                    engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="p"))
                elif req.kind == "yesno":
                    engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="n"))
                elif req.kind == "discard_select":
                    engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=discard_answer(req.prompt)))
                elif req.kind == "area_select":
                    engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="h"))
                elif req.kind == "harvest_select":
                    engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="0"))
                else:
                    engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=""))
            time.sleep(0.01)
        snap = engine.get_snapshot()
        assert snap.winner in {"玩家", "电脑"}
        logs = engine.drain_logs()
        assert any("获胜" in entry.message for entry in logs)
    finally:
        engine.close()


def test_local_visual_engine_restart_cancels_pending_input_and_resets_logs() -> None:
    engine = LocalVisualEngine(config=VisualEngineConfig(seed=11, ai_delay_seconds=0.0, max_rounds=20))
    try:
        engine.dispatch(UIAction(type=ActionType.START))
        deadline = time.monotonic() + 3.0
        saw_play_prompt = False
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            if snap.pending_request is not None and snap.pending_request.kind == "play":
                saw_play_prompt = True
                break
            time.sleep(0.01)
        assert saw_play_prompt is True

        engine.dispatch(UIAction(type=ActionType.RESTART))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            if snap.turn_index == 0 and snap.winner is None and snap.pending_request is not None:
                break
            time.sleep(0.01)
        snap = engine.get_snapshot()
        assert snap.turn_index == 0
        assert snap.winner is None

        engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="p"))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            req = snap.pending_request
            if req is None:
                break
            if req.kind == "yesno":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="n"))
            time.sleep(0.01)

        logs = engine.drain_logs()
        if logs:
            assert logs[0].seq == 1
    finally:
        engine.close()


def test_local_visual_engine_exposes_skills_and_accepts_active_skill_command() -> None:
    engine = LocalVisualEngine(config=VisualEngineConfig(seed=13, ai_delay_seconds=0.0, max_rounds=4))
    try:
        engine.dispatch(UIAction(type=ActionType.START))
        deadline = time.monotonic() + 3.0
        submitted_skill = False
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            human = snap.players[snap.human_index]
            assert "武圣" in human.active_skills
            req = snap.pending_request
            if req is not None and req.kind == "play":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="s0"))
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="p"))
                submitted_skill = True
                break
            time.sleep(0.01)
        assert submitted_skill is True

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            req = engine.get_snapshot().pending_request
            if req is None:
                break
            if req.kind == "yesno":
                engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="n"))
            time.sleep(0.01)
        logs = engine.drain_logs()
        assert any("武圣" in entry.message for entry in logs)
    finally:
        engine.close()


def test_start_and_restart_apply_selected_general() -> None:
    engine = LocalVisualEngine(config=VisualEngineConfig(seed=17, ai_delay_seconds=0.0, max_rounds=4))
    try:
        engine.dispatch(UIAction(type=ActionType.START, text="华佗"))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            human = snap.players[snap.human_index]
            if human.general is not None:
                break
            time.sleep(0.01)
        snap = engine.get_snapshot()
        human = snap.players[snap.human_index]
        enemy = snap.players[1 - snap.human_index]
        assert human.general == "华佗"
        assert enemy.general != "华佗"

        engine.dispatch(UIAction(type=ActionType.RESTART, text="黄月英"))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            human = snap.players[snap.human_index]
            if human.general == "黄月英":
                break
            time.sleep(0.01)
        snap = engine.get_snapshot()
        assert snap.players[snap.human_index].general == "黄月英"
    finally:
        engine.close()


def test_stop_then_start_uses_latest_selected_general() -> None:
    engine = LocalVisualEngine(config=VisualEngineConfig(seed=19, ai_delay_seconds=0.0, max_rounds=4))
    try:
        engine.dispatch(UIAction(type=ActionType.START, text="华佗"))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            human = snap.players[snap.human_index]
            if human.general == "华佗":
                break
            time.sleep(0.01)
        assert engine.get_snapshot().players[engine.get_snapshot().human_index].general == "华佗"

        engine.dispatch(UIAction(type=ActionType.STOP))
        engine.dispatch(UIAction(type=ActionType.START, text="黄月英"))
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = engine.get_snapshot()
            human = snap.players[snap.human_index]
            if human.general == "黄月英":
                break
            time.sleep(0.01)
        assert engine.get_snapshot().players[engine.get_snapshot().human_index].general == "黄月英"
    finally:
        engine.close()
