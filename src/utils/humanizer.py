"""
Humanizer - 사람처럼 보이는 입력 시뮬레이션
매크로 탐지 회피를 위한 랜덤화 모듈
"""

import random
import time
import math
from typing import Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Humanizer:
    """매크로 탐지 회피를 위한 사람 같은 행동 시뮬레이터"""

    def __init__(self, click_offset_range: int = 5,
                 min_delay: float = 0.3, max_delay: float = 1.2,
                 min_hold_ms: int = 50, max_hold_ms: int = 150,
                 long_pause_chance: float = 0.08,
                 long_pause_min: float = 2.0, long_pause_max: float = 5.0,
                 enable_jitter: bool = True):
        self.click_offset_range = click_offset_range
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.min_hold_ms = min_hold_ms
        self.max_hold_ms = max_hold_ms
        self.long_pause_chance = long_pause_chance
        self.long_pause_min = long_pause_min
        self.long_pause_max = long_pause_max
        self.enable_jitter = enable_jitter

        # 내부 상태 - 피로도 시뮬레이션
        self._action_count = 0
        self._session_start = time.time()

        logger.info(
            f"Humanizer 초기화 - 오프셋: ±{click_offset_range}px, "
            f"딜레이: {min_delay}~{max_delay}s"
        )

    def humanize_coords(self, x: int, y: int,
                        region_w: int = 0, region_h: int = 0) -> Tuple[int, int]:
        """
        클릭 좌표에 사람 같은 오프셋 추가

        Args:
            x, y: 원래 좌표
            region_w, region_h: 매칭된 영역 크기 (있으면 영역 내 랜덤)

        Returns:
            랜덤화된 (x, y)
        """
        if region_w > 4 and region_h > 4:
            # 매칭 영역 내에서 가우시안 분포로 랜덤 좌표 생성
            # 중심 부근에 더 많이 클릭하도록 (사람처럼)
            offset_x = int(random.gauss(0, region_w * 0.15))
            offset_y = int(random.gauss(0, region_h * 0.15))
            # 영역을 벗어나지 않도록 클램핑
            offset_x = max(-region_w // 3, min(region_w // 3, offset_x))
            offset_y = max(-region_h // 3, min(region_h // 3, offset_y))
        elif self.enable_jitter:
            # 작은 랜덤 오프셋 (가우시안)
            offset_x = int(random.gauss(0, self.click_offset_range * 0.6))
            offset_y = int(random.gauss(0, self.click_offset_range * 0.6))
            offset_x = max(-self.click_offset_range, min(self.click_offset_range, offset_x))
            offset_y = max(-self.click_offset_range, min(self.click_offset_range, offset_y))
        else:
            offset_x, offset_y = 0, 0

        new_x = max(0, x + offset_x)
        new_y = max(0, y + offset_y)

        if offset_x != 0 or offset_y != 0:
            logger.debug(f"좌표 휴먼화: ({x},{y}) -> ({new_x},{new_y})")

        return new_x, new_y

    def get_click_delay(self) -> float:
        """
        다음 클릭까지의 딜레이 (초)
        사람처럼 불규칙한 간격 생성
        """
        self._action_count += 1

        # 가끔 긴 정지 (딴 짓하는 척)
        if random.random() < self.long_pause_chance:
            delay = random.uniform(self.long_pause_min, self.long_pause_max)
            logger.debug(f"긴 정지 삽입: {delay:.2f}s")
            return delay

        # 기본 딜레이 (로그정규분포 - 사람 반응시간과 유사)
        mu = (self.min_delay + self.max_delay) / 2
        sigma = (self.max_delay - self.min_delay) / 4
        delay = random.lognormvariate(math.log(mu), sigma / mu)

        # 범위 제한
        delay = max(self.min_delay, min(self.max_delay * 1.5, delay))

        # 피로도: 오래 하면 살짝 느려짐
        session_minutes = (time.time() - self._session_start) / 60
        if session_minutes > 30:
            fatigue_factor = 1.0 + (session_minutes - 30) * 0.005
            delay *= min(fatigue_factor, 1.3)

        logger.debug(f"클릭 딜레이: {delay:.3f}s (액션 #{self._action_count})")
        return delay

    def get_hold_duration_ms(self) -> int:
        """
        클릭 홀드 시간 (밀리초)
        너무 정확히 같은 시간 누르지 않도록
        """
        hold = int(random.gauss(
            (self.min_hold_ms + self.max_hold_ms) / 2,
            (self.max_hold_ms - self.min_hold_ms) / 4
        ))
        hold = max(self.min_hold_ms, min(self.max_hold_ms, hold))
        return hold

    def should_micro_pause(self) -> bool:
        """일정 간격마다 마이크로 정지 필요 여부"""
        # 20~40번 클릭마다 약간 쉬기
        if self._action_count > 0 and self._action_count % random.randint(20, 40) == 0:
            return True
        return False

    def get_micro_pause_duration(self) -> float:
        """마이크로 정지 시간"""
        return random.uniform(1.5, 4.0)

    def wait(self):
        """휴먼화된 딜레이로 대기"""
        # 마이크로 정지 체크
        if self.should_micro_pause():
            pause = self.get_micro_pause_duration()
            logger.info(f"마이크로 정지: {pause:.1f}s")
            time.sleep(pause)

        delay = self.get_click_delay()
        time.sleep(delay)

    def reset_session(self):
        """세션 리셋 (피로도 초기화)"""
        self._action_count = 0
        self._session_start = time.time()
        logger.info("세션 리셋")
