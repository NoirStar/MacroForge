"""
Sample Macro - 예시 매크로
이 파일을 참고하여 새로운 매크로를 만들 수 있습니다
"""

import os
from pathlib import Path

from src.macros.base_macro import BaseMacro
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 템플릿 이미지 경로
TEMPLATES = Path(__file__).parent.parent.parent / "assets" / "templates"


class SampleMacro(BaseMacro):
    """
    예시 매크로 - 구조 참고용

    assets/templates/ 폴더에 템플릿 이미지를 넣고 사용
    예: start_button.png, ok_button.png 등
    """

    name = "샘플 매크로"
    description = "예시 매크로 - 이미지를 찾아 클릭하는 기본 패턴"

    def setup(self):
        """매크로 시작 전 초기화"""
        logger.info("샘플 매크로 초기화")
        # 여기에 초기 설정 로직 추가
        # 예: 특정 화면으로 이동, 변수 초기화 등

    def loop(self):
        """
        매 루프마다 실행되는 메인 로직

        아래는 전형적인 게임 매크로 패턴 예시입니다.
        실제 사용 시 게임에 맞게 수정하세요.
        """

        # ── 패턴 1: 이미지 찾아서 클릭 ──
        # start_btn = str(TEMPLATES / "start_button.png")
        # if self.find_and_click(start_btn):
        #     logger.info("시작 버튼 클릭!")
        #     self.wait(2)  # 2초 대기
        #     return

        # ── 패턴 2: 이미지 나타날 때까지 대기 후 클릭 ──
        # ok_btn = str(TEMPLATES / "ok_button.png")
        # match = self.wait_for(ok_btn, timeout=10)
        # if match:
        #     self.input_sim.click_match_and_wait(match)

        # ── 패턴 3: 여러 이미지 중 하나 찾기 ──
        # templates = {
        #     "battle": str(TEMPLATES / "battle_button.png"),
        #     "reward": str(TEMPLATES / "reward_popup.png"),
        #     "retry":  str(TEMPLATES / "retry_button.png"),
        # }
        # for name, path in templates.items():
        #     if os.path.isfile(path):
        #         match = self.find(path)
        #         if match:
        #             logger.info(f"{name} 발견! 클릭")
        #             self.input_sim.click_match_and_wait(match)
        #             break

        # ── 패턴 4: 조건부 로직 ──
        # if self.is_visible(str(TEMPLATES / "loading.png")):
        #     logger.info("로딩 중... 대기")
        #     self.wait(3)
        #     return

        # ── 데모: 기본 대기 ──
        logger.info(f"샘플 매크로 루프 #{self.loop_count}")
        self.wait(1)

    def teardown(self):
        """매크로 종료 시 정리"""
        logger.info("샘플 매크로 종료")
