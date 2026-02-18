"""
MacroForge - ADB 모바일 게임 매크로 자동화
메인 엔트리포인트
"""

import sys
import os

# 프로젝트 루트를 Path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.logger import setup_logging
from src.utils.config_manager import ConfigManager


def main():
    # 설정 로드
    config = ConfigManager()

    # 로깅 초기화
    setup_logging(
        level=config.get("logging.level", "DEBUG"),
        log_dir=config.get("logging.log_dir", "logs"),
        console_output=config.get("logging.console_output", True),
        file_output=config.get("logging.file_output", True),
        console_level=config.get("logging.console_level", "INFO")
    )

    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("=" * 50)
    logger.info("MacroForge 시작")
    logger.info("=" * 50)

    # assets 폴더 생성
    os.makedirs("assets/templates", exist_ok=True)
    os.makedirs("saved_macros", exist_ok=True)
    os.makedirs("logs", exist_ok=True)

    # PySide6 UI 시작
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("MacroForge")
    app.setFont(QFont("맑은 고딕", 10))

    from src.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    logger.info("UI 준비 완료")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
