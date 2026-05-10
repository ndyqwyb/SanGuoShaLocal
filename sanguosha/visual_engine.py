from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, Thread

from .generals import GENERAL_POOL, get_general_by_name
from .game import Game
from .player import Player
from .ui_protocol import ActionType, CardView, EnginePort, GameSnapshot, LogEntry, PendingRequest, PlayerSnapshot, UIAction


@dataclass(frozen=True)
class VisualEngineConfig:
    seed: int | None = None
    ai_delay_seconds: float = 0.35
    max_rounds: int = 200


class SkippableDelay:
    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds
        self._event = Event()

    def set_delay(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    def wait(self) -> None:
        if self._delay_seconds <= 0:
            return
        if self._event.is_set():
            self._event.clear()
            return
        self._event.wait(timeout=self._delay_seconds)
        self._event.clear()

    def skip(self) -> None:
        self._event.set()


class LocalVisualEngine(EnginePort):
    def __init__(self, *, config: VisualEngineConfig | None = None) -> None:
        self._config = config or VisualEngineConfig()
        self._snapshot_lock = Lock()
        self._token_lock = Lock()
        self._log_queue: Queue[LogEntry] = Queue()
        self._input_queue: Queue[str] = Queue()
        self._ai_delay = SkippableDelay(self._config.ai_delay_seconds)
        self._seq = 0
        self._run_token = 0
        self._thread: Thread | None = None
        self._selected_human_general: str | None = None
        self._phase = "未开始"
        self._pending_request: PendingRequest | None = None
        self._latest_snapshot = self._initial_snapshot()

    def dispatch(self, action: UIAction) -> None:
        if action.type == ActionType.START:
            if self._thread is not None and self._thread.is_alive():
                return
            self._selected_human_general = self._normalize_general_choice(action.text)
            self._start_game_thread(reset_state=True)
            return

        if action.type == ActionType.RESTART:
            self._cancel_current_session()
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=5)
            self._selected_human_general = self._normalize_general_choice(action.text)
            self._start_game_thread(reset_state=True)
            return

        if action.type == ActionType.STOP:
            self.close()
            return

        if action.type == ActionType.SUBMIT_TEXT:
            if action.text is not None:
                self._input_queue.put(action.text)
            return

        if action.type == ActionType.SKIP_AI_WAIT:
            self._ai_delay.skip()
            return

    def get_snapshot(self) -> GameSnapshot:
        with self._snapshot_lock:
            return self._latest_snapshot

    def drain_logs(self) -> list[LogEntry]:
        drained: list[LogEntry] = []
        while True:
            try:
                drained.append(self._log_queue.get_nowait())
            except Exception:
                return drained

    def close(self) -> None:
        self._cancel_current_session()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _initial_snapshot(self) -> GameSnapshot:
        return GameSnapshot(
            turn_index=0,
            current_player=None,
            phase=self._phase,
            draw_pile_count=0,
            discard_pile_count=0,
            human_index=0,
            players=(
                PlayerSnapshot(
                    name="玩家",
                    general=None,
                    hp=0,
                    max_hp=0,
                    hand_count=0,
                    hand=(),
                    weapon=None,
                    alive=True,
                    armor=None,
                    plus_horse=None,
                    minus_horse=None,
                    judgment_area=(),
                    active_skills=(),
                    passive_skills=(),
                ),
                PlayerSnapshot(
                    name="电脑",
                    general=None,
                    hp=0,
                    max_hp=0,
                    hand_count=0,
                    hand=None,
                    weapon=None,
                    alive=True,
                    armor=None,
                    plus_horse=None,
                    minus_horse=None,
                    judgment_area=(),
                    active_skills=(),
                    passive_skills=(),
                ),
            ),
            pending_request=None,
            winner=None,
        )

    def _reset_runtime_state(self) -> None:
        self._phase = "未开始"
        self._pending_request = None
        with self._snapshot_lock:
            self._latest_snapshot = self._initial_snapshot()
        self._seq = 0
        self._drain_queue(self._log_queue)
        self._drain_queue(self._input_queue)
        self._ai_delay.skip()

    def _drain_queue(self, q: Queue[object]) -> None:
        while True:
            try:
                q.get_nowait()
            except Exception:
                return

    def _cancel_current_session(self) -> None:
        with self._token_lock:
            self._run_token += 1
        self._ai_delay.skip()

    def _start_game_thread(self, *, reset_state: bool) -> None:
        if reset_state:
            self._reset_runtime_state()
        with self._token_lock:
            token = self._run_token
        self._thread = Thread(target=lambda: self._run_game(token), daemon=True)
        self._thread.start()

    def _run_game(self, token: int) -> None:
        human = Player(name="玩家", is_ai=False, general=self._selected_human_general)
        ai = Player(name="电脑", is_ai=True, general=None)

        class _EngineCancelled(Exception):
            pass

        def output(message: str) -> None:
            if token != self._run_token:
                return
            self._handle_game_output(game, message)

        def input_func(prompt: str) -> str:
            if token != self._run_token:
                raise _EngineCancelled()
            kind = self._classify_prompt(prompt)
            self._phase = self._phase_for_kind(kind)
            self._pending_request = PendingRequest(kind=kind, prompt=prompt)
            self._update_snapshot(game)
            ans = self._wait_for_input(token, _EngineCancelled)
            self._pending_request = None
            if game.winner is None:
                self._phase = "进行中"
            self._update_snapshot(game)
            return ans

        game = Game(human, ai, seed=self._config.seed, input_func=input_func, output_func=output)
        try:
            self._update_snapshot(game)
            winner = game.run(max_rounds=self._config.max_rounds)
            self._update_snapshot(game, winner=winner.name if winner else None)
        except _EngineCancelled:
            return

    def _wait_for_input(self, token: int, exc_type: type[Exception]) -> str:
        while True:
            if token != self._run_token:
                raise exc_type()
            try:
                return self._input_queue.get(timeout=0.05)
            except Empty:
                continue

    def _handle_game_output(self, game: Game, message: str) -> None:
        self._seq += 1
        self._log_queue.put(LogEntry(seq=self._seq, message=message))
        self._update_snapshot(game)
        if self._should_delay_for_message(message):
            self._wait_ai_delay()

    def _update_snapshot(self, game: Game, *, winner: str | None = None) -> None:
        p1 = game.players[0]
        p2 = game.players[1]
        resolved_winner = winner if winner is not None else (game.winner.name if game.winner else None)
        human_index = 0
        for idx, p in enumerate(game.players):
            if not p.is_ai:
                human_index = idx
                break
        snapshot = GameSnapshot(
            turn_index=game.turn_index,
            current_player=game.current_player().name if game.winner is None else None,
            phase="结束" if resolved_winner is not None else self._phase,
            draw_pile_count=len(game.draw_pile),
            discard_pile_count=len(game.discard_pile),
            human_index=human_index,
            players=(
                self._player_snapshot(p1, show_hand=human_index == 0),
                self._player_snapshot(p2, show_hand=human_index == 1),
            ),
            pending_request=None if resolved_winner is not None else self._pending_request,
            winner=resolved_winner,
        )
        with self._snapshot_lock:
            self._latest_snapshot = snapshot

    def _player_snapshot(self, p: Player, *, show_hand: bool) -> PlayerSnapshot:
        active_skills: tuple[str, ...] = ()
        passive_skills: tuple[str, ...] = ()
        if p.general is not None:
            general = get_general_by_name(p.general)
            active_skills = tuple(skill.name for skill in general.skills if skill.kind == "active")
            passive_skills = tuple(skill.name for skill in general.skills if skill.kind == "passive")
        return PlayerSnapshot(
            name=p.name,
            general=p.general,
            hp=p.hp,
            max_hp=p.max_hp,
            hand_count=len(p.hand),
            hand=tuple(CardView(name=c.name, suit=c.suit, rank=c.rank) for c in p.hand) if show_hand else None,
            weapon=p.weapon.name if p.weapon else None,
            alive=p.alive,
            armor=p.armor.name if p.armor else None,
            plus_horse=p.plus_horse.name if p.plus_horse else None,
            minus_horse=p.minus_horse.name if p.minus_horse else None,
            judgment_area=tuple(card.name for card in p.judgment_area),
            active_skills=active_skills,
            passive_skills=passive_skills,
        )

    def _classify_prompt(self, prompt: str) -> str:
        p = prompt.lower()
        if "请选择武将" in prompt:
            return "general"
        if "弃牌选择" in prompt:
            return "discard_select"
        if "区域选择" in prompt:
            return "area_select"
        if "五谷选择" in prompt:
            return "harvest_select"
        if "技能选牌" in prompt:
            return "skill_card_select"
        if "技能目标" in prompt:
            return "skill_target_select"
        if "(y/n)" in p:
            return "yesno"
        if "结束出牌阶段" in prompt or "输入牌序号" in prompt:
            return "play"
        return "text"

    def _phase_for_kind(self, kind: str) -> str:
        if kind == "play":
            return "出牌阶段"
        if kind == "yesno":
            return "响应"
        if kind == "discard_select":
            return "弃牌阶段"
        if kind == "area_select":
            return "目标选择"
        if kind == "harvest_select":
            return "五谷丰登"
        if kind in {"skill_card_select", "skill_target_select"}:
            return "技能选择"
        if kind == "general":
            return "选将"
        return "等待输入"

    def _should_delay_for_message(self, message: str) -> bool:
        if self._config.ai_delay_seconds <= 0:
            return False
        return "电脑" in message

    def _wait_ai_delay(self) -> None:
        self._ai_delay.set_delay(self._config.ai_delay_seconds)
        self._ai_delay.wait()

    def _normalize_general_choice(self, text: str | None) -> str | None:
        candidate = (text or "").strip()
        if candidate:
            return candidate
        return GENERAL_POOL[0].name if GENERAL_POOL else None
