"""
Input Simulator - ADB 기반 사람같은 입력 처리
Humanizer와 ADB를 결합하여 자연스러운 입력 수행
"""

from typing import Optional, Tuple

from src.core.adb_controller import ADBController
from src.core.image_matcher import MatchResult
from src.utils.humanizer import Humanizer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InputSimulator:
    """휴먼라이크 입력 시뮬레이터"""

    def __init__(self, adb: ADBController, humanizer: Humanizer):
        self.adb = adb
        self.humanizer = humanizer

    def click(self, x: int, y: int, humanize: bool = True):
        """
        단일 클릭 (휴먼라이크)

        Args:
            x, y: 클릭 좌표
            humanize: 좌표 랜덤화 활성화
        """
        if humanize:
            x, y = self.humanizer.humanize_coords(x, y)

        hold_ms = self.humanizer.get_hold_duration_ms()

        if hold_ms > 80:
            # 살짝 길게 누르는 느낌으로 swipe 사용
            self.adb.swipe(x, y, x, y, hold_ms)
        else:
            self.adb.tap(x, y)

        logger.info(f"클릭: ({x}, {y}) 홀드: {hold_ms}ms")

    def click_match(self, match: MatchResult, humanize: bool = True):
        """
        매칭 결과 위치 클릭

        Args:
            match: ImageMatcher의 매칭 결과
            humanize: 좌표 랜덤화
        """
        if humanize:
            x, y = self.humanizer.humanize_coords(
                match.x, match.y,
                match.width, match.height
            )
        else:
            x, y = match.x, match.y

        hold_ms = self.humanizer.get_hold_duration_ms()

        if hold_ms > 80:
            self.adb.swipe(x, y, x, y, hold_ms)
        else:
            self.adb.tap(x, y)

        logger.info(
            f"매칭 클릭: ({x}, {y}) "
            f"신뢰도: {match.confidence:.3f} 홀드: {hold_ms}ms"
        )

    def click_and_wait(self, x: int, y: int, humanize: bool = True):
        """클릭 후 휴먼라이크 딜레이"""
        self.click(x, y, humanize)
        self.humanizer.wait()

    def click_match_and_wait(self, match: MatchResult, humanize: bool = True):
        """매칭 클릭 후 휴먼라이크 딜레이"""
        self.click_match(match, humanize)
        self.humanizer.wait()

    def swipe(self, x1: int, y1: int, x2: int, y2: int,
              duration_ms: int = 300, humanize: bool = True):
        """휴먼라이크 스와이프"""
        if humanize:
            x1, y1 = self.humanizer.humanize_coords(x1, y1)
            x2, y2 = self.humanizer.humanize_coords(x2, y2)
            # 스와이프 시간도 약간 변동
            import random
            duration_ms = int(duration_ms * random.uniform(0.85, 1.15))

        self.adb.swipe(x1, y1, x2, y2, duration_ms)
        logger.info(f"스와이프: ({x1},{y1}) -> ({x2},{y2}) {duration_ms}ms")

    def long_press(self, x: int, y: int, duration_ms: int = 1000,
                   humanize: bool = True):
        """휴먼라이크 롱프레스"""
        if humanize:
            x, y = self.humanizer.humanize_coords(x, y)
            import random
            duration_ms = int(duration_ms * random.uniform(0.9, 1.1))

        self.adb.long_press(x, y, duration_ms)
        logger.info(f"롱프레스: ({x}, {y}) {duration_ms}ms")
