"""
매크로 스텝 데이터 모델 및 스크립트 저장/로드
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List
from pathlib import Path

import yaml


class StepType(str, Enum):
    CLICK_IMAGE = "click_image"
    CLICK_COORD = "click_coord"
    WAIT = "wait"
    WAIT_FOR_IMAGE = "wait_for_image"
    IF_IMAGE = "if_image"
    SWIPE = "swipe"


STEP_TYPE_LABELS = {
    StepType.CLICK_IMAGE: "이미지 클릭",
    StepType.CLICK_COORD: "좌표 클릭",
    StepType.WAIT: "대기",
    StepType.WAIT_FOR_IMAGE: "이미지 대기",
    StepType.IF_IMAGE: "조건 분기",
    StepType.SWIPE: "스와이프",
}

# 스텝 타입별 실패 가능 여부
CAN_FAIL_TYPES = {StepType.CLICK_IMAGE, StepType.WAIT_FOR_IMAGE, StepType.IF_IMAGE}

# 스텝 타입별 필요 필드
STEP_FIELDS = {
    StepType.CLICK_IMAGE:    {"template", "threshold", "on_fail", "retries"},
    StepType.CLICK_COORD:    {"coords"},
    StepType.WAIT:           {"wait_time"},
    StepType.WAIT_FOR_IMAGE: {"template", "threshold", "timeout", "on_fail", "retries"},
    StepType.IF_IMAGE:       {"template", "threshold", "on_fail"},
    StepType.SWIPE:          {"coords", "coords2", "duration"},
}


@dataclass
class MacroStep:
    type: StepType = StepType.CLICK_IMAGE
    name: str = "새 스텝"
    # 이미지 관련
    template_path: str = ""
    threshold: float = 0.85
    # 좌표 관련
    x: int = 0
    y: int = 0
    x2: int = 0
    y2: int = 0
    # 대기/타임아웃
    wait_time: float = 1.0
    timeout: float = 10.0
    # 스와이프
    duration_ms: int = 300
    # 흐름 제어
    on_success: str = "next"   # next, stop, loop, goto:N
    on_fail: str = "retry"     # next, stop, loop, retry, goto:N
    max_retries: int = 10
    retry_delay: float = 1.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "MacroStep":
        d = d.copy()
        d["type"] = StepType(d.get("type", "click_image"))
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        d = {k: v for k, v in d.items() if k in valid}
        return cls(**d)

    def display_text(self, index: int) -> str:
        label = STEP_TYPE_LABELS.get(self.type, "?")
        if self.type in (StepType.CLICK_IMAGE, StepType.WAIT_FOR_IMAGE, StepType.IF_IMAGE):
            detail = Path(self.template_path).stem if self.template_path else "미설정"
            return f"{index}. [{label}] {self.name}  [{detail}]"
        elif self.type == StepType.CLICK_COORD:
            return f"{index}. [{label}] {self.name}  ({self.x}, {self.y})"
        elif self.type == StepType.WAIT:
            return f"{index}. [{label}] {self.name}  ({self.wait_time}초)"
        elif self.type == StepType.SWIPE:
            return f"{index}. [{label}] {self.name}  ({self.x},{self.y})→({self.x2},{self.y2})"
        return f"{index}. [{label}] {self.name}"


@dataclass
class MacroScript:
    name: str = "새 매크로"
    description: str = ""
    steps: List[MacroStep] = field(default_factory=list)

    def save(self, path: str):
        data = {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

    @classmethod
    def load(cls, path: str) -> "MacroScript":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            steps=[MacroStep.from_dict(s) for s in data.get("steps", [])],
        )
