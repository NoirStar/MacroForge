"""
Log Widget - 디버그 로그 표시 위젯
실시간 로그 출력 + 필터 + 검색
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QLineEdit, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QTextCursor, QColor, QFont

import qtawesome as qta

from src.utils.logger import add_ui_log_callback, remove_ui_log_callback


class LogWidget(QWidget):
    """실시간 디버그 로그 패널"""

    log_received = Signal(str)

    # 로그 레벨별 색상
    LEVEL_COLORS = {
        "DEBUG":   "#888888",
        "INFO":    "#D4D4D4",
        "WARNING": "#FFC107",
        "ERROR":   "#FF5252",
        "CRITICAL": "#FF1744",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_lines = 2000
        self._auto_scroll = True
        self._filter_level = "INFO"
        self._search_text = ""

        self._setup_ui()
        self._connect_signals()

        # 로거 콜백 등록
        add_ui_log_callback(self._on_log_message)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── 상단 툴바 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        # 로그 레벨 필터
        level_label = QLabel("레벨:")
        level_label.setStyleSheet("color: #8899AA; font-size: 11px;")
        toolbar.addWidget(level_label)

        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setFixedWidth(100)
        self.level_combo.setCurrentText("INFO")
        toolbar.addWidget(self.level_combo)

        # 검색
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("로그 검색...")
        toolbar.addWidget(self.search_input)

        # 자동 스크롤
        self.auto_scroll_btn = QPushButton(qta.icon('mdi.arrow-collapse-down', color='#fff'), " 자동스크롤")
        self.auto_scroll_btn.setObjectName("ghostBtn")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.setFixedWidth(120)
        self.auto_scroll_btn.setFixedHeight(28)
        toolbar.addWidget(self.auto_scroll_btn)

        # 클리어
        self.clear_btn = QPushButton(qta.icon('mdi.delete-sweep', color='#fff'), " 지우기")
        self.clear_btn.setObjectName("ghostBtn")
        self.clear_btn.setFixedWidth(85)
        self.clear_btn.setFixedHeight(28)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # ── 로그 텍스트 영역 ──
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Cascadia Code", 9) if QFont("Cascadia Code").exactMatch() else QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #12141A;
                color: #B0B8C4;
                border: 1px solid #2A2D35;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.log_text)

    def _connect_signals(self):
        self.log_received.connect(self._append_log)
        self.clear_btn.clicked.connect(self.clear)
        self.auto_scroll_btn.toggled.connect(self._toggle_auto_scroll)
        self.level_combo.currentTextChanged.connect(self._set_filter_level)
        self.search_input.textChanged.connect(self._set_search_text)

    def _on_log_message(self, message: str):
        """로거 콜백 (다른 스레드에서 호출될 수 있음)"""
        self.log_received.emit(message)

    @Slot(str)
    def _append_log(self, message: str):
        """로그 메시지 추가 (UI 스레드)"""
        # 레벨 필터
        if not self._passes_filter(message):
            return

        # 검색 필터
        if self._search_text and self._search_text.lower() not in message.lower():
            return

        # 색상 적용
        color = "#D4D4D4"
        for level, c in self.LEVEL_COLORS.items():
            if f"[{level}" in message:
                color = c
                break

        html = f'<span style="color:{color};">{self._escape_html(message)}</span>'
        self.log_text.append(html)

        # 최대 라인 수 제한
        if self.log_text.document().blockCount() > self._max_lines:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.movePosition(QTextCursor.Down, QTextCursor.KeepAnchor, 100)
            cursor.removeSelectedText()

        # 자동 스크롤
        if self._auto_scroll:
            self.log_text.moveCursor(QTextCursor.End)

    def _passes_filter(self, message: str) -> bool:
        """로그 레벨 필터"""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        try:
            filter_idx = levels.index(self._filter_level)
        except ValueError:
            return True

        for i, level in enumerate(levels):
            if f"[{level}" in message:
                return i >= filter_idx
        return True

    def _escape_html(self, text: str) -> str:
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace(" ", "&nbsp;"))

    @Slot()
    def clear(self):
        self.log_text.clear()

    @Slot(bool)
    def _toggle_auto_scroll(self, checked: bool):
        self._auto_scroll = checked

    @Slot(str)
    def _set_filter_level(self, level: str):
        self._filter_level = level

    @Slot(str)
    def _set_search_text(self, text: str):
        self._search_text = text

    def closeEvent(self, event):
        remove_ui_log_callback(self._on_log_message)
        super().closeEvent(event)
