"""
Image Matcher - OpenCV 기반 템플릿 매칭
"""

import os
from typing import Optional, Tuple, List, NamedTuple
from pathlib import Path

import cv2
import numpy as np

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MatchResult(NamedTuple):
    """이미지 매칭 결과"""
    x: int          # 매칭 중심 x
    y: int          # 매칭 중심 y
    width: int      # 템플릿 너비
    height: int     # 템플릿 높이
    confidence: float  # 매칭 신뢰도 (0~1)
    top_left: Tuple[int, int]  # 좌상단 좌표


class ImageMatcher:
    """OpenCV 템플릿 매칭 엔진"""

    METHODS = {
        "TM_CCOEFF_NORMED": cv2.TM_CCOEFF_NORMED,
        "TM_CCORR_NORMED": cv2.TM_CCORR_NORMED,
        "TM_SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
    }

    def __init__(self, confidence_threshold: float = 0.85,
                 method: str = "TM_CCOEFF_NORMED",
                 use_grayscale: bool = True,
                 multi_scale: bool = True):
        self.confidence_threshold = confidence_threshold
        self.method = self.METHODS.get(method, cv2.TM_CCOEFF_NORMED)
        self.method_name = method
        self.use_grayscale = use_grayscale
        self.multi_scale = multi_scale
        self._is_sqdiff = "SQDIFF" in method

        # 템플릿 이미지 캐시
        self._template_cache: dict[str, np.ndarray] = {}

        # 멀티스케일 범위 (0.5배 ~ 2.0배)
        self._scale_factors = [1.0, 0.9, 1.1, 0.8, 1.2, 0.7, 1.3, 0.6, 1.5, 0.5, 2.0]

        logger.info(
            f"ImageMatcher 초기화 - 방법: {method}, "
            f"임계값: {confidence_threshold}, 그레이스케일: {use_grayscale}"
        )

    def load_template(self, template_path: str) -> Optional[np.ndarray]:
        """템플릿 이미지 로드 (캐싱)"""
        if template_path in self._template_cache:
            return self._template_cache[template_path]

        if not os.path.isfile(template_path):
            logger.error(f"템플릿 파일 없음: {template_path}")
            return None

        template = cv2.imread(template_path)
        if template is None:
            logger.error(f"템플릿 로드 실패: {template_path}")
            return None

        self._template_cache[template_path] = template
        logger.debug(f"템플릿 로드: {template_path} ({template.shape})")
        return template

    def clear_cache(self):
        """템플릿 캐시 초기화"""
        self._template_cache.clear()
        logger.debug("템플릿 캐시 초기화")

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """이미지 전처리"""
        if self.use_grayscale and len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def find(self, screen: np.ndarray, template_path: str,
             threshold: Optional[float] = None) -> Optional[MatchResult]:
        """
        화면에서 템플릿 이미지 찾기

        Args:
            screen: 화면 캡처 (BGR numpy 배열)
            template_path: 템플릿 이미지 경로
            threshold: 매칭 임계값 (None이면 기본값 사용)

        Returns:
            MatchResult 또는 None
        """
        threshold = threshold or self.confidence_threshold
        template = self.load_template(template_path)
        if template is None:
            return None

        # 전처리
        screen_proc = self._preprocess(screen)
        template_proc = self._preprocess(template)

        # 크기 체크
        th, tw = template_proc.shape[:2]
        sh, sw = screen_proc.shape[:2]
        if th > sh or tw > sw:
            logger.warning(f"템플릿({tw}x{th})이 화면({sw}x{sh})보다 큼")
            return None

        # 템플릿 매칭
        result = cv2.matchTemplate(screen_proc, template_proc, self.method)

        if self._is_sqdiff:
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            confidence = 1.0 - min_val
            loc = min_loc
        else:
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            confidence = max_val
            loc = max_loc

        if confidence >= threshold:
            center_x = loc[0] + tw // 2
            center_y = loc[1] + th // 2
            match = MatchResult(
                x=center_x, y=center_y,
                width=tw, height=th,
                confidence=confidence,
                top_left=loc
            )
            logger.info(
                f"✅ 매칭 발견: {os.path.basename(template_path)} "
                f"@ ({center_x}, {center_y}) 신뢰도: {confidence:.3f}"
            )
            return match

        # 매칭 실패 시 멀티스케일 매칭 시도
        if self.multi_scale and confidence < threshold:
            ms_result = self._find_multi_scale(
                screen_proc, template_proc, template_path, threshold
            )
            if ms_result:
                return ms_result

        logger.debug(
            f"❌ 매칭 실패: {os.path.basename(template_path)} "
            f"최고 신뢰도: {confidence:.3f} < {threshold}"
        )
        return None

    def _find_multi_scale(
        self, screen_proc: np.ndarray, template_proc: np.ndarray,
        template_path: str, threshold: float
    ) -> Optional[MatchResult]:
        """다양한 스케일로 템플릿을 리사이즈하여 매칭 시도"""
        th, tw = template_proc.shape[:2]
        sh, sw = screen_proc.shape[:2]
        best_match = None
        best_conf = 0.0

        for scale in self._scale_factors:
            if scale == 1.0:
                continue  # 이미 시도함

            new_w = int(tw * scale)
            new_h = int(th * scale)

            if new_w < 10 or new_h < 10 or new_w > sw or new_h > sh:
                continue

            resized = cv2.resize(template_proc, (new_w, new_h), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(screen_proc, resized, self.method)

            if self._is_sqdiff:
                min_val, _, min_loc, _ = cv2.minMaxLoc(result)
                conf = 1.0 - min_val
                loc = min_loc
            else:
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                conf = max_val
                loc = max_loc

            if conf > best_conf:
                best_conf = conf
                if conf >= threshold:
                    best_match = MatchResult(
                        x=loc[0] + new_w // 2,
                        y=loc[1] + new_h // 2,
                        width=new_w, height=new_h,
                        confidence=conf,
                        top_left=loc
                    )

        if best_match:
            logger.info(
                f"✅ 멀티스케일 매칭: {os.path.basename(template_path)} "
                f"@ ({best_match.x}, {best_match.y}) 신뢰도: {best_match.confidence:.3f}"
            )
        return best_match

    def find_all(self, screen: np.ndarray, template_path: str,
                 threshold: Optional[float] = None,
                 max_results: int = 20) -> List[MatchResult]:
        """
        화면에서 템플릿의 모든 매칭 위치 찾기

        Args:
            screen: 화면 캡처
            template_path: 템플릿 경로
            threshold: 매칭 임계값
            max_results: 최대 결과 수

        Returns:
            MatchResult 리스트
        """
        threshold = threshold or self.confidence_threshold
        template = self.load_template(template_path)
        if template is None:
            return []

        screen_proc = self._preprocess(screen)
        template_proc = self._preprocess(template)

        th, tw = template_proc.shape[:2]
        sh, sw = screen_proc.shape[:2]
        if th > sh or tw > sw:
            return []

        result = cv2.matchTemplate(screen_proc, template_proc, self.method)

        results = []
        if self._is_sqdiff:
            locations = np.where(result <= (1.0 - threshold))
        else:
            locations = np.where(result >= threshold)

        points = list(zip(*locations[::-1]))  # (x, y) 형태로

        # NMS (Non-Maximum Suppression) - 중복 제거
        if not points:
            return []

        # 신뢰도순 정렬
        scored = []
        for pt in points:
            val = result[pt[1], pt[0]]
            conf = (1.0 - val) if self._is_sqdiff else val
            scored.append((pt, conf))
        scored.sort(key=lambda x: x[1], reverse=True)

        # 겹침 필터링
        filtered = []
        for pt, conf in scored:
            if len(filtered) >= max_results:
                break
            is_duplicate = False
            for existing in filtered:
                dx = abs(pt[0] - existing.top_left[0])
                dy = abs(pt[1] - existing.top_left[1])
                if dx < tw * 0.5 and dy < th * 0.5:
                    is_duplicate = True
                    break
            if not is_duplicate:
                filtered.append(MatchResult(
                    x=pt[0] + tw // 2,
                    y=pt[1] + th // 2,
                    width=tw, height=th,
                    confidence=conf,
                    top_left=pt
                ))

        logger.info(f"다중 매칭: {os.path.basename(template_path)} - {len(filtered)}개 발견")
        return filtered

    def find_from_array(self, screen: np.ndarray, template: np.ndarray,
                        threshold: Optional[float] = None) -> Optional[MatchResult]:
        """
        numpy 배열 템플릿으로 직접 매칭 (파일 없이)
        """
        threshold = threshold or self.confidence_threshold
        screen_proc = self._preprocess(screen)
        template_proc = self._preprocess(template)

        th, tw = template_proc.shape[:2]
        result = cv2.matchTemplate(screen_proc, template_proc, self.method)

        if self._is_sqdiff:
            min_val, _, min_loc, _ = cv2.minMaxLoc(result)
            confidence = 1.0 - min_val
            loc = min_loc
        else:
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            confidence = max_val
            loc = max_loc

        if confidence >= threshold:
            return MatchResult(
                x=loc[0] + tw // 2,
                y=loc[1] + th // 2,
                width=tw, height=th,
                confidence=confidence,
                top_left=loc
            )
        return None
