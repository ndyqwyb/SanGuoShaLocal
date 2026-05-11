from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .generals import GENERAL_POOL
from .ui_protocol import ActionType, CardView, UIAction
from .visual_engine import LocalVisualEngine


@dataclass(frozen=True)
class GuiConfig:
    refresh_ms: int = 100


def run_gui() -> None:
    from tkinter import StringVar, Tk, ttk
    from tkinter.scrolledtext import ScrolledText

    class App:
        def __init__(self, root: Any, *, config: GuiConfig | None = None) -> None:
            self.root = root
            self.config = config or GuiConfig()
            self.engine = LocalVisualEngine()
            self._style = ttk.Style()
            self._style.configure("Selected.TButton", font=("TkDefaultFont", 10, "bold"))
            self._frame = ttk.Frame(root, padding=16)
            self._frame.grid(row=0, column=0, sticky="nsew")
            root.grid_rowconfigure(0, weight=1)
            root.grid_columnconfigure(0, weight=1)

            # 必须先初始化 textvariable，再构建使用这些变量的页面控件。
            self._current_page: str | None = None
            self._winner_var = StringVar(value="")
            self._self_var = StringVar(value="")
            self._enemy_var = StringVar(value="")
            self._status_var = StringVar(value="")
            self._hint_var = StringVar(value="")
            self._general_var = StringVar(value=GENERAL_POOL[0].name if GENERAL_POOL else "")
            self._log_widget: Any | None = None
            self._hand_cards: tuple[CardView, ...] = ()
            self._hand_buttons: list[Any] = []
            self._hand_frame: Any | None = None
            self._selected_index: int | None = None
            self._multi_selected: set[int] = set()
            self._confirm_btn: Any | None = None
            self._cancel_btn: Any | None = None
            self._end_phase_btn: Any | None = None
            self._skip_btn: Any | None = None
            self._self_box: Any | None = None
            self._enemy_box: Any | None = None
            self._active_skill_buttons: list[Any] = []
            self._active_skill_frame: Any | None = None
            self._passive_skill_var = StringVar(value="无")
            self._active_skill_desc_var = StringVar(value="")
            self._active_modal: Any | None = None
            self._active_modal_kind: str | None = None
            self._active_modal_prompt: str | None = None

            self.pages: dict[str, Any] = {
                "start": self._build_start_page(self._frame),
                "battle": self._build_battle_page(self._frame),
                "end": self._build_end_page(self._frame),
            }
            self._last_request_kind: str | None = None

            self.show("start")
            self._tick()

        def show(self, name: str) -> None:
            if self._current_page is not None:
                self.pages[self._current_page].grid_forget()
            page = self.pages[name]
            page.grid(row=0, column=0, sticky="nsew")
            self._current_page = name

        def _build_start_page(self, parent: Any) -> Any:
            page = ttk.Frame(parent)
            title = ttk.Label(page, text="本地 1v1 三国杀", font=("TkDefaultFont", 16, "bold"))
            title.grid(row=0, column=0, pady=(0, 12))
            ttk.Label(page, text="选择我方武将").grid(row=1, column=0, sticky="w", pady=(0, 6))
            general_names = [g.name for g in GENERAL_POOL]
            general_combo = ttk.Combobox(page, textvariable=self._general_var, values=general_names, state="readonly")
            general_combo.grid(row=2, column=0, sticky="ew", pady=(0, 12))
            page.grid_columnconfigure(0, weight=1)
            btn = ttk.Button(page, text="开始对局", command=self._start_game)
            btn.grid(row=3, column=0)
            return page

        def _build_battle_page(self, parent: Any) -> Any:
            from tkinter import Frame

            page = ttk.Frame(parent)
            page.grid_columnconfigure(0, weight=1)
            page.grid_rowconfigure(4, weight=1)

            info = ttk.Frame(page)
            info.grid(row=0, column=0, sticky="ew")
            info.grid_columnconfigure(0, weight=1)
            info.grid_columnconfigure(1, weight=1)

            self_box = Frame(info, bd=2, relief="groove", padx=8, pady=6)
            self_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
            self_box.grid_columnconfigure(0, weight=1)
            ttk.Label(self_box, text="我方").grid(row=0, column=0, sticky="w")
            ttk.Label(self_box, textvariable=self._self_var).grid(row=1, column=0, sticky="w")
            self._self_box = self_box

            enemy_box = Frame(info, bd=2, relief="groove", padx=8, pady=6)
            enemy_box.grid(row=0, column=1, sticky="ew")
            enemy_box.grid_columnconfigure(0, weight=1)
            ttk.Label(enemy_box, text="对方").grid(row=0, column=0, sticky="e")
            ttk.Label(enemy_box, textvariable=self._enemy_var).grid(row=1, column=0, sticky="e")
            self._enemy_box = enemy_box

            ttk.Label(page, textvariable=self._status_var).grid(row=1, column=0, sticky="w", pady=(10, 4))
            ttk.Label(page, textvariable=self._hint_var, foreground="#8a6d3b").grid(
                row=2, column=0, sticky="w", pady=(0, 8)
            )

            hand_area = ttk.Frame(page)
            hand_area.grid(row=3, column=0, sticky="nsew")
            hand_area.grid_columnconfigure(0, weight=1)
            hand_area.grid_rowconfigure(1, weight=0)
            ttk.Label(hand_area, text="你的手牌").grid(row=0, column=0, sticky="w")
            hand_frame = ttk.Frame(hand_area)
            hand_frame.grid(row=1, column=0, sticky="ew", pady=(6, 0))
            self._hand_frame = hand_frame

            controls = ttk.Frame(hand_area)
            controls.grid(row=2, column=0, sticky="ew", pady=(10, 10))
            confirm_btn = ttk.Button(controls, text="确认", command=self._confirm_play)
            confirm_btn.grid(row=0, column=0)
            cancel_btn = ttk.Button(controls, text="取消", command=self._cancel_selection)
            cancel_btn.grid(row=0, column=1, padx=(8, 0))
            end_phase_btn = ttk.Button(controls, text="结束出牌阶段", command=self._end_play_phase)
            end_phase_btn.grid(row=0, column=2, padx=(8, 0))
            skip_btn = ttk.Button(controls, text="跳过 AI 等待", command=self._skip_ai_wait)
            skip_btn.grid(row=0, column=3, padx=(8, 0))
            self._confirm_btn = confirm_btn
            self._cancel_btn = cancel_btn
            self._end_phase_btn = end_phase_btn
            self._skip_btn = skip_btn

            skill_area = ttk.Frame(page)
            skill_area.grid(row=4, column=0, sticky="ew", pady=(0, 8))
            skill_area.grid_columnconfigure(1, weight=1)
            ttk.Label(skill_area, text="主动技能").grid(row=0, column=0, sticky="w")
            active_skill_frame = ttk.Frame(skill_area)
            active_skill_frame.grid(row=0, column=1, sticky="w")
            self._active_skill_frame = active_skill_frame
            self._active_skill_buttons = []
            ttk.Label(skill_area, text="被动技能").grid(row=1, column=0, sticky="w", pady=(6, 0))
            ttk.Label(skill_area, textvariable=self._passive_skill_var).grid(row=1, column=1, sticky="w", pady=(6, 0))

            log_widget = ScrolledText(page, height=16, state="disabled", wrap="word")
            log_widget.grid(row=5, column=0, sticky="nsew")
            page.grid_rowconfigure(5, weight=1)
            self._log_widget = log_widget

            footer = ttk.Frame(page)
            footer.grid(row=6, column=0, sticky="ew", pady=(10, 0))
            ttk.Button(footer, text="返回开始", command=self._restart_game).grid(row=0, column=0)
            ttk.Button(footer, text="退出", command=self.root.destroy).grid(row=0, column=1, padx=(8, 0))
            return page

        def _build_end_page(self, parent: Any) -> Any:
            page = ttk.Frame(parent)
            label = ttk.Label(page, textvariable=self._winner_var, font=("TkDefaultFont", 14, "bold"))
            label.grid(row=0, column=0, pady=(0, 12))
            btns = ttk.Frame(page)
            btns.grid(row=1, column=0)
            ttk.Button(btns, text="返回开始页", command=self._restart_game).grid(row=0, column=0)
            ttk.Button(btns, text="退出", command=self.root.destroy).grid(row=0, column=1, padx=(8, 0))
            return page

        def _start_game(self) -> None:
            self.engine.dispatch(UIAction(type=ActionType.START, text=self._general_var.get().strip() or None))
            self._clear_logs()
            self._cancel_selection()
            self._close_active_modal()
            self.show("battle")

        def _restart_game(self) -> None:
            self.engine.dispatch(UIAction(type=ActionType.STOP))
            self.engine = LocalVisualEngine()
            self._clear_logs()
            self._cancel_selection()
            self._close_active_modal()
            self._last_request_kind = None
            self.show("start")

        def _tick(self) -> None:
            snapshot = self.engine.get_snapshot()
            req_kind = snapshot.pending_request.kind if snapshot.pending_request is not None else None
            if req_kind != self._last_request_kind:
                self._cancel_selection()
            self._last_request_kind = req_kind
            human = snapshot.players[snapshot.human_index]
            enemy = snapshot.players[1 - snapshot.human_index]
            self._self_var.set(self._format_player(human))
            self._enemy_var.set(self._format_player(enemy))
            current_player = snapshot.current_player or "-"
            self._status_var.set(
                "  ".join(
                    [
                        f"回合：{snapshot.turn_index}",
                        f"当前：{current_player}",
                        f"阶段：{snapshot.phase}",
                        f"牌堆：{snapshot.draw_pile_count}",
                        f"弃牌：{snapshot.discard_pile_count}",
                    ]
                )
            )

            for entry in self.engine.drain_logs():
                self._append_log(entry.message)

            self._sync_hand(human.hand or ())
            self._sync_interactions(snapshot, human.name)
            self._sync_skills(snapshot, human.name)
            self._sync_target_highlight(human.name, enemy.name)

            if snapshot.winner is not None and self._current_page != "end":
                self._winner_var.set(f"对局结束，胜者：{snapshot.winner}")
                self.show("end")

            self.root.after(self.config.refresh_ms, self._tick)

        def _format_player(self, p: object) -> str:
            ps = p
            name = getattr(ps, "name", "")
            general = getattr(ps, "general", None)
            hp = getattr(ps, "hp", 0)
            max_hp = getattr(ps, "max_hp", 0)
            hand_count = getattr(ps, "hand_count", 0)
            weapon = getattr(ps, "weapon", None)
            armor = getattr(ps, "armor", None)
            plus_horse = getattr(ps, "plus_horse", None)
            minus_horse = getattr(ps, "minus_horse", None)
            judgment_area = getattr(ps, "judgment_area", ())
            parts = [name]
            if general:
                parts.append(f"({general})")
            parts.append(f"HP {hp}/{max_hp}")
            parts.append(f"手牌 {hand_count}")
            if weapon:
                parts.append(f"武器 {weapon}")
            if armor:
                parts.append(f"防具 {armor}")
            if plus_horse:
                parts.append(f"+1马 {plus_horse}")
            if minus_horse:
                parts.append(f"-1马 {minus_horse}")
            if judgment_area:
                parts.append("判定[" + "、".join(judgment_area) + "]")
            return "  ".join(parts)

        def _format_hand_card(self, card: CardView) -> str:
            suit_map = {"heart": "♥", "diamond": "♦", "club": "♣", "spade": "♠"}
            symbol = suit_map.get(card.suit, card.suit)
            return f"{card.name} {symbol}{card.rank}"

        def _sync_hand(self, cards: tuple[CardView, ...]) -> None:
            if self._hand_frame is None:
                return
            if cards == self._hand_cards and len(self._hand_buttons) == len(cards):
                self._refresh_hand_styles()
                return
            for btn in self._hand_buttons:
                btn.destroy()
            self._hand_buttons.clear()
            self._hand_cards = cards
            self._selected_index = None
            self._multi_selected.clear()
            for idx, card in enumerate(cards):
                btn = ttk.Button(self._hand_frame, text=self._format_hand_card(card), command=lambda i=idx: self._select_card(i))
                btn.grid(row=0, column=idx, padx=(0, 6), pady=2, sticky="w")
                self._hand_buttons.append(btn)
            self._refresh_hand_styles()

        def _refresh_hand_styles(self) -> None:
            for idx, btn in enumerate(self._hand_buttons):
                selected = idx == self._selected_index or idx in self._multi_selected
                btn.configure(style="Selected.TButton" if selected else "TButton")

        def _select_card(self, idx: int) -> None:
            snapshot = self.engine.get_snapshot()
            req = snapshot.pending_request
            if req is None:
                return
            if req.kind == "discard_select":
                if idx in self._multi_selected:
                    self._multi_selected.remove(idx)
                else:
                    self._multi_selected.add(idx)
                need = self._parse_needed_discard(req.prompt)
                left = max(need - len(self._multi_selected), 0)
                self._hint_var.set(f"弃牌阶段：还需选择 {left} 张。")
                self._refresh_hand_styles()
                return
            if req.kind == "skill_card_select":
                if self._selected_index == idx:
                    self._selected_index = None
                    self._hint_var.set("技能选牌：请先选择要弃置的手牌。")
                else:
                    self._selected_index = idx
                    self._hint_var.set("技能选牌：已选中，点击确认提交。")
                self._refresh_hand_styles()
                return
            if req.kind != "play" or not self._is_waiting_for_play():
                return
            if self._selected_index == idx:
                self._selected_index = None
                self._hint_var.set("")
            else:
                self._selected_index = idx
                target = self._target_for_card(self._hand_cards[idx].name)
                if target == "self":
                    self._hint_var.set("目标：自己（确认后使用）")
                elif target == "enemy":
                    self._hint_var.set("目标：对方（确认后使用）")
                else:
                    self._hint_var.set("确认后执行")
            self._refresh_hand_styles()

        def _confirm_play(self) -> None:
            snapshot = self.engine.get_snapshot()
            req = snapshot.pending_request
            if req is None:
                return
            if req.kind == "discard_select":
                need = self._parse_needed_discard(req.prompt)
                if len(self._multi_selected) != need:
                    self._hint_var.set(f"请恰好选择 {need} 张要弃置的牌。")
                    return
                text = " ".join(str(i) for i in sorted(self._multi_selected))
                self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=text))
                self._multi_selected.clear()
                self._hint_var.set("")
                self._refresh_hand_styles()
                return
            if req.kind == "skill_card_select":
                if self._selected_index is None:
                    self._hint_var.set("技能选牌：请先选择一张手牌。")
                    return
                self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=str(self._selected_index)))
                self._selected_index = None
                self._hint_var.set("")
                self._refresh_hand_styles()
                return
            if not self._is_waiting_for_play():
                return
            if self._selected_index is None:
                self._hint_var.set("请先选择一张手牌。")
                return
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=str(self._selected_index)))
            self._selected_index = None
            self._hint_var.set("")
            self._refresh_hand_styles()

        def _cancel_selection(self) -> None:
            self._selected_index = None
            self._multi_selected.clear()
            self._hint_var.set("")
            self._refresh_hand_styles()

        def _end_play_phase(self) -> None:
            if not self._is_waiting_for_play():
                return
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text="p"))
            self._cancel_selection()

        def _skip_ai_wait(self) -> None:
            self.engine.dispatch(UIAction(type=ActionType.SKIP_AI_WAIT))

        def _trigger_active_skill(self, skill_index: int) -> None:
            if not self._is_waiting_for_play():
                return
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=f"s{skill_index}"))
            self._cancel_selection()

        def _is_waiting_for_play(self) -> bool:
            snapshot = self.engine.get_snapshot()
            req = snapshot.pending_request
            if req is None or req.kind != "play":
                return False
            human = snapshot.players[snapshot.human_index]
            return snapshot.current_player == human.name

        def _sync_interactions(self, snapshot: Any, human_name: str) -> None:
            req = snapshot.pending_request
            can_play = req is not None and req.kind == "play" and snapshot.current_player == human_name
            can_discard = req is not None and req.kind == "discard_select" and snapshot.current_player == human_name
            can_skill_card = req is not None and req.kind == "skill_card_select" and snapshot.current_player == human_name
            for btn in self._hand_buttons:
                btn.configure(state=("normal" if (can_play or can_discard or can_skill_card) else "disabled"))
            if self._confirm_btn is not None:
                self._confirm_btn.configure(state=("normal" if (can_play or can_discard or can_skill_card) else "disabled"))
            if self._cancel_btn is not None:
                self._cancel_btn.configure(state=("normal" if (can_play or can_discard or can_skill_card) else "disabled"))
            if self._end_phase_btn is not None:
                self._end_phase_btn.configure(state=("normal" if can_play else "disabled"))
            self._sync_modal_request(req)

        def _sync_modal_request(self, req: Any) -> None:
            modal_kinds = {"yesno", "skill_target_select", "area_select", "harvest_select"}
            if req is None or req.kind not in modal_kinds:
                self._close_active_modal()
                return
            if (
                self._active_modal is not None
                and self._active_modal.winfo_exists()
                and self._active_modal_kind == req.kind
                and self._active_modal_prompt == req.prompt
            ):
                return
            self._close_active_modal()
            self._create_modal(req.kind, req.prompt)

        def _create_modal(self, kind: str, prompt: str) -> None:
            from tkinter import Toplevel

            title_map = {
                "yesno": "响应选择",
                "skill_target_select": "技能目标",
                "area_select": "区域选择",
                "harvest_select": "五谷丰登",
            }
            modal = Toplevel(self.root)
            modal.title(title_map.get(kind, "输入"))
            modal.transient(self.root)
            modal.resizable(False, False)
            modal.protocol("WM_DELETE_WINDOW", lambda: None)
            modal.bind("<Escape>", lambda _event: "break")
            body = ttk.Frame(modal, padding=12)
            body.grid(row=0, column=0, sticky="nsew")
            ttk.Label(body, text=prompt, foreground="#8a6d3b", wraplength=420, justify="left").grid(
                row=0, column=0, sticky="w"
            )
            btn_row = ttk.Frame(body)
            btn_row.grid(row=1, column=0, sticky="w", pady=(10, 0))

            if kind == "yesno":
                ttk.Button(btn_row, text="是 (y)", command=lambda: self._submit_response("y")).grid(row=0, column=0)
                ttk.Button(btn_row, text="否 (n)", command=lambda: self._submit_response("n")).grid(
                    row=0, column=1, padx=(8, 0)
                )
            elif kind == "skill_target_select":
                options = self._parse_indexed_options(prompt)
                for idx, label in sorted(options.items()):
                    ttk.Button(btn_row, text=f"{label}[{idx}]", command=lambda x=idx: self._submit_skill_target(str(x))).grid(
                        row=idx // 3, column=idx % 3, padx=(0, 8), pady=(0, 6), sticky="w"
                    )
            elif kind == "area_select":
                area_codes = [("h", "手牌"), ("w", "武器"), ("a", "防具"), ("p", "+1马"), ("m", "-1马"), ("j", "判定区")]
                for idx, (code, text) in enumerate(area_codes):
                    ttk.Button(btn_row, text=text, command=lambda c=code: self._submit_area(c)).grid(
                        row=idx // 3, column=idx % 3, padx=(0, 8), pady=(0, 6), sticky="w"
                    )
            elif kind == "harvest_select":
                options = self._parse_indexed_options(prompt)
                for idx, label in sorted(options.items()):
                    ttk.Button(btn_row, text=label, command=lambda x=idx: self._submit_harvest(x)).grid(
                        row=idx // 3, column=idx % 3, padx=(0, 8), pady=(0, 6), sticky="w"
                    )

            modal.update_idletasks()
            self._center_modal(modal)
            modal.grab_set()
            modal.focus_force()
            self._active_modal = modal
            self._active_modal_kind = kind
            self._active_modal_prompt = prompt

        def _center_modal(self, modal: Any) -> None:
            self.root.update_idletasks()
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            mw = modal.winfo_reqwidth()
            mh = modal.winfo_reqheight()
            left = max(x + (w - mw) // 2, 0)
            top = max(y + (h - mh) // 2, 0)
            modal.geometry(f"+{left}+{top}")

        def _close_active_modal(self) -> None:
            modal = self._active_modal
            if modal is not None:
                try:
                    if modal.winfo_exists():
                        modal.grab_release()
                        modal.destroy()
                except Exception:
                    pass
            self._active_modal = None
            self._active_modal_kind = None
            self._active_modal_prompt = None

        def _submit_area(self, code: str) -> None:
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=code))
            self._close_active_modal()

        def _submit_harvest(self, idx: int) -> None:
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=str(idx)))
            self._close_active_modal()

        def _submit_skill_target(self, idx: str) -> None:
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=idx))
            self._close_active_modal()

        def _parse_needed_discard(self, prompt: str) -> int:
            marker = "需弃"
            if marker in prompt and "张" in prompt:
                try:
                    start = prompt.index(marker) + len(marker)
                    end = prompt.index("张", start)
                    return max(0, int(prompt[start:end]))
                except Exception:
                    return 0
            return 0

        def _parse_indexed_options(self, prompt: str) -> dict[int, str]:
            options: dict[int, str] = {}
            for seg in prompt.split("["):
                if "]" not in seg:
                    continue
                idx_txt, rest = seg.split("]", 1)
                idx_txt = idx_txt.strip()
                if not idx_txt.isdigit():
                    continue
                idx = int(idx_txt)
                label = rest.strip().split(" [")[0].strip().rstrip(":").rstrip("：")
                options[idx] = label
            return options

        def _submit_response(self, ans: str) -> None:
            self.engine.dispatch(UIAction(type=ActionType.SUBMIT_TEXT, text=ans))
            self._close_active_modal()

        def _sync_skills(self, snapshot: Any, human_name: str) -> None:
            human = snapshot.players[snapshot.human_index]
            can_play = (
                snapshot.pending_request is not None
                and snapshot.pending_request.kind == "play"
                and snapshot.current_player == human_name
            )
            if self._active_skill_frame is None:
                return
            need = len(human.active_skills)
            while len(self._active_skill_buttons) < need:
                idx = len(self._active_skill_buttons)
                btn = ttk.Button(
                    self._active_skill_frame,
                    text=f"技能{idx + 1}",
                    command=lambda i=idx: self._trigger_active_skill(i),
                )
                btn.grid(row=0, column=idx, padx=(0, 6))
                self._active_skill_buttons.append(btn)
            while len(self._active_skill_buttons) > need:
                btn = self._active_skill_buttons.pop()
                btn.destroy()
            for idx, btn in enumerate(self._active_skill_buttons):
                btn.configure(text=human.active_skills[idx], state=("normal" if can_play else "disabled"))
            self._passive_skill_var.set("、".join(human.passive_skills) if human.passive_skills else "无")
            desc_lines: list[str] = []
            if human.general:
                for g in GENERAL_POOL:
                    if g.name == human.general:
                        for s in g.skills:
                            desc_lines.append(f"{s.name}：{s.description}")
                        break
            self._hint_var.set(self._hint_var.get() if self._hint_var.get() else (" | ".join(desc_lines[:2]) if desc_lines else ""))

        def _target_for_card(self, card_name: str) -> str | None:
            if card_name in (
                "桃",
                "诸葛连弩",
                "青釭剑",
                "八卦阵",
                "赤兔",
                "紫骍",
                "的卢",
                "无中生有",
                "桃园结义",
                "五谷丰登",
                "闪电",
            ):
                return "self"
            if card_name in (
                "杀",
                "决斗",
                "过河拆桥",
                "顺手牵羊",
                "借刀杀人",
                "南蛮入侵",
                "万箭齐发",
                "乐不思蜀",
                "兵粮寸断",
            ):
                return "enemy"
            return "enemy"

        def _sync_target_highlight(self, human_name: str, enemy_name: str) -> None:
            if self._self_box is None or self._enemy_box is None:
                return
            self_box = self._self_box
            enemy_box = self._enemy_box
            self_box.configure(background=self.root.cget("background"))
            enemy_box.configure(background=self.root.cget("background"))
            if not self._is_waiting_for_play() or self._selected_index is None:
                return
            target = self._target_for_card(self._hand_cards[self._selected_index].name)
            if target == "self":
                self_box.configure(background="#fff3cd")
            elif target == "enemy":
                enemy_box.configure(background="#fff3cd")

        def _append_log(self, message: str) -> None:
            if self._log_widget is None:
                return
            if "你当前体力" in message or message.startswith("手牌："):
                return
            if not message.startswith("["):
                message = "[信息] " + message
            self._log_widget.configure(state="normal")
            if message.startswith("[声明]"):
                self._log_widget.insert("end", "\n")
            self._log_widget.insert("end", message + "\n")
            self._log_widget.see("end")
            self._log_widget.configure(state="disabled")

        def _clear_logs(self) -> None:
            if self._log_widget is None:
                return
            self._log_widget.configure(state="normal")
            self._log_widget.delete("1.0", "end")
            self._log_widget.configure(state="disabled")

    root = Tk()
    root.title("本地 1v1 三国杀")
    App(root)
    root.mainloop()
