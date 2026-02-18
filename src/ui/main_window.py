"""
Main Window - MacroForge 메인 UI 윈도우
"""

import time
from typing import Optional, Type

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QPushButton, QLabel,
    QStatusBar, QFrame, QMessageBox, QFileDialog,
    QComboBox, QSpinBox, QLineEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QPointF
from PySide6.QtGui import QFont, QPixmap, QImage, QPainter, QPen, QColor, QBrush

import numpy as np
import qtawesome as qta

from PySide6.QtWidgets import QTabWidget

from src.core.adb_controller import ADBController
from src.core.screen_capture import ScreenCapture
from src.core.image_matcher import ImageMatcher
from src.core.input_simulator import InputSimulator
from src.core.macro_engine import MacroEngine
from src.core.background_worker import BackgroundWorker
from src.macros.base_macro import BaseMacro, MacroState
from src.utils.humanizer import Humanizer
from src.utils.config_manager import ConfigManager
from src.utils.logger import get_logger, setup_logging
from src.ui.log_widget import LogWidget
from src.ui.macro_builder import MacroBuilderWidget
from src.ui.background_panel import BackgroundActionWidget
from src.ui.macro_queue import MacroQueueWidget

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """MacroForge 메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MacroForge")
        self.setWindowIcon(qta.icon('mdi.gamepad-variant', color='#4FC3F7'))
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # ── 설정 로드 ──
        self.config = ConfigManager()

        # ── 코어 초기화 ──
        self.adb = ADBController(
            adb_path=self.config.adb_path,
            host=self.config.adb_host,
            port=self.config.adb_port,
            timeout=self.config.adb_timeout
        )
        self.screen_capture = ScreenCapture(
            self.adb,
            cache_ttl_ms=self.config.screenshot_cache_ttl
        )
        self.matcher = ImageMatcher(
            confidence_threshold=self.config.confidence_threshold,
            method=self.config.match_method,
            use_grayscale=self.config.use_grayscale
        )
        self.humanizer = Humanizer(
            click_offset_range=self.config.get("humanizer.click_offset_range", 5),
            min_delay=self.config.get("humanizer.min_delay", 0.3),
            max_delay=self.config.get("humanizer.max_delay", 1.2),
            min_hold_ms=self.config.get("humanizer.min_hold_ms", 50),
            max_hold_ms=self.config.get("humanizer.max_hold_ms", 150),
            long_pause_chance=self.config.get("humanizer.long_pause_chance", 0.08),
            long_pause_min=self.config.get("humanizer.long_pause_min", 2.0),
            long_pause_max=self.config.get("humanizer.long_pause_max", 5.0),
            enable_jitter=self.config.get("humanizer.enable_jitter", True)
        )
        self.input_sim = InputSimulator(self.adb, self.humanizer)
        self.engine = MacroEngine(
            self.adb, self.screen_capture, self.matcher,
            self.input_sim, self.humanizer
        )

        # 백그라운드 워커
        self.bg_worker = BackgroundWorker(
            self.adb, self.screen_capture, self.matcher,
            self.input_sim, self.humanizer
        )
        self.bg_worker.on_started = self._on_bg_started
        self.bg_worker.on_stopped = self._on_bg_stopped

        # 엔진 콜백
        self.engine.on_state_changed = self._on_engine_state_changed
        self._queue_running = False

        # ── UI 구성 ──
        self._setup_ui()
        self._apply_dark_theme()
        self._fix_combo_popups()
        self._register_macros()

        # ── 상태 업데이트 타이머 ──
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_status)
        self._status_timer.start(1000)

        # ── 화면 미리보기 타이머 ──
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_rgb = None  # numpy 데이터 참조 유지

        # 클릭 시각화
        self._click_markers = []  # [(x, y, timestamp), ...]
        self._click_marker_duration = 2.0  # 마커 표시 시간 (초)
        self.input_sim.on_click = self._on_input_click

        logger.info("MacroForge 초기화 완료")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(8)

        # ── 상단: 연결 + 제어 통합 바 ──
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(16, 10, 16, 10)
        top_bar_layout.setSpacing(12)

        # 에뮬레이터 선택
        self.emu_combo = QComboBox()
        self.emu_combo.setFixedHeight(34)
        self.emu_combo.setFixedWidth(145)
        self.emu_combo.addItem(qta.icon('mdi.cellphone-link', color='#64B5F6'), "BlueStacks", 5555)
        self.emu_combo.addItem(qta.icon('mdi.cellphone-link', color='#81C784'), "LDPlayer", 5555)
        self.emu_combo.addItem(qta.icon('mdi.cellphone-link', color='#FFB74D'), "Nox Player", 62001)
        self.emu_combo.addItem(qta.icon('mdi.cellphone-link', color='#CE93D8'), "MuMu Player", 7555)
        self.emu_combo.addItem(qta.icon('mdi.usb', color='#4FC3F7'), "USB 디바이스", 0)
        self.emu_combo.addItem(qta.icon('mdi.cog', color='#888'), "직접 입력", -1)
        self.emu_combo.currentIndexChanged.connect(self._on_emu_changed)
        top_bar_layout.addWidget(self.emu_combo)

        # 포트 입력 (직접 입력 모드용)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("포트 번호")
        self.port_input.setFixedHeight(34)
        self.port_input.setFixedWidth(90)
        self.port_input.setVisible(False)
        top_bar_layout.addWidget(self.port_input)

        # ADB 연결
        self.connect_btn = QPushButton(qta.icon('mdi.lan-connect', color='#fff'), " 연결")
        self.connect_btn.setObjectName("connectBtn")
        self.connect_btn.setFixedHeight(34)
        self.connect_btn.setFixedWidth(110)
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.clicked.connect(self._on_connect)
        top_bar_layout.addWidget(self.connect_btn)

        self.conn_status_label = QLabel("● 미연결")
        self.conn_status_label.setObjectName("connStatus")
        top_bar_layout.addWidget(self.conn_status_label)

        self.device_label = QLabel("")
        self.device_label.setStyleSheet("color: #666; font-size: 11px; background: transparent;")
        top_bar_layout.addWidget(self.device_label)

        # 구분선
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet("color: #3C3C3C;")
        top_bar_layout.addWidget(sep1)

        # 매크로 제어
        self.start_btn = QPushButton(qta.icon('mdi.play', color='#fff'), " 시작")
        self.start_btn.setObjectName("successBtn")
        self.start_btn.setFixedHeight(34)
        self.start_btn.setFixedWidth(90)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setEnabled(False)
        top_bar_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton(qta.icon('mdi.pause', color='#fff'), " 일시정지")
        self.pause_btn.setObjectName("warningBtn")
        self.pause_btn.setFixedHeight(34)
        self.pause_btn.setFixedWidth(105)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(self._on_pause)
        self.pause_btn.setEnabled(False)
        top_bar_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton(qta.icon('mdi.stop', color='#fff'), " 정지")
        self.stop_btn.setObjectName("dangerBtn")
        self.stop_btn.setFixedHeight(34)
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        top_bar_layout.addWidget(self.stop_btn)

        # 구분선
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setStyleSheet("color: #3C3C3C;")
        top_bar_layout.addWidget(sep2)

        # 상태 / 실행 정보
        self.state_label = QLabel("● 대기")
        self.state_label.setObjectName("stateLabel")
        top_bar_layout.addWidget(self.state_label)

        top_bar_layout.addStretch()

        self.loop_label = QLabel("루프: 0")
        self.loop_label.setObjectName("infoLabel")
        top_bar_layout.addWidget(self.loop_label)

        self.time_label = QLabel("시간: 0s")
        self.time_label.setObjectName("infoLabel")
        top_bar_layout.addWidget(self.time_label)

        main_layout.addWidget(top_bar)

        # ── 중앙: 좌측(매크로+미리보기) / 우측(로그) ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # 좌측 패널
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(6)

        # 탭 위젯: 매크로 빌더 + 백그라운드 액션
        self.left_tabs = QTabWidget()
        self.left_tabs.setObjectName("mainTabs")

        # 탭 1: 매크로 빌더
        self.macro_builder = MacroBuilderWidget(
            screen_capture=self.screen_capture,
            builtin_macros={},
        )
        self.left_tabs.addTab(self.macro_builder, qta.icon('mdi.robot', color='#4FC3F7'), "매크로 빌더")

        # 탭 2: 백그라운드 액션
        self.bg_panel = BackgroundActionWidget(
            screen_capture=self.screen_capture,
        )
        self.bg_panel.start_requested.connect(self._on_bg_start)
        self.bg_panel.stop_requested.connect(self._on_bg_stop)
        self.left_tabs.addTab(self.bg_panel, qta.icon('mdi.sync', color='#81C784'), "백그라운드 액션")

        # 탭 3: 매크로 큐
        self.macro_queue = MacroQueueWidget()
        self.macro_queue.queue_start_requested.connect(self._on_queue_start)
        self.macro_queue.queue_stop_requested.connect(self._on_queue_stop)
        self.left_tabs.addTab(self.macro_queue, qta.icon('mdi.playlist-play', color='#FFB74D'), "매크로 큐")

        left_layout.addWidget(self.left_tabs, 3)

        # 화면 미리보기
        preview_frame = QFrame()
        preview_frame.setObjectName("previewFrame")
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(10, 8, 10, 8)
        preview_layout.setSpacing(6)

        preview_header = QLabel("화면 미리보기")
        preview_header.setObjectName("sectionHeader")
        preview_layout.addWidget(preview_header)

        self.preview_label = QLabel("ADB 연결 후 미리보기 가능")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(180)
        self.preview_label.setObjectName("previewArea")
        preview_layout.addWidget(self.preview_label)

        preview_btn_layout = QHBoxLayout()
        preview_btn_layout.setSpacing(6)
        self.preview_toggle_btn = QPushButton(qta.icon('mdi.monitor-eye', color='#fff'), " 미리보기 시작")
        self.preview_toggle_btn.setObjectName("ghostBtn")
        self.preview_toggle_btn.setFixedHeight(30)
        self.preview_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.preview_toggle_btn.setCheckable(True)
        self.preview_toggle_btn.toggled.connect(self._toggle_preview)
        self.preview_toggle_btn.setEnabled(False)
        preview_btn_layout.addWidget(self.preview_toggle_btn)

        self.screenshot_btn = QPushButton(qta.icon('mdi.camera', color='#fff'), " 스크린샷 저장")
        self.screenshot_btn.setObjectName("ghostBtn")
        self.screenshot_btn.setFixedHeight(30)
        self.screenshot_btn.setCursor(Qt.PointingHandCursor)
        self.screenshot_btn.clicked.connect(self._save_screenshot)
        self.screenshot_btn.setEnabled(False)
        preview_btn_layout.addWidget(self.screenshot_btn)

        preview_layout.addLayout(preview_btn_layout)
        left_layout.addWidget(preview_frame, 1)

        splitter.addWidget(left_panel)

        # 우측: 로그 패널
        self.log_widget = LogWidget()
        splitter.addWidget(self.log_widget)

        # 좌측(매크로)에 더 많은 공간
        splitter.setSizes([720, 280])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

        # ── 상태바 ──
        self.statusBar().showMessage("MacroForge 준비 완료")

    def _apply_dark_theme(self):
        """모던 다크 테마 적용"""
        self.setStyleSheet("""
            /* ── 기본 ── */
            QMainWindow, QWidget {
                background-color: #181A20;
                color: #E0E0E0;
                font-family: "Segoe UI", "맑은 고딕", sans-serif;
                font-size: 12px;
            }

            /* ── 상단 바 ── */
            QFrame#topBar {
                background-color: #1E2028;
                border: 1px solid #2A2D35;
                border-radius: 8px;
            }
            QFrame#topBar QLabel {
                background: transparent;
            }
            QFrame#topBar QFrame {
                background: transparent;
            }

            /* ── 상태 라벨 ── */
            QLabel#connStatus {
                font-weight: bold;
                font-size: 12px;
                color: #FF6B6B;
            }
            QLabel#stateLabel {
                font-weight: bold;
                font-size: 13px;
                color: #666;
            }
            QLabel#infoLabel {
                color: #4FC3F7;
                font-size: 11px;
                padding: 0 4px;
            }
            QLabel#sectionHeader {
                color: #8899AA;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
                padding: 2px 0;
                background: transparent;
            }

            /* ── 미리보기 영역 ── */
            QFrame#previewFrame {
                background-color: #1E2028;
                border: 1px solid #2A2D35;
                border-radius: 8px;
            }
            QFrame#previewFrame QLabel,
            QFrame#previewFrame QFrame {
                background: transparent;
            }
            QLabel#previewArea {
                background-color: #12141A;
                border: 1px solid #2A2D35;
                border-radius: 6px;
                color: #555;
            }

            /* ── 버튼: 기본 (프라이머리) ── */
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3B82F6;
            }
            QPushButton:pressed {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #2A2D35;
                color: #555;
            }

            /* 연결 버튼 */
            QPushButton#connectBtn {
                background-color: #2563EB;
            }
            QPushButton#connectBtn:hover {
                background-color: #3B82F6;
            }

            /* 성공 (시작) 버튼 */
            QPushButton#successBtn {
                background-color: #16A34A;
            }
            QPushButton#successBtn:hover {
                background-color: #22C55E;
            }
            QPushButton#successBtn:pressed {
                background-color: #15803D;
            }
            QPushButton#successBtn:disabled {
                background-color: #2A2D35;
                color: #555;
            }

            /* 경고 (일시정지) 버튼 */
            QPushButton#warningBtn {
                background-color: #D97706;
            }
            QPushButton#warningBtn:hover {
                background-color: #F59E0B;
            }
            QPushButton#warningBtn:pressed {
                background-color: #B45309;
            }
            QPushButton#warningBtn:disabled {
                background-color: #2A2D35;
                color: #555;
            }

            /* 위험 (정지/삭제) 버튼 */
            QPushButton#dangerBtn {
                background-color: #DC2626;
            }
            QPushButton#dangerBtn:hover {
                background-color: #EF4444;
            }
            QPushButton#dangerBtn:pressed {
                background-color: #B91C1C;
            }
            QPushButton#dangerBtn:disabled {
                background-color: #2A2D35;
                color: #555;
            }

            /* 고스트 버튼 (배경 투명) */
            QPushButton#ghostBtn {
                background-color: #2A2D35;
                color: #B0B8C4;
                border: 1px solid #363A45;
            }
            QPushButton#ghostBtn:hover {
                background-color: #363A45;
                color: #E0E0E0;
            }
            QPushButton#ghostBtn:checked {
                background-color: #16A34A;
                color: #FFFFFF;
                border: 1px solid #22C55E;
            }

            /* ── 입력 위젯 ── */
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #252830;
                color: #E0E0E0;
                border: 1px solid #363A45;
                border-radius: 6px;
                padding: 5px 8px;
                selection-background-color: #2563EB;
            }
            QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1px solid #2563EB;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #252830;
                color: #E0E0E0;
                border: 1px solid #363A45;
                selection-background-color: #2563EB;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                padding: 4px 8px;
                min-height: 22px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #2563EB;
                color: #FFFFFF;
            }

            /* ── 그룹박스 ── */
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #8899AA;
                border: 1px solid #2A2D35;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 18px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }

            /* ── 탭 위젯 ── */
            QTabWidget#mainTabs::pane {
                border: 1px solid #2A2D35;
                border-radius: 0 0 8px 8px;
                background-color: #181A20;
            }
            QTabBar::tab {
                background: #1E2028;
                color: #8899AA;
                padding: 8px 20px;
                border: 1px solid #2A2D35;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #181A20;
                color: #E0E0E0;
                border-bottom: 2px solid #2563EB;
            }
            QTabBar::tab:hover:!selected {
                background: #252830;
                color: #B0B8C4;
            }

            /* ── 리스트 위젯 ── */
            QListWidget {
                background-color: #1E2028;
                color: #E0E0E0;
                border: 1px solid #2A2D35;
                border-radius: 6px;
                outline: none;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 5px 8px;
                border-radius: 4px;
                margin: 1px 2px;
            }
            QListWidget::item:selected {
                background-color: #2563EB;
                color: #FFFFFF;
            }
            QListWidget::item:hover:!selected {
                background-color: #252830;
            }

            /* ── 스크롤바 ── */
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #363A45;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4A4E5A;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 8px;
            }
            QScrollBar::handle:horizontal {
                background: #363A45;
                border-radius: 4px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4A4E5A;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }

            /* ── 스플리터 ── */
            QSplitter::handle {
                background-color: #2A2D35;
                width: 1px;
            }

            /* ── 상태바 ── */
            QStatusBar {
                background-color: #1E2028;
                color: #8899AA;
                border-top: 1px solid #2A2D35;
                font-size: 11px;
                padding: 2px 8px;
            }

            /* ── 스크롤 영역 ── */
            QScrollArea {
                border: none;
                background-color: transparent;
            }

            /* ── 체크박스 ── */
            QCheckBox {
                color: #E0E0E0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 4px;
                border: 1px solid #363A45;
                background-color: #252830;
            }
            QCheckBox::indicator:checked {
                background-color: #2563EB;
                border: 1px solid #3B82F6;
            }

            /* ── 폼 라벨 ── */
            QFormLayout QLabel {
                color: #8899AA;
                font-size: 11px;
            }

            /* ── 다이얼로그 ── */
            QMessageBox, QDialog, QInputDialog {
                background-color: #1E2028;
            }
            QMessageBox QLabel, QDialog QLabel {
                color: #E0E0E0;
            }

            /* ── 툴팁 ── */
            QToolTip {
                background-color: #252830;
                color: #E0E0E0;
                border: 1px solid #363A45;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
        """)

    def _fix_combo_popups(self):
        """Windows에서 QComboBox 팝업 투명 문제 해결
        
        Qt가 콤보박스 팝업을 top-level 윈도우로 만들 때
        WA_TranslucentBackground가 적용되어 투명해지는 문제를
        팝업 컨테이너에 직접 배경색을 지정하여 해결
        """
        for combo in self.findChildren(QComboBox):
            view = combo.view()
            if view:
                container = view.parentWidget()
                if container:
                    container.setStyleSheet(
                        "background-color: #252830;"
                        "border: 1px solid #363A45;"
                        "border-radius: 4px;"
                    )
                view.setStyleSheet(
                    "QAbstractItemView {"
                    "  background-color: #252830;"
                    "  color: #E0E0E0;"
                    "  border: none;"
                    "  outline: none;"
                    "  selection-background-color: #2563EB;"
                    "}"
                    "QAbstractItemView::item {"
                    "  padding: 4px 8px;"
                    "  min-height: 22px;"
                    "}"
                    "QAbstractItemView::item:hover {"
                    "  background-color: #2563EB;"
                    "  color: #FFFFFF;"
                    "}"
                )

    def _register_macros(self):
        """매크로 등록"""
        logger.info("매크로 등록 완료")

    # ── 이벤트 핸들러 ──

    @Slot(int)
    def _on_emu_changed(self, index: int):
        """에뮬레이터 선택 변경 시 포트 자동 설정"""
        port = self.emu_combo.currentData()
        if port == -1:  # 직접 입력
            self.port_input.setVisible(True)
        elif port == 0:  # USB 디바이스
            self.port_input.setVisible(False)
        else:
            self.port_input.setVisible(False)
            self.adb.port = port

    @Slot()
    def _on_connect(self):
        """ADB 연결/해제"""
        if self.adb.is_connected:
            self.adb.disconnect()
            self._update_connection_ui(False)
        else:
            # 에뮬레이터 설정 반영
            port = self.emu_combo.currentData()
            if port == -1:  # 직접 입력
                try:
                    self.adb.port = int(self.port_input.text().strip())
                except ValueError:
                    QMessageBox.warning(self, "오류", "올바른 포트 번호를 입력하세요.")
                    self.connect_btn.setEnabled(True)
                    return
            elif port == 0:  # USB 디바이스
                pass  # USB는 포트 불필요
            else:
                self.adb.port = port

            self.statusBar().showMessage("ADB 연결 중...")
            self.connect_btn.setEnabled(False)

            success = self.adb.connect()
            self._update_connection_ui(success)
            self.connect_btn.setEnabled(True)

            if not success:
                self._show_connection_guide()

    def _show_connection_guide(self):
        """ADB 연결 실패 시 상세 가이드 표시"""
        guide = QMessageBox(self)
        guide.setIcon(QMessageBox.Warning)
        guide.setWindowTitle("ADB 연결 실패")
        guide.setText(
            "<b>ADB 연결에 실패했습니다.</b><br><br>"
            "아래 설정을 확인해주세요:"
        )
        guide.setInformativeText(
            "<b>▶ 블루스택 (BlueStacks)</b><br>"
            "&nbsp;&nbsp;1. 설정 → 고급 → <b>Android 디버그 브리지(ADB) 활성화</b><br>"
            "&nbsp;&nbsp;2. 기본 포트: <b>5555</b><br><br>"
            "<b>▶ LDPlayer (라드플레이어)</b><br>"
            "&nbsp;&nbsp;1. 설정 → 기타 → <b>ADB 디버그 열기</b><br>"
            "&nbsp;&nbsp;2. 기본 포트: <b>5555</b> (또는 5556+)<br><br>"
            "<b>▶ Nox Player (녹스)</b><br>"
            "&nbsp;&nbsp;1. 설정 → 일반 → <b>ROOT 켜기</b> (ADB 자동 활성)<br>"
            "&nbsp;&nbsp;2. 기본 포트: <b>62001</b><br><br>"
            "<b>▶ MuMu Player (뮤뮤)</b><br>"
            "&nbsp;&nbsp;1. 설정 → 기타 → <b>ADB 연결 열기</b><br>"
            "&nbsp;&nbsp;2. 기본 포트: <b>7555</b><br><br>"
            "<b>▶ 실제 안드로이드 디바이스</b><br>"
            "&nbsp;&nbsp;1. 개발자 옵션 → <b>USB 디버깅</b> 활성<br>"
            "&nbsp;&nbsp;2. USB 케이블로 연결 후 자동 감지<br><br>"
            "※ <b>config.yaml</b>의 <code>adb.port</code> 값이 에뮤레이터 설정과 일치하는지 확인하세요."
        )
        guide.setStandardButtons(QMessageBox.Ok)
        guide.exec()

    def _update_connection_ui(self, connected: bool):
        """연결 상태 UI 업데이트"""
        if connected:
            self.connect_btn.setIcon(qta.icon('mdi.lan-disconnect', color='#FF5252'))
            self.connect_btn.setText(" 연결해제")
            self.conn_status_label.setText("● 연결됨")
            self.conn_status_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 12px;")
            self.device_label.setText(f"({self.adb._device_serial})")
            self.start_btn.setEnabled(True)
            self.preview_toggle_btn.setEnabled(True)
            self.screenshot_btn.setEnabled(True)
            self.statusBar().showMessage("ADB 연결 성공")

            size = self.adb.screen_size
            if size:
                self.statusBar().showMessage(f"ADB 연결 성공 - 해상도: {size[0]}x{size[1]}")
        else:
            self.connect_btn.setIcon(qta.icon('mdi.lan-connect', color='#4FC3F7'))
            self.connect_btn.setText(" 연결")
            self.conn_status_label.setText("● 미연결")
            self.conn_status_label.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 12px;")
            self.device_label.setText("")
            self.start_btn.setEnabled(False)
            self.preview_toggle_btn.setEnabled(False)
            self.screenshot_btn.setEnabled(False)
            self._preview_timer.stop()

    @Slot()
    def _on_start(self):
        """매크로 시작"""
        if not self.macro_builder.is_ready():
            QMessageBox.information(self, "알림", "실행할 매크로를 선택하거나 스텝을 추가하세요.")
            return

        self.macro_builder.auto_save_before_run()
        rtype, data = self.macro_builder.get_run_info()

        if rtype == "builtin":
            self.engine.start(data)
        elif rtype == "script":
            self.engine.start_script(data)
        else:
            return

        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.state_label.setText("● 실행 중")
        self.state_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 13px;")

    @Slot()
    def _on_pause(self):
        """일시정지 토글"""
        self.engine.toggle_pause()
        if self.engine.current_state == MacroState.PAUSED:
            self.pause_btn.setIcon(qta.icon('mdi.play', color='#4CAF50'))
            self.pause_btn.setText(" 재개")
            self.state_label.setText("● 일시정지")
            self.state_label.setStyleSheet("color: #F59E0B; font-weight: bold; font-size: 13px;")
        else:
            self.pause_btn.setIcon(qta.icon('mdi.pause', color='#fff'))
            self.pause_btn.setText(" 일시정지")
            self.state_label.setText("● 실행 중")
            self.state_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 13px;")

    @Slot()
    def _on_stop(self):
        """매크로 정지"""
        if self._queue_running:
            self._on_queue_stop()
            return
        if self.engine.is_running:
            self.engine.stop()
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setIcon(qta.icon('mdi.pause', color='#FFC107'))
        self.pause_btn.setText(" 일시정지")
        self.stop_btn.setEnabled(False)
        self.state_label.setText("● 대기")
        self.state_label.setStyleSheet("color: #666; font-weight: bold; font-size: 13px;")

    def _on_engine_state_changed(self, old_state, new_state):
        """엔진 상태 변경 시"""
        if new_state in (MacroState.STOPPED, MacroState.ERROR):
            # 큐 실행 중에는 개별 매크로 종료로 UI 리셋하지 않음
            if self._queue_running:
                return
            # UI 스레드에서 안전하게 처리하기 위해 타이머 사용
            QTimer.singleShot(0, self._on_stop)

    @Slot()
    def _update_status(self):
        """상태바 정보 업데이트"""
        macro = self.engine.current_macro
        if macro and macro.state in (MacroState.RUNNING, MacroState.PAUSED):
            self.loop_label.setText(f"루프: {macro.loop_count}")
            elapsed = macro.elapsed_time
            if elapsed > 3600:
                time_str = f"{elapsed/3600:.1f}h"
            elif elapsed > 60:
                time_str = f"{elapsed/60:.1f}m"
            else:
                time_str = f"{elapsed:.0f}s"
            self.time_label.setText(f"시간: {time_str}")

    @Slot(bool)
    def _toggle_preview(self, checked: bool):
        """화면 미리보기 토글"""
        if checked:
            self.preview_toggle_btn.setText(" 미리보기 중지")
            self._preview_timer.start(500)  # 0.5초 간격
        else:
            self.preview_toggle_btn.setText(" 미리보기 시작")
            self._preview_timer.stop()

    @Slot()
    def _update_preview(self):
        """화면 미리보기 업데이트"""
        if not self.adb.is_connected:
            return

        rgb = self.screen_capture.capture_rgb(force=True)
        if rgb is None:
            return

        # numpy 데이터가 QImage 사용 중 GC되지 않도록 참조 유지
        self._preview_rgb = rgb.copy()
        h, w, ch = self._preview_rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(self._preview_rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        # 클릭 마커 그리기
        now = time.time()
        self._click_markers = [
            m for m in self._click_markers
            if now - m[2] < self._click_marker_duration
        ]
        if self._click_markers:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            for mx, my, ts in self._click_markers:
                age = now - ts
                alpha = max(0, int(255 * (1.0 - age / self._click_marker_duration)))

                # 외곽 원 (빨간)
                pen = QPen(QColor(255, 80, 80, alpha), 2)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(255, 80, 80, alpha // 3)))
                radius = int(12 + age * 8)  # 시간이 지나면 커지는 원
                painter.drawEllipse(QPointF(mx, my), radius, radius)

                # 중심점
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(QColor(255, 255, 0, alpha)))
                painter.drawEllipse(QPointF(mx, my), 3, 3)
            painter.end()

        # 미리보기 영역에 맞게 스케일
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled)

    def _on_input_click(self, x: int, y: int):
        """InputSimulator에서 클릭 발생 시 미리보기에 마커 추가"""
        self._click_markers.append((x, y, time.time()))

    @Slot()
    def _save_screenshot(self):
        """스크린샷 저장"""
        if not self.adb.is_connected:
            return

        import cv2
        screen = self.screen_capture.capture(force=True)
        if screen is None:
            QMessageBox.warning(self, "오류", "스크린샷을 캡처할 수 없습니다.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "스크린샷 저장", "screenshot.png",
            "이미지 (*.png *.jpg *.bmp)"
        )
        if path:
            cv2.imwrite(path, screen)
            logger.info(f"스크린샷 저장: {path}")
            self.statusBar().showMessage(f"스크린샷 저장됨: {path}")

    # ── 매크로 큐 제어 ──

    @Slot(list)
    def _on_queue_start(self, queue_items: list):
        """매크로 큐 실행"""
        if not self.adb.is_connected:
            QMessageBox.warning(self, "알림", "ADB가 연결되어 있지 않습니다.")
            return

        self._queue_running = True
        self.macro_queue.set_running(True, 0)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.state_label.setText("● 큐 실행 중")
        self.state_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 13px;")

        total = self.macro_queue.total_repeats

        def on_progress(index, rep_cur, rep_total):
            QTimer.singleShot(0, lambda i=index, rc=rep_cur, rt=rep_total:
                              self.macro_queue.update_progress(i, rc, rt))

        def on_done():
            QTimer.singleShot(0, self._on_queue_done)

        self.engine.start_queue(queue_items, total, on_progress, on_done)

    @Slot()
    def _on_queue_stop(self):
        """매크로 큐 정지"""
        self.engine.stop_queue()
        self._on_queue_done()

    def _on_queue_done(self):
        """매크로 큐 완료 처리"""
        self._queue_running = False
        self.macro_queue.set_running(False)
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setIcon(qta.icon('mdi.pause', color='#FFC107'))
        self.pause_btn.setText(" 일시정지")
        self.stop_btn.setEnabled(False)
        self.state_label.setText("● 대기")
        self.state_label.setStyleSheet("color: #666; font-weight: bold; font-size: 13px;")

    # ── 백그라운드 워커 제어 ──

    @Slot()
    def _on_bg_start(self):
        """백그라운드 액션 시작"""
        if not self.adb.is_connected:
            QMessageBox.warning(self, "알림", "ADB가 연결되어 있지 않습니다.")
            return

        actions = self.bg_panel.get_actions()
        self.bg_worker.set_actions(actions)
        self.bg_worker.start()

    @Slot()
    def _on_bg_stop(self):
        """백그라운드 액션 정지"""
        self.bg_worker.stop()

    def _on_bg_started(self):
        """백그라운드 워커 시작 콜백 (워커 스레드에서 호출)"""
        QTimer.singleShot(0, lambda: self.bg_panel.set_running(True))

    def _on_bg_stopped(self):
        """백그라운드 워커 정지 콜백 (워커 스레드에서 호출)"""
        QTimer.singleShot(0, lambda: self.bg_panel.set_running(False))

    def closeEvent(self, event):
        """종료 시 정리"""
        if self.bg_worker.is_running:
            self.bg_worker.stop()
        if self.engine.is_running:
            self.engine.stop()
        self.engine.stop_queue()
        if self.adb.is_connected:
            self.adb.disconnect()
        self._preview_timer.stop()
        self._status_timer.stop()
        event.accept()
