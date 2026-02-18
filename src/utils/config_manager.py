"""
Config Manager - YAML 설정 파일 관리
"""

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils.logger import get_logger

logger = get_logger(__name__)

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class ConfigManager:
    """YAML 설정 파일 관리자"""

    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config: dict = {}
        self.load()

    def load(self):
        """설정 파일 로드"""
        if not self.config_path.is_file():
            logger.warning(f"설정 파일 없음: {self.config_path}")
            self._config = {}
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"설정 로드 완료: {self.config_path}")
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            self._config = {}

    def save(self):
        """설정 파일 저장"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"설정 저장 완료: {self.config_path}")
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점(.) 구분 키로 설정값 조회

        Args:
            key_path: "adb.host", "humanizer.min_delay" 등
            default: 기본값

        Returns:
            설정값 또는 기본값
        """
        keys = key_path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key_path: str, value: Any):
        """
        점(.) 구분 키로 설정값 변경

        Args:
            key_path: "adb.host" 등
            value: 설정할 값
        """
        keys = key_path.split(".")
        config = self._config
        for key in keys[:-1]:
            if key not in config or not isinstance(config[key], dict):
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    @property
    def raw(self) -> dict:
        """원시 설정 딕셔너리"""
        return self._config

    # ── 편의 프로퍼티 ──

    @property
    def adb_path(self) -> str:
        return self.get("adb.adb_path", "auto")

    @property
    def adb_host(self) -> str:
        return self.get("adb.host", "127.0.0.1")

    @property
    def adb_port(self) -> int:
        return self.get("adb.port", 7555)

    @property
    def adb_timeout(self) -> int:
        return self.get("adb.timeout", 10)

    @property
    def confidence_threshold(self) -> float:
        return self.get("image_matching.confidence_threshold", 0.85)

    @property
    def match_method(self) -> str:
        return self.get("image_matching.method", "TM_CCOEFF_NORMED")

    @property
    def use_grayscale(self) -> bool:
        return self.get("image_matching.use_grayscale", True)

    @property
    def screenshot_cache_ttl(self) -> int:
        return self.get("screenshot.cache_ttl_ms", 100)
