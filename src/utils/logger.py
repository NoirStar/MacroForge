"""
Logger - 로깅 설정 모듈
파일 + 콘솔 + UI 로그 위젯 출력 지원
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, List
from logging.handlers import RotatingFileHandler

# 루트 로거 설정 여부
_initialized = False

# UI 로그 콜백 핸들러
_ui_callbacks: List[Callable[[str], None]] = []


class UILogHandler(logging.Handler):
    """UI 로그 위젯으로 로그 전달하는 핸들러"""

    def emit(self, record):
        try:
            msg = self.format(record)
            for callback in _ui_callbacks:
                callback(msg)
        except Exception:
            pass


def add_ui_log_callback(callback: Callable[[str], None]):
    """UI 로그 콜백 등록"""
    if callback not in _ui_callbacks:
        _ui_callbacks.append(callback)


def remove_ui_log_callback(callback: Callable[[str], None]):
    """UI 로그 콜백 제거"""
    if callback in _ui_callbacks:
        _ui_callbacks.remove(callback)


def setup_logging(level: str = "DEBUG", log_dir: str = "logs",
                  console_output: bool = True, file_output: bool = True,
                  console_level: str = "INFO"):
    """
    전역 로깅 설정

    Args:
        level: 파일 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        log_dir: 로그 파일 디렉토리
        console_output: 콘솔 출력 여부
        file_output: 파일 출력 여부
        console_level: 콘솔 로그 레벨 (기본 INFO)
    """
    global _initialized
    if _initialized:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.DEBUG))

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)-25s] %(message)s",
        datefmt="%H:%M:%S"
    )

    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔 핸들러 (기본 INFO 이상만 출력)
    if console_output:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(getattr(logging, console_level.upper(), logging.INFO))
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    # 파일 핸들러
    if file_output:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_path / f"macroforge_{today}.log"

        file_handler = RotatingFileHandler(
            str(log_file), maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # UI 핸들러 (시간 + 레벨만 표시)
    ui_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S"
    )
    ui_handler = UILogHandler()
    ui_handler.setLevel(logging.DEBUG)
    ui_handler.setFormatter(ui_formatter)
    root_logger.addHandler(ui_handler)

    # PIL / Pillow 내부 디버그 로그 억제
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)

    _initialized = True
    root_logger.info("=== MacroForge 로깅 시스템 초기화 ===")


def get_logger(name: str) -> logging.Logger:
    """모듈별 로거 획득"""
    return logging.getLogger(name)
