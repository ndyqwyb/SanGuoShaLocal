from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


@dataclass(frozen=True)
class LogEntry:
    seq: int
    message: str


@dataclass(frozen=True)
class PlayerSnapshot:
    name: str
    general: str | None
    hp: int
    max_hp: int
    hand_count: int
    hand: tuple["CardView", ...] | None
    weapon: str | None
    alive: bool
    armor: str | None = None
    plus_horse: str | None = None
    minus_horse: str | None = None
    judgment_area: tuple[str, ...] = ()
    active_skills: tuple[str, ...] = ()
    passive_skills: tuple[str, ...] = ()


@dataclass(frozen=True)
class PendingRequest:
    kind: str
    prompt: str


@dataclass(frozen=True)
class CardView:
    name: str
    suit: str
    rank: int


@dataclass(frozen=True)
class GameSnapshot:
    turn_index: int
    current_player: str | None
    phase: str
    draw_pile_count: int
    discard_pile_count: int
    human_index: int
    players: tuple[PlayerSnapshot, PlayerSnapshot]
    pending_request: PendingRequest | None
    winner: str | None


class ActionType(str, Enum):
    START = "start"
    RESTART = "restart"
    STOP = "stop"
    SUBMIT_TEXT = "submit_text"
    SKIP_AI_WAIT = "skip_ai_wait"


@dataclass(frozen=True)
class UIAction:
    type: ActionType
    text: str | None = None


class EnginePort(Protocol):
    def dispatch(self, action: UIAction) -> None: ...

    def get_snapshot(self) -> GameSnapshot: ...

    def drain_logs(self) -> list[LogEntry]: ...

    def close(self) -> None: ...
