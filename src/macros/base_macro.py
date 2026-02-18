"""
Base Macro - 매크로 기본 클래스
모든 커스텀 매크로는 이 클래스를 상속
"""

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from src.core.adb_controller import ADBController
from src.core.screen_capture import ScreenCapture
from src.core.image_matcher import ImageMatcher, MatchResult
from src.core.input_simulator import InputSimulator
from src.utils.humanizer import Humanizer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MacroState(Enum):
    """매크로 상태"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class BaseMacro(ABC):
    """
    매크로 기본 클래스

    사용법:
        class MyMacro(BaseMacro):
            name = "내 매크로"
            description = "설명"

            def setup(self):
                # 초기화 로직
                pass

            def loop(self):
                # 매 루프마다 실행될 로직
                screen = self.capture()
                match = self.find("button.png")
                if match:
                    self.click_match(match)
    """

    name: str = "기본 매크로"
    description: str = ""

    def __init__(self, adb: ADBController, screen: ScreenCapture,
                 matcher: ImageMatcher, input_sim: InputSimulator,
                 humanizer: Humanizer):
        self.adb = adb
        self.screen = screen
        self.matcher = matcher
        self.input_sim = input_sim
        self.humanizer = humanizer

        self._state = MacroState.IDLE
        self._loop_count = 0
        self._start_time: Optional[float] = None

        # 콜백
        self._on_state_change = None
        self._on_log = None

    @property
    def state(self) -> MacroState:
        return self._state

    @state.setter
    def state(self, value: MacroState):
        old = self._state
        if old == value:
            return
        self._state = value
        if self._on_state_change:
            self._on_state_change(old, value)
        logger.info(f"[{self.name}] 상태 변경: {old.value} -> {value.value}")

    @property
    def loop_count(self) -> int:
        return self._loop_count

    @property
    def elapsed_time(self) -> float:
        """실행 경과 시간 (초)"""
        if self._start_time:
            return time.time() - self._start_time
        return 0

    def set_callbacks(self, on_state_change=None, on_log=None):
        """UI 콜백 설정"""
        self._on_state_change = on_state_change
        self._on_log = on_log

    # ── 편의 메서드 (자식 클래스에서 사용) ──

    def capture(self, force: bool = False):
        """화면 캡처"""
        return self.screen.capture(force)

    def find(self, template_path: str, threshold: float = None) -> Optional[MatchResult]:
        """화면에서 이미지 찾기"""
        screen = self.capture()
        if screen is None:
            return None
        return self.matcher.find(screen, template_path, threshold)

    def find_and_click(self, template_path: str, threshold: float = None,
                       wait: bool = True) -> bool:
        """이미지 찾아서 클릭 (성공 여부 반환)"""
        match = self.find(template_path, threshold)
        if match:
            if wait:
                self.input_sim.click_match_and_wait(match)
            else:
                self.input_sim.click_match(match)
            return True
        return False

    def click(self, x: int, y: int, wait: bool = True):
        """좌표 클릭"""
        if wait:
            self.input_sim.click_and_wait(x, y)
        else:
            self.input_sim.click(x, y)

    def wait(self, seconds: float = None):
        """대기 (None이면 휴먼라이크 딜레이)"""
        if seconds is not None:
            time.sleep(seconds)
        else:
            self.humanizer.wait()

    def wait_for(self, template_path: str, timeout: float = 30,
                 interval: float = 0.5) -> Optional[MatchResult]:
        """이미지가 나타날 때까지 대기"""
        start = time.time()
        while time.time() - start < timeout:
            if self._state != MacroState.RUNNING:
                return None
            match = self.find(template_path)
            if match:
                return match
            time.sleep(interval)
        logger.warning(f"wait_for 타임아웃: {template_path} ({timeout}s)")
        return None

    def is_visible(self, template_path: str, threshold: float = None) -> bool:
        """이미지가 화면에 보이는지 확인"""
        return self.find(template_path, threshold) is not None

    # ── 매크로 라이프사이클 ──

    @abstractmethod
    def setup(self):
        """매크로 시작 전 초기화 (한 번 호출)"""
        pass

    @abstractmethod
    def loop(self):
        """매크로 메인 루프 (반복 호출)"""
        pass

    def teardown(self):
        """매크로 종료 시 정리 (선택적)"""
        pass

    def on_error(self, error: Exception):
        """에러 발생 시 처리 (선택적)"""
        logger.error(f"[{self.name}] 에러: {error}")

    def run(self):
        """매크로 실행 (MacroEngine에서 호출)"""
        self.state = MacroState.RUNNING
        self._start_time = time.time()
        self._loop_count = 0

        try:
            logger.info(f"[{self.name}] 매크로 시작")
            self.setup()

            while self._state == MacroState.RUNNING:
                self._loop_count += 1
                if self._loop_count <= 3 or self._loop_count % 50 == 0:
                    logger.debug(f"[{self.name}] 루프 #{self._loop_count}")

                try:
                    self.loop()
                except Exception as e:
                    self.on_error(e)
                    if self._state == MacroState.RUNNING:
                        # 에러 후에도 계속 실행
                        time.sleep(1)

                # 일시정지 대기
                while self._state == MacroState.PAUSED:
                    time.sleep(0.1)

        except Exception as e:
            logger.error(f"[{self.name}] 치명적 에러: {e}")
            self.state = MacroState.ERROR
        finally:
            try:
                self.teardown()
            except Exception:
                pass
            if self._state != MacroState.ERROR:
                self.state = MacroState.STOPPED
            logger.info(
                f"[{self.name}] 매크로 종료 - "
                f"루프: {self._loop_count}, "
                f"시간: {self.elapsed_time:.1f}s"
            )

    def pause(self):
        """일시정지"""
        if self._state == MacroState.RUNNING:
            self.state = MacroState.PAUSED

    def resume(self):
        """재개"""
        if self._state == MacroState.PAUSED:
            self.state = MacroState.RUNNING

    def stop(self):
        """중지"""
        self.state = MacroState.STOPPED
