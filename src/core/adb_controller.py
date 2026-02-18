"""
ADB Controller - Android 에뮤레이터/디바이스 ADB 연결 및 제어
창이 최소화/가려져 있어도 ADB를 통해 직접 안드로이드에 명령을 보내므로 항상 동작
"""

import subprocess
import os
import time
import re
from pathlib import Path
from typing import Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ADBController:
    """Android 에뮬레이터/디바이스 ADB 연결 관리"""

    # 프로젝트 내 ADB 저장 경로
    LOCAL_ADB_DIR = Path(__file__).parent.parent.parent / "tools" / "platform-tools"
    LOCAL_ADB_PATH = LOCAL_ADB_DIR / "adb.exe"

    # 블루스택 기본 설치 경로들 (fallback 전용)
    BLUESTACKS_PATHS = [
        r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
        r"C:\Program Files\BlueStacks\HD-Adb.exe",
        r"C:\Program Files (x86)\BlueStacks_nxt\HD-Adb.exe",
        r"C:\Program Files (x86)\BlueStacks\HD-Adb.exe",
    ]

    # Android platform-tools 다운로드 URL
    PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

    def __init__(self, adb_path: str = "auto", host: str = "127.0.0.1",
                 port: int = 5555, timeout: int = 10):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.adb_path = self._resolve_adb_path(adb_path)
        self._connected = False
        self._device_serial: Optional[str] = None
        self._screen_size: Optional[Tuple[int, int]] = None
        self._screenshot_size: Optional[Tuple[int, int]] = None  # 실제 스크린샷 해상도
        self._coord_scale: Tuple[float, float] = (1.0, 1.0)  # (sx, sy) 스크린샷→입력 스케일

        logger.info(f"ADB 경로: {self.adb_path}")

    def _resolve_adb_path(self, adb_path: str) -> str:
        """ADB 실행 파일 경로 자동 탐색 (표준 ADB 우선)"""
        if adb_path != "auto" and os.path.isfile(adb_path):
            return adb_path

        # 1순위: 프로젝트 내 다운로드된 표준 ADB
        if self.LOCAL_ADB_PATH.is_file():
            logger.info(f"로컬 표준 ADB 사용: {self.LOCAL_ADB_PATH}")
            return str(self.LOCAL_ADB_PATH)

        # 2순위: 시스템 PATH의 표준 ADB
        try:
            result = subprocess.run(
                ["where", "adb"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    path = line.strip()
                    if path and os.path.isfile(path) and "HD-Adb" not in path:
                        logger.info(f"시스템 표준 ADB 발견: {path}")
                        return path
        except Exception:
            pass

        # 3순위: 자동 다운로드
        logger.info("표준 ADB를 찾을 수 없습니다. 자동 다운로드를 시도합니다...")
        downloaded = self._download_platform_tools()
        if downloaded:
            return downloaded

        # 4순위: 블루스택 내장 ADB (최후 수단 - input 명령 불안정)
        for path in self.BLUESTACKS_PATHS:
            if os.path.isfile(path):
                logger.warning(
                    f"⚠️ 블루스택 HD-Adb 사용 - input 명령이 동작하지 않을 수 있습니다: {path}"
                )
                return path

        logger.warning("ADB를 찾을 수 없습니다. 'adb' 명령어로 시도합니다.")
        return "adb"

    def _download_platform_tools(self) -> Optional[str]:
        """Android platform-tools를 다운로드하여 프로젝트 내에 설치"""
        import zipfile
        import urllib.request

        try:
            self.LOCAL_ADB_DIR.parent.mkdir(parents=True, exist_ok=True)
            zip_path = self.LOCAL_ADB_DIR.parent / "platform-tools.zip"

            logger.info(f"platform-tools 다운로드 중... ({self.PLATFORM_TOOLS_URL})")
            urllib.request.urlretrieve(self.PLATFORM_TOOLS_URL, str(zip_path))
            logger.info("다운로드 완료, 압축 해제 중...")

            with zipfile.ZipFile(str(zip_path), 'r') as zf:
                zf.extractall(str(self.LOCAL_ADB_DIR.parent))

            zip_path.unlink(missing_ok=True)

            if self.LOCAL_ADB_PATH.is_file():
                logger.info(f"✅ 표준 ADB 설치 완료: {self.LOCAL_ADB_PATH}")
                return str(self.LOCAL_ADB_PATH)
            else:
                logger.error("압축 해제 후 adb.exe를 찾을 수 없습니다")
                return None

        except Exception as e:
            logger.error(f"platform-tools 다운로드 실패: {e}")
            return None

    def _run_adb(self, *args: str, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """ADB 명령 실행"""
        cmd = [self.adb_path] + list(args)
        t = timeout or self.timeout
        logger.debug(f"ADB 명령: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=t,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"ADB 명령 타임아웃: {' '.join(cmd)}")
            raise
        except FileNotFoundError:
            logger.error(f"ADB 실행 파일을 찾을 수 없습니다: {self.adb_path}")
            raise

    def _run_adb_device(self, *args: str, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """연결된 디바이스에 ADB 명령 실행"""
        if self._device_serial:
            return self._run_adb("-s", self._device_serial, *args, timeout=timeout)
        return self._run_adb(*args, timeout=timeout)

    def _run_shell(self, shell_cmd: str, timeout: Optional[int] = None, retries: int = 2) -> subprocess.CompletedProcess:
        """
        ADB shell 명령 실행
        실패 시 재연결 후 재시도
        """
        args = shell_cmd.split()

        for attempt in range(retries + 1):
            # shell + 인자 분리 (표준 방식)
            result = self._run_adb_device("shell", *args, timeout=timeout)
            stderr = result.stderr.decode("utf-8", errors="ignore").strip() if result.stderr else ""

            # 성공
            if result.returncode == 0 and "error" not in stderr.lower():
                return result

            # 실패 시 재연결
            if attempt < retries:
                logger.warning(f"ADB 명령 실패 ({stderr}), 재연결 시도 {attempt + 1}/{retries}")
                target = f"{self.host}:{self.port}"
                self._run_adb("disconnect", target)
                time.sleep(0.5)
                self._run_adb("connect", target, timeout=5)
                time.sleep(0.5)
            else:
                logger.error(f"ADB 명령 실패 ({retries}회 재시도 후): {stderr}")

        return result

    def connect(self) -> bool:
        """ADB 디바이스 연결"""
        target = f"{self.host}:{self.port}"
        logger.info(f"ADB 연결 시도: {target}")

        # ADB 서버 시작
        self._run_adb("start-server")
        time.sleep(0.5)

        # 연결
        result = self._run_adb("connect", target, timeout=15)
        output = result.stdout.decode("utf-8", errors="ignore").strip()
        logger.info(f"ADB connect 응답: {output}")

        if "connected" in output.lower():
            self._device_serial = target
            self._connected = True
            self._fetch_screen_size()
            logger.info(f"✅ ADB 연결 성공: {target}")
            return True

        # 이미 연결된 디바이스 확인
        devices = self.list_devices()
        if devices:
            self._device_serial = devices[0]
            self._connected = True
            self._fetch_screen_size()
            logger.info(f"✅ 기존 디바이스 사용: {self._device_serial}")
            return True

        logger.error("❌ ADB 연결 실패")
        self._connected = False
        return False

    def disconnect(self):
        """ADB 연결 해제"""
        if self._device_serial:
            self._run_adb("disconnect", self._device_serial)
        self._connected = False
        self._device_serial = None
        logger.info("ADB 연결 해제")

    def list_devices(self) -> list[str]:
        """연결된 디바이스 목록"""
        result = self._run_adb("devices")
        output = result.stdout.decode("utf-8", errors="ignore")
        devices = []
        for line in output.strip().split("\n")[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        logger.debug(f"연결된 디바이스: {devices}")
        return devices

    def _fetch_screen_size(self):
        """화면 해상도 조회 및 좌표 스케일 계산"""
        try:
            result = self._run_adb_device("shell", "wm", "size")
            output = result.stdout.decode("utf-8", errors="ignore").strip()
            match = re.search(r"(\d+)x(\d+)", output)
            if match:
                w, h = int(match.group(1)), int(match.group(2))
                self._screen_size = (w, h)
                logger.info(f"화면 해상도 (wm size): {w}x{h}")
            else:
                logger.warning(f"wm size 파싱 실패: '{output}'")
        except Exception as e:
            logger.warning(f"해상도 조회 실패: {e}")

        # 실제 스크린샷을 찍어서 해상도 확인 후 스케일 계산
        self._calibrate_coordinates()

    def _calibrate_coordinates(self):
        """스크린샷 해상도와 wm size를 비교하여 좌표 스케일 계산"""
        try:
            from PIL import Image
            import io
            png_bytes = self.screenshot_bytes()
            if png_bytes:
                img = Image.open(io.BytesIO(png_bytes))
                ss_w, ss_h = img.size  # PIL size = (width, height)
                self._screenshot_size = (ss_w, ss_h)
                logger.info(f"스크린샷 해상도: {ss_w}x{ss_h}")

                if self._screen_size:
                    wm_w, wm_h = self._screen_size
                    sx = wm_w / ss_w
                    sy = wm_h / ss_h
                    self._coord_scale = (sx, sy)
                    if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
                        logger.warning(
                            f"⚠️ 좌표 스케일 감지: "
                            f"스크린샷({ss_w}x{ss_h}) ≠ wm size({wm_w}x{wm_h}) "
                            f"→ 스케일 ({sx:.3f}, {sy:.3f})"
                        )
                    else:
                        logger.info("✅ 좌표 스케일: 1:1 (스케일링 불필요)")
        except Exception as e:
            logger.warning(f"좌표 캘리브레이션 실패: {e}")

    def _scale_coords(self, x: int, y: int) -> Tuple[int, int]:
        """스크린샷 좌표를 입력 좌표로 변환"""
        sx, sy = self._coord_scale
        return int(x * sx), int(y * sy)

    @property
    def screenshot_size(self) -> Optional[Tuple[int, int]]:
        return self._screenshot_size

    @property
    def screen_size(self) -> Optional[Tuple[int, int]]:
        return self._screen_size

    @property
    def is_connected(self) -> bool:
        return self._connected

    def screenshot_bytes(self) -> Optional[bytes]:
        """
        ADB를 통해 스크린샷을 PNG 바이트로 가져옴
        창 상태와 무관하게 항상 동작
        """
        if not self._connected:
            logger.error("ADB 미연결 상태에서 스크린샷 시도")
            return None

        try:
            result = self._run_adb_device(
                "exec-out", "screencap", "-p",
                timeout=10
            )
            if result.returncode == 0 and len(result.stdout) > 100:
                logger.debug(f"스크린샷 캡처 ({len(result.stdout)} bytes)")
                return result.stdout
            else:
                logger.error("스크린샷 실패: 데이터 없음")
                return None
        except Exception as e:
            logger.error(f"스크린샷 오류: {e}")
            return None

    def tap(self, x: int, y: int):
        """단순 탭 (좌표 자동 스케일링)"""
        sx, sy = self._scale_coords(x, y)
        self._run_shell(f"input tap {sx} {sy}")
        logger.debug(f"탭: ({x},{y}) → 스케일링({sx},{sy})")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """스와이프 (좌표 자동 스케일링)"""
        sx1, sy1 = self._scale_coords(x1, y1)
        sx2, sy2 = self._scale_coords(x2, y2)
        self._run_shell(f"input swipe {sx1} {sy1} {sx2} {sy2} {duration_ms}")
        logger.debug(f"스와이프: ({x1},{y1})→({x2},{y2}) 스케일링({sx1},{sy1})→({sx2},{sy2}) {duration_ms}ms")

    def long_press(self, x: int, y: int, duration_ms: int = 1000):
        """길게 누르기 (swipe로 구현)"""
        self.swipe(x, y, x, y, duration_ms)
        logger.debug(f"롱프레스: ({x}, {y}) {duration_ms}ms")

    def key_event(self, keycode: int):
        """키 이벤트 전송"""
        self._run_shell(f"input keyevent {keycode}")
        logger.debug(f"키 이벤트: {keycode}")

    def text_input(self, text: str):
        """텍스트 입력"""
        escaped = text.replace(" ", "%s")
        self._run_shell(f"input text {escaped}")
        logger.debug(f"텍스트 입력: {text}")

    def get_current_activity(self) -> Optional[str]:
        """현재 포그라운드 액티비티 확인"""
        try:
            result = self._run_shell("dumpsys activity activities")
            output = result.stdout.decode("utf-8", errors="ignore")
            for line in output.split("\n"):
                if "mResumedActivity" in line or "mFocusedActivity" in line:
                    return line.strip()
            return None
        except Exception:
            return None
