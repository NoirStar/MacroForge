"""
Macro Engine - 매크로 실행 관리 엔진
스레드 기반으로 매크로를 실행/정지/일시정지 관리
"""

import threading
import time
from typing import Optional, Type, List

from src.core.adb_controller import ADBController
from src.core.screen_capture import ScreenCapture
from src.core.image_matcher import ImageMatcher
from src.core.input_simulator import InputSimulator
from src.macros.base_macro import BaseMacro, MacroState
from src.utils.humanizer import Humanizer
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MacroEngine:
    """매크로 실행 엔진"""

    def __init__(self, adb: ADBController, screen: ScreenCapture,
                 matcher: ImageMatcher, input_sim: InputSimulator,
                 humanizer: Humanizer):
        self.adb = adb
        self.screen = screen
        self.matcher = matcher
        self.input_sim = input_sim
        self.humanizer = humanizer

        self._current_macro: Optional[BaseMacro] = None
        self._thread: Optional[threading.Thread] = None
        self._registered_macros: dict[str, Type[BaseMacro]] = {}
        self._queue_stop: bool = False

        # 콜백
        self.on_macro_started = None
        self.on_macro_stopped = None
        self.on_macro_error = None
        self.on_state_changed = None

    def register_macro(self, macro_class: Type[BaseMacro]):
        """매크로 클래스 등록"""
        name = macro_class.name
        self._registered_macros[name] = macro_class
        logger.info(f"매크로 등록: {name}")

    def get_registered_macros(self) -> dict[str, Type[BaseMacro]]:
        """등록된 매크로 목록"""
        return self._registered_macros.copy()

    def create_macro(self, macro_class: Type[BaseMacro]) -> BaseMacro:
        """매크로 인스턴스 생성"""
        macro = macro_class(
            adb=self.adb,
            screen=self.screen,
            matcher=self.matcher,
            input_sim=self.input_sim,
            humanizer=self.humanizer
        )
        macro.set_callbacks(
            on_state_change=self._on_macro_state_change
        )
        return macro

    def start(self, macro_class: Type[BaseMacro]):
        """매크로 시작"""
        if self._current_macro and self._current_macro.state == MacroState.RUNNING:
            logger.warning("이미 실행 중인 매크로가 있습니다.")
            self.stop()
            time.sleep(0.5)

        self._current_macro = self.create_macro(macro_class)
        self.humanizer.reset_session()

        self._thread = threading.Thread(
            target=self._run_macro,
            name=f"Macro-{self._current_macro.name}",
            daemon=True
        )
        self._thread.start()
        logger.info(f"매크로 시작: {self._current_macro.name}")

        if self.on_macro_started:
            self.on_macro_started(self._current_macro)

    def _run_macro(self):
        """매크로 실행 (스레드)"""
        try:
            self._current_macro.run()
        except Exception as e:
            logger.error(f"매크로 실행 오류: {e}")
            if self.on_macro_error:
                self.on_macro_error(e)
        finally:
            if self.on_macro_stopped:
                self.on_macro_stopped(self._current_macro)

    def stop(self):
        """매크로 중지"""
        if self._current_macro and self._current_macro.state in (MacroState.RUNNING, MacroState.PAUSED):
            self._current_macro.stop()
            logger.info(f"매크로 중지 요청: {self._current_macro.name}")

            # 스레드 종료 대기
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)

    def pause(self):
        """매크로 일시정지"""
        if self._current_macro and self._current_macro.state == MacroState.RUNNING:
            self._current_macro.pause()
            logger.info(f"매크로 일시정지: {self._current_macro.name}")

    def resume(self):
        """매크로 재개"""
        if self._current_macro and self._current_macro.state == MacroState.PAUSED:
            self._current_macro.resume()
            logger.info(f"매크로 재개: {self._current_macro.name}")

    def toggle_pause(self):
        """일시정지 토글"""
        if self._current_macro:
            if self._current_macro.state == MacroState.RUNNING:
                self.pause()
            elif self._current_macro.state == MacroState.PAUSED:
                self.resume()

    @property
    def is_running(self) -> bool:
        return (self._current_macro is not None and
                self._current_macro.state in (MacroState.RUNNING, MacroState.PAUSED))

    @property
    def current_macro(self) -> Optional[BaseMacro]:
        return self._current_macro

    @property
    def current_state(self) -> MacroState:
        if self._current_macro:
            return self._current_macro.state
        return MacroState.IDLE

    def start_script(self, script):
        """스크립트 매크로 시작"""
        from src.macros.script_macro import ScriptMacro

        if self._current_macro and self._current_macro.state == MacroState.RUNNING:
            self.stop()
            time.sleep(0.5)

        macro = ScriptMacro(
            script=script,
            adb=self.adb,
            screen=self.screen,
            matcher=self.matcher,
            input_sim=self.input_sim,
            humanizer=self.humanizer,
        )
        macro.set_callbacks(on_state_change=self._on_macro_state_change)
        self._current_macro = macro
        self.humanizer.reset_session()

        self._thread = threading.Thread(
            target=self._run_macro,
            name=f"Script-{script.name}",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"스크립트 매크로 시작: {script.name}")

        if self.on_macro_started:
            self.on_macro_started(macro)

    # ── 큐 실행 ──

    def start_queue(self, queue_items: list, total_repeats: int = 1,
                    on_progress=None, on_queue_done=None):
        """
        매크로 큐 순차 실행

        Args:
            queue_items: [{"name": str, "path": str, "repeats": int}, ...]
            total_repeats: 큐 전체 반복 횟수
            on_progress: 콜백(index, repeat_current, repeat_total)
            on_queue_done: 큐 완료 콜백
        """
        if self.is_running:
            self.stop()
            time.sleep(0.5)

        self._queue_stop = False
        self._thread = threading.Thread(
            target=self._run_queue,
            args=(queue_items, total_repeats, on_progress, on_queue_done),
            name="MacroQueue",
            daemon=True,
        )
        self._thread.start()

    def _run_queue(self, queue_items, total_repeats, on_progress, on_queue_done):
        """큐 실행 스레드"""
        from src.macros.script_macro import ScriptMacro
        from src.macros.macro_step import MacroScript

        logger.info(f"매크로 큐 시작: {len(queue_items)}개 매크로, {total_repeats}회 반복")

        for queue_round in range(total_repeats):
            if self._queue_stop:
                break

            if total_repeats > 1:
                logger.info(f"큐 반복 {queue_round + 1}/{total_repeats}")

            for idx, item in enumerate(queue_items):
                if self._queue_stop:
                    break

                try:
                    script = MacroScript.load(item["path"])
                except Exception as e:
                    logger.error(f"매크로 로드 실패: {item['name']} - {e}")
                    continue

                repeats = item.get("repeats", 1)

                for rep in range(repeats):
                    if self._queue_stop:
                        break

                    if on_progress:
                        on_progress(idx, rep + 1, repeats)

                    logger.info(
                        f"큐 [{idx + 1}/{len(queue_items)}] "
                        f"{script.name} ({rep + 1}/{repeats})"
                    )

                    macro = ScriptMacro(
                        script=script,
                        adb=self.adb,
                        screen=self.screen,
                        matcher=self.matcher,
                        input_sim=self.input_sim,
                        humanizer=self.humanizer,
                    )
                    macro.set_callbacks(on_state_change=self._on_macro_state_change)
                    self._current_macro = macro
                    self.humanizer.reset_session()

                    try:
                        macro.run()
                    except Exception as e:
                        logger.error(f"큐 매크로 실행 오류: {e}")

                    # 매크로 간 짧은 대기
                    if not self._queue_stop:
                        time.sleep(1.0)

        self._current_macro = None
        logger.info("매크로 큐 완료")

        if on_queue_done:
            on_queue_done()

    def stop_queue(self):
        """큐 실행 중지"""
        self._queue_stop = True
        if self._current_macro and self._current_macro.state in (MacroState.RUNNING, MacroState.PAUSED):
            self._current_macro.stop()
        logger.info("매크로 큐 중지 요청")

    def _on_macro_state_change(self, old_state: MacroState, new_state: MacroState):
        """매크로 상태 변경 콜백"""
        if self.on_state_changed:
            self.on_state_changed(old_state, new_state)
