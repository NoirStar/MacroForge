"""
Macro Queue - 여러 매크로를 순차적으로 실행하는 큐 관리 위젯
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFrame, QSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, Signal, Slot

import qtawesome as qta

from src.macros.macro_step import MacroScript
from src.utils.logger import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SAVED_DIR = PROJECT_ROOT / "saved_macros"


class MacroQueueWidget(QWidget):
    """매크로 순차 실행 큐 위젯"""

    # 시그널: 큐 실행 요청 (매크로 스크립트 리스트)
    queue_start_requested = Signal(list)
    queue_stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue_items: List[dict] = []  # [{"name": str, "path": str, "repeats": int}, ...]
        self._is_running = False
        self._current_index = -1
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── 상단: 설명 + 제어 ──
        top_frame = QFrame()
        top_frame.setObjectName("previewFrame")
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.setSpacing(8)

        header = QLabel("매크로 큐")
        header.setObjectName("sectionHeader")
        top_layout.addWidget(header)

        desc = QLabel(
            "저장된 매크로를 순서대로 추가하고, 순차적으로 실행합니다.\n"
            "각 매크로의 반복 횟수를 개별 설정할 수 있습니다."
        )
        desc.setStyleSheet("color: #666; font-size: 11px;")
        desc.setWordWrap(True)
        top_layout.addWidget(desc)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.start_btn = QPushButton(qta.icon('mdi.playlist-play', color='#fff'), " 큐 실행")
        self.start_btn.setObjectName("successBtn")
        self.start_btn.setFixedHeight(32)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)
        ctrl_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton(qta.icon('mdi.stop', color='#fff'), " 큐 정지")
        self.stop_btn.setObjectName("dangerBtn")
        self.stop_btn.setFixedHeight(32)
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        ctrl_row.addWidget(self.stop_btn)

        self.status_label = QLabel("● 대기")
        self.status_label.setObjectName("stateLabel")
        ctrl_row.addWidget(self.status_label)
        ctrl_row.addStretch()

        # 전체 반복
        ctrl_row.addWidget(QLabel("전체 반복:"))
        self.total_repeats_spin = QSpinBox()
        self.total_repeats_spin.setRange(1, 9999)
        self.total_repeats_spin.setValue(1)
        self.total_repeats_spin.setFixedWidth(70)
        self.total_repeats_spin.setToolTip("큐 전체를 몇 번 반복할지 설정")
        ctrl_row.addWidget(self.total_repeats_spin)

        top_layout.addLayout(ctrl_row)
        layout.addWidget(top_frame)

        # ── 큐 목록 ──
        queue_header = QLabel("실행 대기열")
        queue_header.setObjectName("sectionHeader")
        layout.addWidget(queue_header)

        self.queue_list = QListWidget()
        self.queue_list.setDragDropMode(QListWidget.InternalMove)
        self.queue_list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.queue_list, 1)

        # ── 하단: 추가/제거 버튼 ──
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(4)

        add_btn = QPushButton(qta.icon('mdi.plus-circle', color='#fff'), " 매크로 추가")
        add_btn.setObjectName("successBtn")
        add_btn.setFixedHeight(30)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._add_macro)
        btn_bar.addWidget(add_btn)

        up_btn = QPushButton(qta.icon('mdi.arrow-up-bold', color='#fff'), "")
        up_btn.setObjectName("ghostBtn")
        up_btn.setFixedSize(30, 30)
        up_btn.setToolTip("위로")
        up_btn.setCursor(Qt.PointingHandCursor)
        up_btn.clicked.connect(self._move_up)
        btn_bar.addWidget(up_btn)

        down_btn = QPushButton(qta.icon('mdi.arrow-down-bold', color='#fff'), "")
        down_btn.setObjectName("ghostBtn")
        down_btn.setFixedSize(30, 30)
        down_btn.setToolTip("아래로")
        down_btn.setCursor(Qt.PointingHandCursor)
        down_btn.clicked.connect(self._move_down)
        btn_bar.addWidget(down_btn)

        dup_btn = QPushButton(qta.icon('mdi.content-copy', color='#fff'), "")
        dup_btn.setObjectName("ghostBtn")
        dup_btn.setFixedSize(30, 30)
        dup_btn.setToolTip("복제")
        dup_btn.setCursor(Qt.PointingHandCursor)
        dup_btn.clicked.connect(self._duplicate)
        btn_bar.addWidget(dup_btn)

        del_btn = QPushButton(qta.icon('mdi.delete', color='#fff'), "")
        del_btn.setObjectName("dangerBtn")
        del_btn.setFixedSize(30, 30)
        del_btn.setToolTip("삭제")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(self._remove_macro)
        btn_bar.addWidget(del_btn)

        btn_bar.addStretch()

        # 선택한 매크로의 반복 횟수
        btn_bar.addWidget(QLabel("반복:"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(1, 9999)
        self.repeat_spin.setValue(1)
        self.repeat_spin.setFixedWidth(70)
        self.repeat_spin.setToolTip("선택한 매크로의 반복 횟수")
        self.repeat_spin.valueChanged.connect(self._on_repeat_changed)
        btn_bar.addWidget(self.repeat_spin)

        layout.addLayout(btn_bar)

    # ── 큐 관리 ──

    def _add_macro(self):
        """저장된 매크로 파일을 선택하여 큐에 추가"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "매크로 추가",
            str(SAVED_DIR),
            "매크로 파일 (*.yaml)"
        )
        for f in files:
            try:
                script = MacroScript.load(f)
                item_data = {
                    "name": script.name,
                    "path": f,
                    "repeats": 1,
                    "steps": len(script.steps),
                }
                self._queue_items.append(item_data)
            except Exception as e:
                logger.error(f"매크로 로드 실패: {f} - {e}")
                QMessageBox.warning(self, "오류", f"매크로 로드 실패:\n{Path(f).name}\n{e}")
        self._refresh_list()

    def _remove_macro(self):
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._queue_items):
            self._queue_items.pop(row)
            self._refresh_list()

    def _duplicate(self):
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._queue_items):
            item = self._queue_items[row].copy()
            self._queue_items.insert(row + 1, item)
            self._refresh_list()
            self.queue_list.setCurrentRow(row + 1)

    def _move_up(self):
        row = self.queue_list.currentRow()
        if row > 0:
            self._queue_items[row], self._queue_items[row - 1] = \
                self._queue_items[row - 1], self._queue_items[row]
            self._refresh_list()
            self.queue_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._queue_items) - 1:
            self._queue_items[row], self._queue_items[row + 1] = \
                self._queue_items[row + 1], self._queue_items[row]
            self._refresh_list()
            self.queue_list.setCurrentRow(row + 1)

    def _on_repeat_changed(self, value: int):
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._queue_items):
            self._queue_items[row]["repeats"] = value
            self._refresh_list_text(row)

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self._queue_items):
            self.repeat_spin.blockSignals(True)
            self.repeat_spin.setValue(self._queue_items[row]["repeats"])
            self.repeat_spin.blockSignals(False)

    def _refresh_list(self):
        cur = self.queue_list.currentRow()
        self.queue_list.clear()
        for i, item in enumerate(self._queue_items):
            display = self._format_item(i, item)
            list_item = QListWidgetItem(display)
            list_item.setIcon(qta.icon('mdi.file-document-edit', color='#81C784'))
            # 현재 실행 중인 항목 강조
            if self._is_running and i == self._current_index:
                list_item.setIcon(qta.icon('mdi.play-circle', color='#22C55E'))
            self.queue_list.addItem(list_item)
        if 0 <= cur < self.queue_list.count():
            self.queue_list.setCurrentRow(cur)
        elif self.queue_list.count() > 0:
            self.queue_list.setCurrentRow(self.queue_list.count() - 1)

    def _refresh_list_text(self, row: int):
        if 0 <= row < self.queue_list.count():
            self.queue_list.item(row).setText(
                self._format_item(row, self._queue_items[row])
            )

    def _format_item(self, index: int, item: dict) -> str:
        repeats_str = f"x{item['repeats']}" if item['repeats'] > 1 else ""
        status = ""
        if self._is_running:
            if index < self._current_index:
                status = " [완료]"
            elif index == self._current_index:
                status = " [실행 중]"
        return f"{index + 1}. {item['name']}  ({item['steps']}스텝) {repeats_str}{status}"

    # ── 실행 제어 ──

    @Slot()
    def _on_start(self):
        if not self._queue_items:
            QMessageBox.information(self, "알림", "큐에 매크로를 추가하세요.")
            return
        self.queue_start_requested.emit(self._queue_items.copy())

    @Slot()
    def _on_stop(self):
        self.queue_stop_requested.emit()

    def set_running(self, running: bool, current_index: int = -1):
        """외부에서 실행 상태 업데이트"""
        self._is_running = running
        self._current_index = current_index

        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

        if running:
            self.status_label.setText("● 실행 중")
            self.status_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 12px;")
        else:
            self.status_label.setText("● 대기")
            self.status_label.setStyleSheet("color: #666; font-weight: bold; font-size: 12px;")
            self._current_index = -1

        self._refresh_list()

    def update_progress(self, index: int, repeat_current: int, repeat_total: int):
        """현재 진행 상황 업데이트"""
        self._current_index = index
        if 0 <= index < len(self._queue_items):
            item = self._queue_items[index]
            if repeat_total > 1:
                self.status_label.setText(
                    f"● {item['name']} ({repeat_current}/{repeat_total})"
                )
            else:
                self.status_label.setText(f"● {item['name']}")
            self.status_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 12px;")
        self._refresh_list()

    @property
    def total_repeats(self) -> int:
        return self.total_repeats_spin.value()
