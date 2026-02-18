"""
백그라운드 액션 데이터 모델
메인 매크로 루프와 독립적으로 동작하는 반복 액션 정의
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List
from pathlib import Path

import yaml


class ActionType(str, Enum):
    """백그라운드 액션 타입"""
    KEY_PRESS = "key_press"           # 주기적 키 입력 (예: 점프)
    TAP_COORD = "tap_coord"           # 주기적 좌표 탭
    IMAGE_KEY = "image_key"           # 이미지 감지 시 키 입력
    IMAGE_TAP = "image_tap"           # 이미지 감지 시 이미지 위치 탭


ACTION_TYPE_LABELS = {
    ActionType.KEY_PRESS: "키 입력 (주기적)",
    ActionType.TAP_COORD: "좌표 탭 (주기적)",
    ActionType.IMAGE_KEY: "이미지 감지 → 키 입력",
    ActionType.IMAGE_TAP: "이미지 감지 → 탭",
}

# ADB 키코드 프리셋 (카테고리별)
KEYCODE_PRESETS = {
    # ── 게임 자주 사용 ──
    "스페이스바 (점프)": 62,
    "Enter (확인)": 66,
    "ESC (취소)": 111,
    "Back (뒤로)": 4,
    "Tab": 61,
    # ── 방향키 ──
    "↑ 위": 19,
    "↓ 아래": 20,
    "← 왼쪽": 21,
    "→ 오른쪽": 22,
    # ── 알파벳 ──
    "A": 29, "B": 30, "C": 31, "D": 32, "E": 33,
    "F": 34, "G": 35, "H": 36, "I": 37, "J": 38,
    "K": 39, "L": 40, "M": 41, "N": 42, "O": 43,
    "P": 44, "Q": 45, "R": 46, "S": 47, "T": 48,
    "U": 49, "V": 50, "W": 51, "X": 52, "Y": 53, "Z": 54,
    # ── 숫자 ──
    "0": 7, "1": 8, "2": 9, "3": 10, "4": 11,
    "5": 12, "6": 13, "7": 14, "8": 15, "9": 16,
    # ── 기능키 ──
    "F1": 131, "F2": 132, "F3": 133, "F4": 134,
    "F5": 135, "F6": 136, "F7": 137, "F8": 138,
    "F9": 139, "F10": 140, "F11": 141, "F12": 142,
    # ── 시스템 ──
    "Home": 3,
    "볼륨 업": 24,
    "볼륨 다운": 25,
    "메뉴": 82,
    "전원": 26,
    # ── 특수 ──
    "Shift": 59,
    "Ctrl": 113,
    "Alt": 57,
    "Delete": 67,
    "Caps Lock": 115,
}


@dataclass
class BackgroundAction:
    """단일 백그라운드 액션"""
    type: ActionType = ActionType.KEY_PRESS
    name: str = "새 액션"
    enabled: bool = True

    # 키 입력 관련
    keycode: int = 62  # 기본: 스페이스바
    keycode_label: str = "스페이스바 (점프)"

    # 좌표 관련
    x: int = 0
    y: int = 0

    # 이미지 관련
    template_path: str = ""
    threshold: float = 0.85

    # 타이밍
    interval: float = 2.0       # 실행 간격 (초)
    interval_jitter: float = 0.5  # 간격 랜덤 변동 ± (초)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BackgroundAction":
        d = d.copy()
        d["type"] = ActionType(d.get("type", "key_press"))
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        d = {k: v for k, v in d.items() if k in valid}
        return cls(**d)

    def display_text(self, index: int) -> str:
        label = ACTION_TYPE_LABELS.get(self.type, "?")
        status = "●" if self.enabled else "○"
        detail = ""
        if self.type == ActionType.KEY_PRESS:
            detail = f"키:{self.keycode_label}  {self.interval}초 간격"
        elif self.type == ActionType.TAP_COORD:
            detail = f"({self.x},{self.y})  {self.interval}초 간격"
        elif self.type == ActionType.IMAGE_KEY:
            tpl = Path(self.template_path).stem if self.template_path else "미설정"
            detail = f"[{tpl}]→키:{self.keycode_label}"
        elif self.type == ActionType.IMAGE_TAP:
            tpl = Path(self.template_path).stem if self.template_path else "미설정"
            detail = f"[{tpl}]→탭"
        return f"{status} {index}. [{label}] {self.name}  {detail}"


@dataclass
class BackgroundActionSet:
    """백그라운드 액션 세트 (저장/로드 단위)"""
    name: str = "백그라운드 액션"
    actions: List[BackgroundAction] = field(default_factory=list)

    def save(self, path: str):
        data = {
            "name": self.name,
            "actions": [a.to_dict() for a in self.actions],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def load(cls, path: str) -> "BackgroundActionSet":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            name=data.get("name", "unnamed"),
            actions=[BackgroundAction.from_dict(a) for a in data.get("actions", [])],
        )
