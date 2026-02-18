"""
비주얼 매크로 빌더 - 스텝 기반 매크로 생성/편집/저장
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QListWidget, QListWidgetItem, QPushButton,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QFormLayout, QMessageBox, QFileDialog, QInputDialog,
    QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot

import qtawesome as qta

from src.macros.macro_step import (
    MacroStep, MacroScript, StepType,
    STEP_TYPE_LABELS, STEP_FIELDS, CAN_FAIL_TYPES,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# 스텝 타입별 아이콘 매핑
STEP_TYPE_ICONS = {
    StepType.CLICK_IMAGE:    ('mdi.image-search', '#64B5F6'),
    StepType.CLICK_COORD:    ('mdi.crosshairs-gps', '#81C784'),
    StepType.WAIT:           ('mdi.timer-sand', '#FFB74D'),
    StepType.WAIT_FOR_IMAGE: ('mdi.eye-outline', '#CE93D8'),
    StepType.IF_IMAGE:       ('mdi.help-rhombus-outline', '#4FC3F7'),
    StepType.SWIPE:          ('mdi.gesture-swipe', '#F48FB1'),
}

PROJECT_ROOT = Path(__file__).parent.parent.parent
SAVED_DIR = PROJECT_ROOT / "saved_macros"
TEMPLATES_DIR = PROJECT_ROOT / "assets" / "templates"


# ═══════════════════════════════════════════════════════════
#  스텝 에디터 패널
# ═══════════════════════════════════════════════════════════

class StepEditorPanel(QScrollArea):
    """단일 스텝 속성 편집 패널"""

    step_changed = Signal()

    def __init__(self, screen_capture=None, parent=None):
        super().__init__(parent)
        self.screen_capture = screen_capture
        self._step: Optional[MacroStep] = None
        self._all_steps: list[MacroStep] = []
        self._updating = False  # 프로그래밍적 변경 시 시그널 차단

        content = QWidget()
        self.setWidget(content)
        self.setWidgetResizable(True)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(6)

        self._rows = {}  # key -> QWidget (show/hide용)
        self._build_ui()
        self._connect_signals()
        self._set_enabled(False)

    def _build_ui(self):
        # ── 기본 정보 ──
        self._add_section("기본 설정")

        # 타입
        self.type_combo = QComboBox()
        for st in StepType:
            self.type_combo.addItem(STEP_TYPE_LABELS[st], st.value)
        self._add_field_row("type", "타입:", self.type_combo)

        # 이름
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("스텝 이름")
        self._add_field_row("name", "이름:", self.name_input)

        # ── 이미지 관련 ──
        self._add_section("이미지 설정")

        tpl_widget = QWidget()
        tpl_layout = QHBoxLayout(tpl_widget)
        tpl_layout.setContentsMargins(0, 0, 0, 0)
        self.template_input = QLineEdit()
        self.template_input.setReadOnly(True)
        self.template_input.setPlaceholderText("템플릿 이미지 경로")
        tpl_layout.addWidget(self.template_input, 1)
        self.capture_btn = QPushButton(qta.icon('mdi.camera', color='#CE93D8'), "")
        self.capture_btn.setToolTip("화면 캡처로 템플릿 생성")
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

        coord2_w = QWidget()
        coord2_l = QHBoxLayout(coord2_w)
        coord2_l.setContentsMargins(0, 0, 0, 0)
        self.x2_spin = QSpinBox()
        self.x2_spin.setRange(0, 9999)
        self.y2_spin = QSpinBox()
        self.y2_spin.setRange(0, 9999)
        coord2_l.addWidget(QLabel("X2:"))
        coord2_l.addWidget(self.x2_spin)
        coord2_l.addWidget(QLabel("Y2:"))
        coord2_l.addWidget(self.y2_spin)
        self._add_field_row("coords2", "도착점:", coord2_w)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(50, 5000)
        self.duration_spin.setValue(300)
        self.duration_spin.setSuffix(" ms")
        self._add_field_row("duration", "소요시간:", self.duration_spin)

        # ── 시간 관련 ──
        self._add_section("시간 설정")

        self.wait_spin = QDoubleSpinBox()
        self.wait_spin.setRange(0.1, 300)
        self.wait_spin.setValue(1.0)
        self.wait_spin.setSingleStep(0.5)
        self.wait_spin.setSuffix(" 초")
        self._add_field_row("wait_time", "대기시간:", self.wait_spin)

        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1, 300)
        self.timeout_spin.setValue(10)
        self.timeout_spin.setSingleStep(1)
        self.timeout_spin.setSuffix(" 초")
        self._add_field_row("timeout", "타임아웃:", self.timeout_spin)

        # ── 흐름 제어 ──
        self._add_section("흐름 제어")

        self.success_combo = QComboBox()
        self._add_field_row("on_success", "성공시:", self.success_combo)

        self.fail_combo = QComboBox()
        self._add_field_row("on_fail", "실패시:", self.fail_combo)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 9999)
        self.retries_spin.setValue(10)
        self._add_field_row("retries", "재시도횟수:", self.retries_spin)

        self.retry_delay_spin = QDoubleSpinBox()
        self.retry_delay_spin.setRange(0.1, 60)
        self.retry_delay_spin.setValue(1.0)
        self.retry_delay_spin.setSingleStep(0.5)
        self.retry_delay_spin.setSuffix(" 초")
        self._add_field_row("retry_delay", "재시도간격:", self.retry_delay_spin)

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
        lbl.setFixedWidth(75)
        row_layout.addWidget(lbl)
        row_layout.addWidget(widget, 1)
        self._layout.addWidget(row)
        self._rows[key] = row

    def _connect_signals(self):
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.name_input.textChanged.connect(self._emit)
        self.template_input.textChanged.connect(self._emit)
        self.threshold_spin.valueChanged.connect(self._emit)
        self.x_spin.valueChanged.connect(self._emit)
        self.y_spin.valueChanged.connect(self._emit)
        self.x2_spin.valueChanged.connect(self._emit)
        self.y2_spin.valueChanged.connect(self._emit)
        self.duration_spin.valueChanged.connect(self._emit)
        self.wait_spin.valueChanged.connect(self._emit)
        self.timeout_spin.valueChanged.connect(self._emit)
        self.success_combo.currentIndexChanged.connect(self._emit)
        self.fail_combo.currentIndexChanged.connect(self._on_fail_changed)
        self.retries_spin.valueChanged.connect(self._emit)
        self.retry_delay_spin.valueChanged.connect(self._emit)
        self.capture_btn.clicked.connect(self._capture_template)
        self.browse_btn.clicked.connect(self._browse_template)

    def _emit(self):
        if not self._updating:
            self._save_to_step()
            self.step_changed.emit()

    def _on_type_changed(self):
        if self._updating:
            return
        st = StepType(self.type_combo.currentData())
        self._update_visibility(st)
        self._emit()

    def _on_fail_changed(self):
        if self._updating:
            return
        # 재시도 관련 필드 표시 여부
        fail_val = self.fail_combo.currentData()
        show_retry = (fail_val == "retry")
        self._rows.get("retries", QWidget()).setVisible(show_retry)
        self._rows.get("retry_delay", QWidget()).setVisible(show_retry)
        self._emit()

    def _set_enabled(self, enabled: bool):
        for row in self._rows.values():
            row.setEnabled(enabled)

    # ── 필드 표시/숨김 ──

    def _update_visibility(self, st: StepType):
        fields = STEP_FIELDS.get(st, set())
        self._rows["template"].setVisible("template" in fields)
        self._rows["threshold"].setVisible("threshold" in fields)
        self._rows["coords"].setVisible("coords" in fields)
        self._rows["coords2"].setVisible("coords2" in fields)
        self._rows["duration"].setVisible("duration" in fields)
        self._rows["wait_time"].setVisible("wait_time" in fields)
        self._rows["timeout"].setVisible("timeout" in fields)
        self._rows["on_fail"].setVisible("on_fail" in fields)

        # 재시도 필드
        show_retry = ("retries" in fields)
        if show_retry:
            fail_val = self.fail_combo.currentData()
            show_retry = (fail_val == "retry")
        self._rows["retries"].setVisible(show_retry)
        self._rows["retry_delay"].setVisible(show_retry)

    # ── 스텝 로드/저장 ──

    def load_step(self, step: MacroStep, all_steps: list[MacroStep]):
        self._updating = True
        self._step = step
        self._all_steps = all_steps

        self._set_enabled(True)

        # 타입
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == step.type.value:
                self.type_combo.setCurrentIndex(i)
                break

        self.name_input.setText(step.name)
        self.template_input.setText(step.template_path)
        self.threshold_spin.setValue(step.threshold)
        self.x_spin.setValue(step.x)
        self.y_spin.setValue(step.y)
        self.x2_spin.setValue(step.x2)
        self.y2_spin.setValue(step.y2)
        self.duration_spin.setValue(step.duration_ms)
        self.wait_spin.setValue(step.wait_time)
        self.timeout_spin.setValue(step.timeout)
        self.retries_spin.setValue(step.max_retries)
        self.retry_delay_spin.setValue(step.retry_delay)

        self._populate_flow_combos(step)
        self._update_visibility(step.type)

        self._updating = False

    def _populate_flow_combos(self, step: MacroStep):
        """흐름 제어 콤보 채우기"""
        for combo, action_val in [(self.success_combo, step.on_success),
                                   (self.fail_combo, step.on_fail)]:
            combo.clear()
            combo.addItem(qta.icon('mdi.skip-next', color='#4FC3F7'), "다음 스텝으로", "next")
            combo.addItem(qta.icon('mdi.restart', color='#81C784'), "처음으로 (루프)", "loop")
            combo.addItem(qta.icon('mdi.stop', color='#FF5252'), "매크로 정지", "stop")
            if combo is self.fail_combo:
                combo.addItem(qta.icon('mdi.refresh', color='#FFB74D'), "재시도", "retry")

            # 각 스텝으로 이동 옵션
            for i, s in enumerate(self._all_steps):
                combo.addItem(f"↪ {i+1}번: {s.name}", f"goto:{i}")

            # 현재 값 선택
            for i in range(combo.count()):
                if combo.itemData(i) == action_val:
                    combo.setCurrentIndex(i)
                    break

    def _save_to_step(self):
        if not self._step:
            return
        s = self._step
        s.type = StepType(self.type_combo.currentData())
        s.name = self.name_input.text()
        s.template_path = self.template_input.text()
        s.threshold = self.threshold_spin.value()
        s.x = self.x_spin.value()
        s.y = self.y_spin.value()
        s.x2 = self.x2_spin.value()
        s.y2 = self.y2_spin.value()
        s.duration_ms = self.duration_spin.value()
        s.wait_time = self.wait_spin.value()
        s.timeout = self.timeout_spin.value()
        s.max_retries = self.retries_spin.value()
        s.retry_delay = self.retry_delay_spin.value()

        succ_data = self.success_combo.currentData()
        if succ_data:
            s.on_success = succ_data
        fail_data = self.fail_combo.currentData()
        if fail_data:
            s.on_fail = fail_data

    def clear(self):
        self._step = None
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
            logger.info(f"템플릿 저장: {dlg.saved_path}")

    def _browse_template(self):
        start_dir = str(TEMPLATES_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, "템플릿 이미지 선택", start_dir,
            "이미지 (*.png *.jpg *.bmp)"
        )
        if path:
            self.template_input.setText(path)
            self._emit()


# ═══════════════════════════════════════════════════════════
#  매크로 빌더 메인 위젯
# ═══════════════════════════════════════════════════════════

class MacroBuilderWidget(QWidget):
    """비주얼 매크로 빌더 - 생성/편집/저장/실행"""

    macro_run_requested = Signal()  # 실행 요청 시그널

    def __init__(self, screen_capture=None, builtin_macros: dict = None, parent=None):
        super().__init__(parent)
        self.screen_capture = screen_capture
        self._builtin_macros = builtin_macros or {}  # {name: class}
        self._scripts: dict[str, dict] = {}  # name -> {"script": MacroScript, "path": str}
        self._current_script: Optional[MacroScript] = None
        self._is_builtin = False

        self._setup_ui()
        self._load_saved_macros()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── 매크로 선택/관리 ──
        top_frame = QFrame()
        top_frame.setObjectName("previewFrame")
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.setSpacing(8)

        header = QLabel("매크로 관리")
        header.setObjectName("sectionHeader")
        top_layout.addWidget(header)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self.macro_combo = QComboBox()
        self.macro_combo.setMinimumWidth(150)
        self.macro_combo.setFixedHeight(30)
        self.macro_combo.currentIndexChanged.connect(self._on_macro_selected)
        row1.addWidget(self.macro_combo, 1)

        self.new_btn = QPushButton(qta.icon('mdi.plus-circle', color='#fff'), " 새로")
        self.new_btn.setObjectName("successBtn")
        self.new_btn.setFixedSize(70, 30)
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.clicked.connect(self._new_macro)
        row1.addWidget(self.new_btn)

        self.save_btn = QPushButton(qta.icon('mdi.content-save', color='#fff'), " 저장")
        self.save_btn.setFixedSize(70, 30)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_macro)
        row1.addWidget(self.save_btn)

        self.dup_btn = QPushButton(qta.icon('mdi.content-copy', color='#fff'), " 복사")
        self.dup_btn.setObjectName("ghostBtn")
        self.dup_btn.setFixedSize(70, 30)
        self.dup_btn.setCursor(Qt.PointingHandCursor)
        self.dup_btn.clicked.connect(self._duplicate_macro)
        row1.addWidget(self.dup_btn)

        self.del_btn = QPushButton(qta.icon('mdi.delete', color='#fff'), "")
        self.del_btn.setObjectName("dangerBtn")
        self.del_btn.setFixedSize(34, 30)
        self.del_btn.setCursor(Qt.PointingHandCursor)
        self.del_btn.clicked.connect(self._delete_macro)
        row1.addWidget(self.del_btn)

        top_layout.addLayout(row1)

        # 매크로 이름
        name_row = QHBoxLayout()
        name_lbl = QLabel("이름:")
        name_lbl.setStyleSheet("color: #8899AA; font-size: 11px;")
        name_row.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("매크로 이름")
        self.name_input.setFixedHeight(28)
        self.name_input.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self.name_input, 1)
        top_layout.addLayout(name_row)

        # 내장 매크로 안내
        self.builtin_label = QLabel("  내장 매크로 - 편집 불가")
        self.builtin_label.setStyleSheet(
            "color: #F59E0B; padding: 8px; background: #2A2510; border-radius: 6px; font-size: 11px;"
        )
        self.builtin_label.setVisible(False)
        top_layout.addWidget(self.builtin_label)

        layout.addWidget(top_frame)

        # ── 스텝 목록 + 에디터 (스플리터) ──
        self.builder_area = QWidget()
        builder_layout = QVBoxLayout(self.builder_area)
        builder_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)

        # 좌: 스텝 목록
        step_panel = QWidget()
        sp_layout = QVBoxLayout(step_panel)
        sp_layout.setContentsMargins(0, 0, 4, 0)
        sp_layout.setSpacing(4)

        step_header = QLabel("스텝 목록")
        step_header.setObjectName("sectionHeader")
        sp_layout.addWidget(step_header)

        self.step_list = QListWidget()
        self.step_list.currentRowChanged.connect(self._on_step_selected)
        sp_layout.addWidget(self.step_list, 1)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(3)
        for icon_name, obj_name, tip, slot in [
            ('mdi.arrow-up-bold', 'ghostBtn', "위로", self._move_up),
            ('mdi.arrow-down-bold', 'ghostBtn', "아래로", self._move_down),
            ('mdi.plus-circle', 'successBtn', "스텝 추가", self._add_step),
            ('mdi.content-copy', 'ghostBtn', "복사", self._copy_step),
            ('mdi.delete', 'dangerBtn', "삭제", self._delete_step),
        ]:
            b = QPushButton(qta.icon(icon_name, color='#fff'), "")
            b.setObjectName(obj_name)
            b.setToolTip(tip)
            b.setFixedSize(34, 28)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            btn_bar.addWidget(b)
        btn_bar.addStretch()
        sp_layout.addLayout(btn_bar)

        splitter.addWidget(step_panel)

        # 우: 스텝 에디터
        self.step_editor = StepEditorPanel(screen_capture=self.screen_capture)
        self.step_editor.step_changed.connect(self._on_step_edited)
        splitter.addWidget(self.step_editor)

        splitter.setSizes([220, 280])
        builder_layout.addWidget(splitter)

        layout.addWidget(self.builder_area, 1)

    # ── 매크로 관리 ──

    def _load_saved_macros(self):
        """저장된 매크로 로드"""
        SAVED_DIR.mkdir(parents=True, exist_ok=True)

        self.macro_combo.blockSignals(True)
        self.macro_combo.clear()

        # 내장 매크로
        for name in self._builtin_macros:
            self.macro_combo.addItem(qta.icon('mdi.cog', color='#888'), name)
            idx = self.macro_combo.count() - 1
            self.macro_combo.setItemData(idx, "builtin", Qt.UserRole)
            self.macro_combo.setItemData(idx, name, Qt.UserRole + 1)

        # 저장된 스크립트 매크로
        self._scripts.clear()
        for f in sorted(SAVED_DIR.glob("*.yaml")):
            try:
                script = MacroScript.load(str(f))
                self._scripts[script.name] = {"script": script, "path": str(f)}
                self.macro_combo.addItem(qta.icon('mdi.file-document-edit', color='#81C784'), script.name)
                idx = self.macro_combo.count() - 1
                self.macro_combo.setItemData(idx, "script", Qt.UserRole)
                self.macro_combo.setItemData(idx, script.name, Qt.UserRole + 1)
            except Exception as e:
                logger.error(f"매크로 로드 실패: {f} - {e}")

        self.macro_combo.blockSignals(False)

        if self.macro_combo.count() > 0:
            self.macro_combo.setCurrentIndex(0)
            self._on_macro_selected(0)

    @Slot(int)
    def _on_macro_selected(self, index: int):
        if index < 0:
            return
        mtype = self.macro_combo.itemData(index, Qt.UserRole)
        mname = self.macro_combo.itemData(index, Qt.UserRole + 1)

        if mtype == "builtin":
            self._is_builtin = True
            self._current_script = None
            self.builtin_label.setVisible(True)
            self.builder_area.setVisible(False)
            self.name_input.setText(mname)
            self.name_input.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.del_btn.setEnabled(False)
        else:
            self._is_builtin = False
            self.builtin_label.setVisible(False)
            self.builder_area.setVisible(True)
            self.name_input.setEnabled(True)
            self.save_btn.setEnabled(True)
            self.del_btn.setEnabled(True)

            info = self._scripts.get(mname)
            if info:
                self._current_script = info["script"]
                self.name_input.setText(self._current_script.name)
                self._refresh_step_list()
            else:
                self._current_script = None
                self.step_list.clear()
                self.step_editor.clear()

    @Slot()
    def _new_macro(self):
        name, ok = QInputDialog.getText(self, "새 매크로", "매크로 이름:")
        if not ok or not name.strip():
            return
        name = name.strip()

        if name in self._scripts:
            QMessageBox.warning(self, "중복", f"'{name}' 이미 존재합니다")
            return

        script = MacroScript(name=name)
        path = str(SAVED_DIR / f"{name}.yaml")
        script.save(path)
        self._scripts[name] = {"script": script, "path": path}

        self.macro_combo.addItem(qta.icon('mdi.file-document-edit', color='#81C784'), name)
        idx = self.macro_combo.count() - 1
        self.macro_combo.setItemData(idx, "script", Qt.UserRole)
        self.macro_combo.setItemData(idx, name, Qt.UserRole + 1)
        self.macro_combo.setCurrentIndex(idx)

        logger.info(f"새 매크로 생성: {name}")

    @Slot()
    def _save_macro(self):
        if not self._current_script or self._is_builtin:
            return

        new_name = self.name_input.text().strip()
        if new_name:
            self._current_script.name = new_name

        info = None
        for n, i in self._scripts.items():
            if i["script"] is self._current_script:
                info = i
                break

        if info:
            self._current_script.save(info["path"])
            logger.info(f"매크로 저장: {info['path']}")
            self.window().statusBar().showMessage(f"매크로 저장됨: {self._current_script.name}")

    @Slot()
    def _delete_macro(self):
        if self._is_builtin or not self._current_script:
            return

        reply = QMessageBox.question(
            self, "삭제 확인",
            f"'{self._current_script.name}' 매크로를 삭제하시겠습니까?"
        )
        if reply != QMessageBox.Yes:
            return

        # 파일 삭제
        for name, info in list(self._scripts.items()):
            if info["script"] is self._current_script:
                try:
                    os.remove(info["path"])
                except OSError:
                    pass
                del self._scripts[name]
                break

        self._current_script = None
        self._load_saved_macros()

    @Slot()
    def _duplicate_macro(self):
        """현재 매크로를 복사하여 새 매크로 생성"""
        if not self._current_script:
            QMessageBox.warning(self, "복사 불가", "복사할 매크로가 선택되지 않았습니다.")
            return

        base_name = self._current_script.name
        copy_name = f"{base_name} (복사)"
        counter = 2
        while copy_name in self._scripts:
            copy_name = f"{base_name} (복사 {counter})"
            counter += 1

        name, ok = QInputDialog.getText(
            self, "매크로 복사", "새 매크로 이름:",
            text=copy_name
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        if name in self._scripts:
            QMessageBox.warning(self, "중복", f"'{name}' 이미 존재합니다")
            return

        # 스텝 깊은 복사
        copied_steps = [
            MacroStep.from_dict(s.to_dict())
            for s in self._current_script.steps
        ]
        new_script = MacroScript(
            name=name,
            description=self._current_script.description,
            steps=copied_steps,
        )
        path = str(SAVED_DIR / f"{name}.yaml")
        new_script.save(path)
        self._scripts[name] = {"script": new_script, "path": path}

        self.macro_combo.addItem(qta.icon('mdi.file-document-edit', color='#81C784'), name)
        idx = self.macro_combo.count() - 1
        self.macro_combo.setItemData(idx, "script", Qt.UserRole)
        self.macro_combo.setItemData(idx, name, Qt.UserRole + 1)
        self.macro_combo.setCurrentIndex(idx)

        logger.info(f"매크로 복사: {base_name} → {name}")
        self.window().statusBar().showMessage(f"매크로 복사됨: {name}")

    @Slot(str)
    def _on_name_changed(self, text):
        if self._current_script and not self._is_builtin:
            self._current_script.name = text.strip()

    # ── 스텝 관리 ──

    def _refresh_step_list(self):
        """스텝 목록 새로고침"""
        current_row = self.step_list.currentRow()
        self.step_list.blockSignals(True)
        self.step_list.clear()

        if self._current_script:
            for i, step in enumerate(self._current_script.steps):
                item = QListWidgetItem(step.display_text(i + 1))
                icon_info = STEP_TYPE_ICONS.get(step.type)
                if icon_info:
                    item.setIcon(qta.icon(icon_info[0], color=icon_info[1]))
                self.step_list.addItem(item)

        self.step_list.blockSignals(False)

        if self._current_script and 0 <= current_row < len(self._current_script.steps):
            self.step_list.setCurrentRow(current_row)
        elif self._current_script and self._current_script.steps:
            self.step_list.setCurrentRow(len(self._current_script.steps) - 1)

    @Slot(int)
    def _on_step_selected(self, row: int):
        if not self._current_script or row < 0 or row >= len(self._current_script.steps):
            self.step_editor.clear()
            return
        step = self._current_script.steps[row]
        self.step_editor.load_step(step, self._current_script.steps)

    @Slot()
    def _on_step_edited(self):
        """스텝 편집 시 목록 갱신"""
        self._refresh_step_list()

    @Slot()
    def _add_step(self):
        if not self._current_script:
            return
        idx = self.step_list.currentRow() + 1
        if idx <= 0:
            idx = len(self._current_script.steps)
        step = MacroStep(name=f"스텝 {len(self._current_script.steps) + 1}")
        self._current_script.steps.insert(idx, step)
        self._refresh_step_list()
        self.step_list.setCurrentRow(idx)

    @Slot()
    def _copy_step(self):
        if not self._current_script:
            return
        row = self.step_list.currentRow()
        if row < 0:
            return
        import copy
        original = self._current_script.steps[row]
        new_step = copy.deepcopy(original)
        new_step.name = f"{original.name} (복사)"
        self._current_script.steps.insert(row + 1, new_step)
        self._refresh_step_list()
        self.step_list.setCurrentRow(row + 1)

    @Slot()
    def _delete_step(self):
        if not self._current_script:
            return
        row = self.step_list.currentRow()
        if row < 0:
            return
        self._current_script.steps.pop(row)
        self._refresh_step_list()

    @Slot()
    def _move_up(self):
        if not self._current_script:
            return
        row = self.step_list.currentRow()
        if row <= 0:
            return
        steps = self._current_script.steps
        steps[row], steps[row - 1] = steps[row - 1], steps[row]
        self._refresh_step_list()
        self.step_list.setCurrentRow(row - 1)

    @Slot()
    def _move_down(self):
        if not self._current_script:
            return
        row = self.step_list.currentRow()
        steps = self._current_script.steps
        if row < 0 or row >= len(steps) - 1:
            return
        steps[row], steps[row + 1] = steps[row + 1], steps[row]
        self._refresh_step_list()
        self.step_list.setCurrentRow(row + 1)

    # ── 외부 인터페이스 ──

    def get_run_info(self):
        """
        실행 정보 반환

        Returns:
            ("builtin", macro_class) 또는 ("script", MacroScript) 또는 (None, None)
        """
        if self._is_builtin:
            mname = self.macro_combo.currentData(Qt.UserRole + 1)
            cls = self._builtin_macros.get(mname)
            if cls:
                return ("builtin", cls)
        elif self._current_script:
            return ("script", self._current_script)
        return (None, None)

    def is_ready(self) -> bool:
        """실행 가능 여부"""
        rtype, data = self.get_run_info()
        if rtype == "builtin":
            return True
        if rtype == "script" and data and data.steps:
            return True
        return False

    def auto_save_before_run(self):
        """실행 전 자동 저장"""
        if self._current_script and not self._is_builtin:
            self._save_macro()
