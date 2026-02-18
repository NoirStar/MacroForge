"""
백그라운드 액션 패널 - 메인 매크로와 독립적으로 동작하는 반복 액션 관리 UI
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QFormLayout, QMessageBox, QFileDialog, QCheckBox,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, Signal, Slot

import qtawesome as qta

from src.macros.background_action import (
    BackgroundAction, BackgroundActionSet, ActionType,
    ACTION_TYPE_LABELS, KEYCODE_PRESETS,
)
from src.utils.logger import get_logger

# 액션 타입별 아이콘 매핑
ACTION_TYPE_ICONS = {
    ActionType.KEY_PRESS:  ('mdi.keyboard', '#81C784'),
    ActionType.TAP_COORD:  ('mdi.gesture-tap', '#64B5F6'),
    ActionType.IMAGE_KEY:  ('mdi.image-filter-center-focus', '#FFB74D'),
    ActionType.IMAGE_TAP:  ('mdi.image-move', '#CE93D8'),
}

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SAVED_DIR = PROJECT_ROOT / "saved_macros"
TEMPLATES_DIR = PROJECT_ROOT / "assets" / "templates"


# ═══════════════════════════════════════════════════════════
#  액션 에디터 패널
# ═══════════════════════════════════════════════════════════

class ActionEditorPanel(QScrollArea):
    """단일 백그라운드 액션 속성 편집 패널"""

    action_changed = Signal()

    def __init__(self, screen_capture=None, parent=None):
        super().__init__(parent)
        self.screen_capture = screen_capture
        self._action: Optional[BackgroundAction] = None
        self._updating = False

        content = QWidget()
        self.setWidget(content)
        self.setWidgetResizable(True)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        self._rows = {}
        self._build_ui()
        self._connect_signals()
        self._set_enabled(False)

    def _build_ui(self):
        # ── 기본 정보 ──
        self._add_section("기본 설정")

        # 활성화 체크박스
        self.enabled_check = QCheckBox("활성화")
        self.enabled_check.setChecked(True)
        self.enabled_check.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self._add_field_row("enabled", "상태:", self.enabled_check)

        # 타입
        self.type_combo = QComboBox()
        for at in ActionType:
            self.type_combo.addItem(ACTION_TYPE_LABELS[at], at.value)
        self._add_field_row("type", "타입:", self.type_combo)

        # 이름
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("액션 이름")
        self._add_field_row("name", "이름:", self.name_input)

        # ── 키 입력 관련 ──
        self._add_section("키 설정")

        # 키코드 프리셋
        self.key_preset_combo = QComboBox()
        self.key_preset_combo.addItem("직접 입력", -1)
        for label, code in KEYCODE_PRESETS.items():
            self.key_preset_combo.addItem(f"{label} ({code})", code)
        self.key_preset_combo.setCurrentIndex(1)  # 기본: 스페이스바
        self._add_field_row("key_preset", "키 프리셋:", self.key_preset_combo)

        self.keycode_spin = QSpinBox()
        self.keycode_spin.setRange(0, 999)
        self.keycode_spin.setValue(62)
        self._add_field_row("keycode", "키코드:", self.keycode_spin)

        # ── 좌표 관련 ──
        self._add_section("좌표 설정")

        coord_w = QWidget()
        coord_l = QHBoxLayout(coord_w)
        coord_l.setContentsMargins(0, 0, 0, 0)
        self.x_spin = QSpinBox()
        self.x_spin.setRange(0, 9999)
        self.y_spin = QSpinBox()
        self.y_spin.setRange(0, 9999)
        coord_l.addWidget(QLabel("X:"))
        coord_l.addWidget(self.x_spin)
        coord_l.addWidget(QLabel("Y:"))
        coord_l.addWidget(self.y_spin)
        self._add_field_row("coords", "좌표:", coord_w)

        # ── 이미지 관련 ──
        self._add_section("이미지 설정")

        tpl_widget = QWidget()
        tpl_layout = QHBoxLayout(tpl_widget)
        tpl_layout.setContentsMargins(0, 0, 0, 0)
        self.template_input = QLineEdit()
        self.template_input.setReadOnly(True)
        self.template_input.setPlaceholderText("감지할 이미지 경로")
        tpl_layout.addWidget(self.template_input, 1)
        self.capture_btn = QPushButton(qta.icon('mdi.camera', color='#CE93D8'), "")
        self.capture_btn.setToolTip("화면 캡처로 이미지 생성")
        self.capture_btn.setFixedWidth(35)
        tpl_layout.addWidget(self.capture_btn)
        self.browse_btn = QPushButton(qta.icon('mdi.folder-open', color='#FFB74D'), "")
        self.browse_btn.setToolTip("기존 이미지 선택")
        self.browse_btn.setFixedWidth(35)
        tpl_layout.addWidget(self.browse_btn)
        self._add_field_row("template", "이미지:", tpl_widget)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.30, 1.00)
        self.threshold_spin.setValue(0.85)
        self.threshold_spin.setSingleStep(0.05)
        self._add_field_row("threshold", "신뢰도:", self.threshold_spin)

        # ── 타이밍 ──
        self._add_section("타이밍 설정")

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.1, 300)
        self.interval_spin.setValue(2.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setSuffix(" 초")
        self._add_field_row("interval", "실행 간격:", self.interval_spin)

        self.jitter_spin = QDoubleSpinBox()
        self.jitter_spin.setRange(0, 30)
        self.jitter_spin.setValue(0.5)
        self.jitter_spin.setSingleStep(0.1)
        self.jitter_spin.setSuffix(" 초")
        self.jitter_spin.setToolTip("간격에 ± 랜덤 변동을 주어 탐지를 회피합니다")
        self._add_field_row("jitter", "랜덤 변동:", self.jitter_spin)

        self._layout.addStretch()

    def _add_section(self, title: str):
        lbl = QLabel(f"── {title} ──")
        lbl.setStyleSheet("color: #4FC3F7; font-weight: bold; padding-top: 4px;")
        self._layout.addWidget(lbl)

    def _add_field_row(self, key: str, label_text: str, widget: QWidget):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(80)
        row_layout.addWidget(lbl)
        row_layout.addWidget(widget, 1)
        self._layout.addWidget(row)
        self._rows[key] = row

    def _connect_signals(self):
        self.enabled_check.toggled.connect(self._emit)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.name_input.textChanged.connect(self._emit)
        self.key_preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.keycode_spin.valueChanged.connect(self._emit)
        self.x_spin.valueChanged.connect(self._emit)
        self.y_spin.valueChanged.connect(self._emit)
        self.template_input.textChanged.connect(self._emit)
        self.threshold_spin.valueChanged.connect(self._emit)
        self.interval_spin.valueChanged.connect(self._emit)
        self.jitter_spin.valueChanged.connect(self._emit)
        self.capture_btn.clicked.connect(self._capture_template)
        self.browse_btn.clicked.connect(self._browse_template)

    def _emit(self):
        if not self._updating:
            self._save_to_action()
            self.action_changed.emit()

    def _on_type_changed(self):
        if self._updating:
            return
        at = ActionType(self.type_combo.currentData())
        self._update_visibility(at)
        self._emit()

    def _on_preset_changed(self):
        if self._updating:
            return
        code = self.key_preset_combo.currentData()
        if code != -1:
            self._updating = True
            self.keycode_spin.setValue(code)
            self._updating = False
        # 직접 입력 시 keycode spin 수동 편집
        self._rows["keycode"].setVisible(code == -1)
        self._emit()

    def _set_enabled(self, enabled: bool):
        for row in self._rows.values():
            row.setEnabled(enabled)

    def _update_visibility(self, at: ActionType):
        """액션 타입에 따라 관련 필드만 표시"""
        needs_key = at in (ActionType.KEY_PRESS, ActionType.IMAGE_KEY)
        needs_coord = at == ActionType.TAP_COORD
        needs_image = at in (ActionType.IMAGE_KEY, ActionType.IMAGE_TAP)

        self._rows["key_preset"].setVisible(needs_key)
        # 직접 입력 모드일때만 키코드 표시
        if needs_key:
            code = self.key_preset_combo.currentData()
            self._rows["keycode"].setVisible(code == -1)
        else:
            self._rows["keycode"].setVisible(False)

        self._rows["coords"].setVisible(needs_coord)
        self._rows["template"].setVisible(needs_image)
        self._rows["threshold"].setVisible(needs_image)

    # ── 액션 로드/저장 ──

    def load_action(self, action: BackgroundAction):
        self._updating = True
        self._action = action
        self._set_enabled(True)

        self.enabled_check.setChecked(action.enabled)

        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == action.type.value:
                self.type_combo.setCurrentIndex(i)
                break

        self.name_input.setText(action.name)
        self.keycode_spin.setValue(action.keycode)
        self.x_spin.setValue(action.x)
        self.y_spin.setValue(action.y)
        self.template_input.setText(action.template_path)
        self.threshold_spin.setValue(action.threshold)
        self.interval_spin.setValue(action.interval)
        self.jitter_spin.setValue(action.interval_jitter)

        # 프리셋 콤보 맞추기
        preset_found = False
        for i in range(self.key_preset_combo.count()):
            if self.key_preset_combo.itemData(i) == action.keycode:
                self.key_preset_combo.setCurrentIndex(i)
                preset_found = True
                break
        if not preset_found:
            self.key_preset_combo.setCurrentIndex(0)  # 직접 입력

        self._update_visibility(action.type)
        self._updating = False

    def _save_to_action(self):
        if not self._action:
            return
        a = self._action
        a.type = ActionType(self.type_combo.currentData())
        a.name = self.name_input.text()
        a.enabled = self.enabled_check.isChecked()
        a.keycode = self.keycode_spin.value()
        a.x = self.x_spin.value()
        a.y = self.y_spin.value()
        a.template_path = self.template_input.text()
        a.threshold = self.threshold_spin.value()
        a.interval = self.interval_spin.value()
        a.interval_jitter = self.jitter_spin.value()

        # 키코드 라벨 업데이트
        preset_idx = self.key_preset_combo.currentIndex()
        if preset_idx > 0:
            a.keycode_label = self.key_preset_combo.currentText().split(" (")[0]
        else:
            a.keycode_label = f"키코드 {a.keycode}"

    def clear(self):
        self._action = None
        self._set_enabled(False)

    # ── 템플릿 캡처/선택 ──

    def _capture_template(self):
        if not self.screen_capture:
            QMessageBox.warning(self, "오류", "스크린 캡처 모듈이 없습니다")
            return

        bgr = self.screen_capture.capture(force=True)
        if bgr is None:
            QMessageBox.warning(self, "오류", "스크린샷을 캡처할 수 없습니다.\nADB 연결을 확인하세요.")
            return

        from src.ui.capture_dialog import CaptureDialog
        dlg = CaptureDialog(bgr, self)
        if dlg.exec() and dlg.saved_path:
            self.template_input.setText(dlg.saved_path)
            self._emit()
            logger.info(f"BG 템플릿 저장: {dlg.saved_path}")

    def _browse_template(self):
        start_dir = str(TEMPLATES_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "감지 이미지 선택", start_dir,
            "이미지 (*.png *.jpg *.bmp)"
        )
        if path:
            self.template_input.setText(path)
            self._emit()


# ═══════════════════════════════════════════════════════════
#  백그라운드 액션 메인 위젯
# ═══════════════════════════════════════════════════════════

class BackgroundActionWidget(QWidget):
    """백그라운드 액션 관리 탭 위젯"""

    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self, screen_capture=None, parent=None):
        super().__init__(parent)
        self.screen_capture = screen_capture
        self._action_set = BackgroundActionSet()
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

        header = QLabel("백그라운드 액션")
        header.setObjectName("sectionHeader")
        top_layout.addWidget(header)

        desc = QLabel(
            "메인 매크로 루프와 독립적으로 동작하는 반복 액션입니다.\n"
            "점프, 버프 등 주기적으로 실행해야 하는 동작을 설정하세요."
        )
        desc.setStyleSheet("color: #666; font-size: 11px;")
        desc.setWordWrap(True)
        top_layout.addWidget(desc)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)

        self.start_btn = QPushButton(qta.icon('mdi.play', color='#fff'), " 백그라운드 시작")
        self.start_btn.setObjectName("successBtn")
        self.start_btn.setFixedHeight(32)
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._on_start)
        ctrl_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton(qta.icon('mdi.stop', color='#fff'), " 백그라운드 정지")
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

        # 저장/로드
        self.save_btn = QPushButton(qta.icon('mdi.content-save', color='#fff'), " 저장")
        self.save_btn.setFixedSize(70, 30)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_actions)
        ctrl_row.addWidget(self.save_btn)

        self.load_btn = QPushButton(qta.icon('mdi.folder-open', color='#fff'), " 로드")
        self.load_btn.setObjectName("ghostBtn")
        self.load_btn.setFixedSize(70, 30)
        self.load_btn.setCursor(Qt.PointingHandCursor)
        self.load_btn.clicked.connect(self._load_actions)
        ctrl_row.addWidget(self.load_btn)

        top_layout.addLayout(ctrl_row)
        layout.addWidget(top_frame)

        # ── 중앙: 액션 목록 + 에디터 ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # 좌: 액션 리스트
        list_panel = QWidget()
        lp_layout = QVBoxLayout(list_panel)
        lp_layout.setContentsMargins(0, 0, 4, 0)
        lp_layout.setSpacing(4)

        action_header = QLabel("액션 목록")
        action_header.setObjectName("sectionHeader")
        lp_layout.addWidget(action_header)

        self.action_list = QListWidget()
        self.action_list.currentRowChanged.connect(self._on_action_selected)
        lp_layout.addWidget(self.action_list, 1)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(3)
        for icon_name, obj_name, tip, slot in [
            ('mdi.arrow-up-bold', 'ghostBtn', "위로", self._move_up),
            ('mdi.arrow-down-bold', 'ghostBtn', "아래로", self._move_down),
            ('mdi.plus-circle', 'successBtn', "액션 추가", self._add_action),
            ('mdi.content-copy', 'ghostBtn', "복사", self._copy_action),
            ('mdi.delete', 'dangerBtn', "삭제", self._delete_action),
        ]:
            b = QPushButton(qta.icon(icon_name, color='#fff'), "")
            b.setObjectName(obj_name)
            b.setToolTip(tip)
            b.setFixedSize(34, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            btn_bar.addWidget(b)
        btn_bar.addStretch()
        lp_layout.addLayout(btn_bar)

        splitter.addWidget(list_panel)

        # 우: 에디터
        self.action_editor = ActionEditorPanel(screen_capture=self.screen_capture)
        self.action_editor.action_changed.connect(self._on_action_edited)
        splitter.addWidget(self.action_editor)

        splitter.setSizes([250, 280])
        layout.addWidget(splitter, 1)

    # ── 액션 목록 관리 ──

    def _refresh_list(self):
        """리스트 위젯 갱신"""
        cur = self.action_list.currentRow()
        self.action_list.clear()
        for i, action in enumerate(self._action_set.actions):
            item = QListWidgetItem(action.display_text(i + 1))
            icon_info = ACTION_TYPE_ICONS.get(action.type)
            if icon_info:
                item.setIcon(qta.icon(icon_info[0], color=icon_info[1]))
            self.action_list.addItem(item)
        if 0 <= cur < self.action_list.count():
            self.action_list.setCurrentRow(cur)
        elif self.action_list.count() > 0:
            self.action_list.setCurrentRow(self.action_list.count() - 1)

    @Slot(int)
    def _on_action_selected(self, row: int):
        if 0 <= row < len(self._action_set.actions):
            action = self._action_set.actions[row]
            self.action_editor.load_action(action)
        else:
            self.action_editor.clear()

    def _on_action_edited(self):
        """에디터에서 속성 변경 시 리스트 텍스트/아이콘 갱신"""
        row = self.action_list.currentRow()
        if 0 <= row < len(self._action_set.actions):
            action = self._action_set.actions[row]
            item = self.action_list.item(row)
            item.setText(action.display_text(row + 1))
            icon_info = ACTION_TYPE_ICONS.get(action.type)
            if icon_info:
                item.setIcon(qta.icon(icon_info[0], color=icon_info[1]))

    @Slot()
    def _add_action(self):
        action = BackgroundAction(name=f"액션 {len(self._action_set.actions) + 1}")
        self._action_set.actions.append(action)
        self._refresh_list()
        self.action_list.setCurrentRow(len(self._action_set.actions) - 1)

    @Slot()
    def _copy_action(self):
        row = self.action_list.currentRow()
        if row < 0:
            return
        import copy
        action = copy.deepcopy(self._action_set.actions[row])
        action.name += " (복사)"
        self._action_set.actions.insert(row + 1, action)
        self._refresh_list()
        self.action_list.setCurrentRow(row + 1)

    @Slot()
    def _delete_action(self):
        row = self.action_list.currentRow()
        if row < 0:
            return
        self._action_set.actions.pop(row)
        self._refresh_list()

    @Slot()
    def _move_up(self):
        row = self.action_list.currentRow()
        if row <= 0:
            return
        actions = self._action_set.actions
        actions[row], actions[row - 1] = actions[row - 1], actions[row]
        self._refresh_list()
        self.action_list.setCurrentRow(row - 1)

    @Slot()
    def _move_down(self):
        row = self.action_list.currentRow()
        actions = self._action_set.actions
        if row < 0 or row >= len(actions) - 1:
            return
        actions[row], actions[row + 1] = actions[row + 1], actions[row]
        self._refresh_list()
        self.action_list.setCurrentRow(row + 1)

    # ── 시작/정지 ──

    @Slot()
    def _on_start(self):
        enabled = [a for a in self._action_set.actions if a.enabled]
        if not enabled:
            QMessageBox.information(self, "알림", "활성화된 액션이 없습니다.\n액션을 추가하고 활성화하세요.")
            return
        self.start_requested.emit()

    @Slot()
    def _on_stop(self):
        self.stop_requested.emit()

    def set_running(self, running: bool):
        """실행 상태 UI 반영"""
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        if running:
            self.status_label.setText("● 실행 중")
            self.status_label.setStyleSheet("color: #22C55E; font-weight: bold; font-size: 12px;")
        else:
            self.status_label.setText("● 대기")
            self.status_label.setStyleSheet("color: #666; font-weight: bold; font-size: 12px;")

    def get_action_set(self) -> BackgroundActionSet:
        return self._action_set

    def get_actions(self) -> list[BackgroundAction]:
        return self._action_set.actions

    # ── 저장/로드 ──

    @Slot()
    def _save_actions(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "백그라운드 액션 저장",
            str(SAVED_DIR / "bg_actions.yaml"),
            "YAML (*.yaml *.yml)"
        )
        if path:
            self._action_set.save(path)
            logger.info(f"백그라운드 액션 저장: {path}")

    @Slot()
    def _load_actions(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "백그라운드 액션 로드",
            str(SAVED_DIR),
            "YAML (*.yaml *.yml)"
        )
        if path:
            try:
                self._action_set = BackgroundActionSet.load(path)
                self._refresh_list()
                logger.info(f"백그라운드 액션 로드: {path}")
            except Exception as e:
                QMessageBox.warning(self, "로드 오류", f"파일을 로드할 수 없습니다:\n{e}")
