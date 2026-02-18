"""
Macro Editor Widget - 매크로 선택/설정 패널
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton,
    QLabel, QTextEdit, QSpinBox, QDoubleSpinBox,
    QFormLayout, QFrame
)
from PySide6.QtCore import Qt, Signal

import qtawesome as qta


class MacroEditorWidget(QWidget):
    """매크로 선택 및 설정 위젯"""

    macro_selected = Signal(str)  # 매크로 이름

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── 매크로 목록 ──
        list_group = QGroupBox("매크로 목록")
        list_layout = QVBoxLayout(list_group)

        self.macro_list = QListWidget()
        self.macro_list.setStyleSheet("""
            QListWidget {
                background-color: #252526;
                color: #D4D4D4;
                border: 1px solid #333;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background-color: #094771;
            }
            QListWidget::item:hover {
                background-color: #2A2D2E;
            }
        """)
        list_layout.addWidget(self.macro_list)

        layout.addWidget(list_group)

        # ── 매크로 정보 ──
        info_group = QGroupBox("매크로 정보")
        info_layout = QVBoxLayout(info_group)

        self.info_label = QLabel("매크로를 선택하세요")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #CCCCCC; padding: 8px;")
        info_layout.addWidget(self.info_label)

        layout.addWidget(info_group)

        # ── 매크로 설정 ──
        settings_group = QGroupBox("실행 설정")
        settings_layout = QFormLayout(settings_group)

        # 반복 횟수 (0 = 무한)
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(0, 99999)
        self.repeat_spin.setValue(0)
        self.repeat_spin.setSpecialValueText("무한 반복")
        settings_layout.addRow("반복 횟수:", self.repeat_spin)

        # 루프 간 추가 딜레이
        self.loop_delay_spin = QDoubleSpinBox()
        self.loop_delay_spin.setRange(0, 60)
        self.loop_delay_spin.setValue(0)
        self.loop_delay_spin.setSuffix(" 초")
        self.loop_delay_spin.setSingleStep(0.1)
        settings_layout.addRow("루프 딜레이:", self.loop_delay_spin)

        layout.addWidget(settings_group)

        # ── 시그널 연결 ──
        self.macro_list.currentItemChanged.connect(self._on_macro_selected)

    def add_macro(self, name: str, description: str = ""):
        """매크로 목록에 추가"""
        item = QListWidgetItem(name)
        item.setIcon(qta.icon('mdi.robot', color='#4FC3F7'))
        item.setData(Qt.UserRole, name)
        item.setData(Qt.UserRole + 1, description)
        self.macro_list.addItem(item)

    def clear_macros(self):
        """매크로 목록 초기화"""
        self.macro_list.clear()

    def get_selected_macro_name(self) -> str:
        """선택된 매크로 이름"""
        item = self.macro_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return ""

    def _on_macro_selected(self, current, previous):
        if current:
            name = current.data(Qt.UserRole)
            desc = current.data(Qt.UserRole + 1) or "설명 없음"
            self.info_label.setText(f"<b>{name}</b><br><br>{desc}")
            self.macro_selected.emit(name)
