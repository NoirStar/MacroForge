"""
Screen Capture - ADB 기반 스크린샷 캡처 및 캐싱
"""

import time
import io
from typing import Optional

import numpy as np
from PIL import Image

from src.core.adb_controller import ADBController
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScreenCapture:
    """ADB를 통한 화면 캡처 (캐싱 지원)"""

    def __init__(self, adb: ADBController, cache_ttl_ms: int = 100):
        self.adb = adb
        self.cache_ttl_ms = cache_ttl_ms
        self._last_capture: Optional[np.ndarray] = None
        self._last_capture_time: float = 0

    def capture(self, force: bool = False) -> Optional[np.ndarray]:
        """
        화면 캡처 후 numpy 배열(BGR)로 반환
        캐시 TTL 내이면 이전 캡처 재사용
        """
        now = time.time() * 1000  # ms

        if not force and self._last_capture is not None:
            elapsed = now - self._last_capture_time
            if elapsed < self.cache_ttl_ms:
                logger.debug(f"캐시된 스크린샷 사용 ({elapsed:.0f}ms)")
                return self._last_capture

        png_bytes = self.adb.screenshot_bytes()
        if png_bytes is None:
            return self._last_capture  # 실패 시 마지막 캡처 반환

        try:
            image = Image.open(io.BytesIO(png_bytes))
            # PIL(RGB) -> numpy(BGR) for OpenCV
            frame = np.array(image)
            if frame.shape[2] == 4:  # RGBA -> BGR
                frame = frame[:, :, :3]
            frame = frame[:, :, ::-1]  # RGB -> BGR

            self._last_capture = frame
            self._last_capture_time = now
            logger.debug(f"스크린샷 캡처 완료: {frame.shape}")
            return frame

        except Exception as e:
            logger.error(f"스크린샷 디코딩 오류: {e}")
            return self._last_capture

    def capture_rgb(self, force: bool = False) -> Optional[np.ndarray]:
        """RGB 포맷으로 캡처 (UI 표시용)"""
        bgr = self.capture(force)
        if bgr is not None:
            return bgr[:, :, ::-1]
        return None

    def invalidate_cache(self):
        """캐시 무효화"""
        self._last_capture = None
        self._last_capture_time = 0
