"""
Background Worker - 메인 매크로 루프와 독립적으로 동작하는 백그라운드 액션 실행기
별도 스레드에서 활성화된 액션들을 주기적으로 실행
"""

import threading
import time
import random
from typing import List, Optional

from src.core.adb_controller import ADBController
from src.core.screen_capture import ScreenCapture
from src.core.image_matcher import ImageMatcher
from src.core.input_simulator import InputSimulator
from src.utils.humanizer import Humanizer
from src.macros.background_action import BackgroundAction, ActionType, BackgroundActionSet
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BackgroundWorker:
    """
    백그라운드 액션 워커 스레드
    매크로 엔진과 독립적으로 동작하며 활성화된 액션을 주기적으로 실행
    """

    def __init__(self, adb: ADBController, screen: ScreenCapture,
                 matcher: ImageMatcher, input_sim: InputSimulator,
                 humanizer: Humanizer):
        self.adb = adb
        self.screen = screen
        self.matcher = matcher
        self.input_sim = input_sim
        self.humanizer = humanizer

        self._action_set: BackgroundActionSet = BackgroundActionSet()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()

        # 액션별 마지막 실행 시각
        self._last_exec: dict[int, float] = {}

        # 콜백
        self.on_started = None
        self.on_stopped = None
        self.on_action_executed = None  # (action_index, action_name)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def action_set(self) -> BackgroundActionSet:
        return self._action_set

    @action_set.setter
    def action_set(self, value: BackgroundActionSet):
        with self._lock:
            self._action_set = value
            self._last_exec.clear()

    def set_actions(self, actions: List[BackgroundAction]):
        """액션 리스트 갱신 (실행 중에도 가능)"""
        with self._lock:
            self._action_set.actions = actions
            # 기존 타이밍 유지, 새 액션은 초기화
            new_last = {}
            for i in range(len(actions)):
                new_last[i] = self._last_exec.get(i, 0.0)
            self._last_exec = new_last

    def start(self):
        """백그라운드 워커 시작"""
        if self._running:
            logger.warning("백그라운드 워커가 이미 실행 중입니다.")
            return

        if not self.adb.is_connected:
            logger.error("ADB 미연결 - 백그라운드 워커를 시작할 수 없습니다.")
            return

        enabled_count = sum(1 for a in self._action_set.actions if a.enabled)
        if enabled_count == 0:
            logger.warning("활성화된 백그라운드 액션이 없습니다.")
            return

        self._running = True
        self._paused = False
        self._last_exec.clear()

        self._thread = threading.Thread(
            target=self._worker_loop,
            name="BackgroundWorker",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"🔄 백그라운드 워커 시작 (활성 액션: {enabled_count}개)")

        if self.on_started:
            self.on_started()

    def stop(self):
        """백그라운드 워커 정지"""
        if not self._running:
            return

        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        logger.info("⏹️ 백그라운드 워커 정지")

        if self.on_stopped:
            self.on_stopped()

    def pause(self):
        """일시 정지"""
        self._paused = True
        logger.info("⏸️ 백그라운드 워커 일시정지")

    def resume(self):
        """재개"""
        self._paused = False
        logger.info("▶️ 백그라운드 워커 재개")

    def toggle_pause(self):
        if self._paused:
            self.resume()
        else:
            self.pause()

    def _worker_loop(self):
        """워커 메인 루프"""
        logger.info("백그라운드 워커 루프 시작")

        while self._running:
            if self._paused:
                time.sleep(0.2)
                continue

            now = time.time()

            with self._lock:
                actions_snapshot = list(enumerate(self._action_set.actions))

            for idx, action in actions_snapshot:
                if not self._running:
                    break
                if not action.enabled:
                    continue

                # 간격 체크
                last = self._last_exec.get(idx, 0.0)
                jitter = random.uniform(-action.interval_jitter, action.interval_jitter)
                next_time = last + action.interval + jitter

                if now >= next_time:
                    try:
                        self._execute_action(idx, action)
                        self._last_exec[idx] = time.time()
                    except Exception as e:
                        logger.error(f"백그라운드 액션 오류 [{action.name}]: {e}")

            # 짧은 슬립으로 CPU 과부하 방지
            time.sleep(0.1)

        logger.info("백그라운드 워커 루프 종료")

    def _execute_action(self, index: int, action: BackgroundAction):
        """개별 액션 실행"""

        if action.type == ActionType.KEY_PRESS:
            self._exec_key_press(action)

        elif action.type == ActionType.TAP_COORD:
            self._exec_tap_coord(action)

        elif action.type == ActionType.IMAGE_KEY:
            self._exec_image_key(action)

        elif action.type == ActionType.IMAGE_TAP:
            self._exec_image_tap(action)

        if self.on_action_executed:
            self.on_action_executed(index, action.name)

    def _exec_key_press(self, action: BackgroundAction):
        """주기적 키 입력"""
        self.adb.key_event(action.keycode)
        logger.debug(f"🔄 [BG] 키 입력: {action.keycode_label} (키코드 {action.keycode})")

    def _exec_tap_coord(self, action: BackgroundAction):
        """주기적 좌표 탭"""
        self.input_sim.click(action.x, action.y, humanize=True)
        logger.debug(f"🔄 [BG] 좌표 탭: ({action.x}, {action.y})")

    def _exec_image_key(self, action: BackgroundAction):
        """이미지 감지 시 키 입력"""
        if not action.template_path:
            return

        screen = self.screen.capture()
        if screen is None:
            return

        match = self.matcher.find(screen, action.template_path, action.threshold)
        if match:
            self.adb.key_event(action.keycode)
            logger.debug(
                f"🔄 [BG] 이미지 감지→키 입력: {action.keycode_label} "
                f"(신뢰도 {match.confidence:.3f})"
            )

    def _exec_image_tap(self, action: BackgroundAction):
        """이미지 감지 시 해당 위치 탭"""
        if not action.template_path:
            return

        screen = self.screen.capture()
        if screen is None:
            return

        match = self.matcher.find(screen, action.template_path, action.threshold)
        if match:
            self.input_sim.click_match(match, humanize=True)
            logger.debug(
                f"🔄 [BG] 이미지 감지→탭: ({match.x}, {match.y}) "
                f"(신뢰도 {match.confidence:.3f})"
            )
