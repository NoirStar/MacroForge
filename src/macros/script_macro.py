"""
스크립트 매크로 실행기 - MacroScript의 스텝들을 순차 실행
"""

import time

from src.macros.base_macro import BaseMacro, MacroState
from src.macros.macro_step import MacroScript, MacroStep, StepType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScriptMacro(BaseMacro):
    """스텝 기반 스크립트 매크로 실행기"""

    name = "스크립트"
    description = ""

    def __init__(self, script: MacroScript, adb, screen, matcher, input_sim, humanizer):
        super().__init__(adb, screen, matcher, input_sim, humanizer)
        self.script = script
        self.name = script.name
        self.description = script.description
        self._step_idx = 0
        self._retry_count = 0

    def setup(self):
        self._step_idx = 0
        self._retry_count = 0
        if not self.script.steps:
            raise ValueError("스텝이 없습니다")
        logger.info(f"스크립트 시작: {self.name} ({len(self.script.steps)}스텝)")

    def loop(self):
        if self._step_idx >= len(self.script.steps):
            self._step_idx = 0
            self._retry_count = 0
            logger.info("처음부터 반복")
            return

        step = self.script.steps[self._step_idx]
        logger.info(
            f"[{self._step_idx + 1}/{len(self.script.steps)}] {step.name}"
        )

        success = self._exec(step)
        self._flow(step, success)

    def _exec(self, step: MacroStep) -> bool:
        t = step.type

        if t == StepType.CLICK_IMAGE:
            match = self.find(step.template_path, step.threshold)
            if match:
                self.input_sim.click_match_and_wait(match)
                return True
            return False

        elif t == StepType.CLICK_COORD:
            self.input_sim.click_and_wait(step.x, step.y)
            return True

        elif t == StepType.WAIT:
            time.sleep(step.wait_time)
            return True

        elif t == StepType.WAIT_FOR_IMAGE:
            match = self.wait_for(step.template_path, timeout=step.timeout, interval=0.5)
            return match is not None

        elif t == StepType.IF_IMAGE:
            return self.is_visible(step.template_path, step.threshold)

        elif t == StepType.SWIPE:
            self.input_sim.swipe(step.x, step.y, step.x2, step.y2, step.duration_ms)
            self.humanizer.wait()
            return True

        return True

    def _flow(self, step: MacroStep, success: bool):
        action = step.on_success if success else step.on_fail

        if success:
            self._retry_count = 0

        if action == "next":
            self._step_idx += 1
            self._retry_count = 0

        elif action == "stop":
            logger.info("매크로 정지 (스텝 설정)")
            self.stop()

        elif action == "retry":
            self._retry_count += 1
            if self._retry_count >= step.max_retries:
                logger.warning(f"재시도 한도 초과 ({step.max_retries}회), 다음으로")
                self._step_idx += 1
                self._retry_count = 0
            else:
                # 재시도 로그는 1, 5, 10회 이후 50회 단위로만 출력
                if self._retry_count in (1, 5, 10) or self._retry_count % 50 == 0:
                    logger.info(f"재시도 {self._retry_count}/{step.max_retries}")
                time.sleep(step.retry_delay)

        elif action == "loop":
            self._step_idx = 0
            self._retry_count = 0
            logger.info("루프 → 처음으로")

        elif action.startswith("goto:"):
            try:
                target = int(action.split(":")[1])
                self._step_idx = target
                self._retry_count = 0
                logger.info(f"↪ {target + 1}번 스텝으로 이동")
            except (ValueError, IndexError):
                self._step_idx += 1

        else:
            self._step_idx += 1

    def teardown(self):
        logger.info(f"스크립트 종료: {self.name}")
