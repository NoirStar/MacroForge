"""
인앱 템플릿 캡처 다이얼로그
스크린샷 위에 마우스로 영역 선택 → 템플릿 이미지 저장
"""

import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

import cv2
import numpy as np

import qtawesome as qta


class ScreenshotLabel(QLabel):
    """마우스 드래그로 영역 선택 가능한 스크린샷 라벨"""

    def __init__(self):
        super().__init__()
        self._base_pixmap = None
        self._start = None
        self._end = None
        self._scale = 1.0
        self._original_size = (0, 0)

    def set_screenshot(self, rgb_array: np.ndarray, max_w: int = 800, max_h: int = 600):
        h, w = rgb_array.shape[:2]
        self._scale = min(max_w / w, max_h / h, 1.0)
        dw, dh = int(w * self._scale), int(h * self._scale)

        resized = cv2.resize(rgb_array, (dw, dh))
        qimg = QImage(resized.data.tobytes(), dw, dh, dw * 3, QImage.Format_RGB888)
        self._base_pixmap = QPixmap.fromImage(qimg)
        self._original_size = (w, h)
        self._start = None
        self._end = None
        self.setPixmap(self._base_pixmap)
        self.setFixedSize(dw, dh)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = e.pos()
            self._end = e.pos()

    def mouseMoveEvent(self, e):
        if self._start and e.buttons() & Qt.LeftButton:
            self._end = e.pos()
            self._draw_rect()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._start:
            self._end = e.pos()
            self._draw_rect()

    def _draw_rect(self):
        if not self._base_pixmap or not self._start or not self._end:
            return
        pm = self._base_pixmap.copy()
        painter = QPainter(pm)
        painter.setPen(QPen(QColor(0, 255, 0), 2))
        rect = QRect(self._start, self._end).normalized()
        painter.drawRect(rect)
        # 크기 표시
        ow = int(rect.width() / self._scale)
        oh = int(rect.height() / self._scale)
        painter.setPen(QColor(255, 255, 0))
        painter.drawText(rect.topLeft() + QPoint(4, -4), f"{ow}×{oh}")
        painter.end()
        self.setPixmap(pm)

    def get_selection_original(self):
        """원본 이미지 좌표로 선택 영역 반환"""
        if not self._start or not self._end:
            return None
        rect = QRect(self._start, self._end).normalized()
        x1 = int(rect.x() / self._scale)
        y1 = int(rect.y() / self._scale)
        x2 = int(rect.right() / self._scale)
        y2 = int(rect.bottom() / self._scale)
        if x2 - x1 < 5 or y2 - y1 < 5:
            return None
        ow, oh = self._original_size
        x1, x2 = max(0, x1), min(ow, x2)
        y1, y2 = max(0, y1), min(oh, y2)
        return (x1, y1, x2, y2)


class CaptureDialog(QDialog):
    """템플릿 캡처 다이얼로그"""

    def __init__(self, screenshot_bgr: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle("템플릿 캡처")
        self.setWindowIcon(qta.icon('mdi.camera', color='#CE93D8'))
        self.setMinimumSize(640, 500)
        self._bgr = screenshot_bgr
        self._rgb = screenshot_bgr[:, :, ::-1].copy()
        self._saved_path = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel("마우스로 드래그하여 템플릿 영역을 선택하세요")
        info.setStyleSheet("font-size: 13px; padding: 4px;")
        layout.addWidget(info)

        # 스크롤 영역 (큰 스크린샷용)
        scroll = QScrollArea()
        self.screenshot_label = ScreenshotLabel()
        self.screenshot_label.set_screenshot(self._rgb)
        scroll.setWidget(self.screenshot_label)
        scroll.setWidgetResizable(False)
        layout.addWidget(scroll, 1)

        # 파일명 입력
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("파일명:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: menu_button")
        name_row.addWidget(self.name_input, 1)
        name_row.addWidget(QLabel(".png"))
        layout.addLayout(name_row)

        # 버튼
        btn_row = QHBoxLayout()
        save_btn = QPushButton(qta.icon('mdi.content-save', color='#4FC3F7'), " 저장")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_save(self):
        sel = self.screenshot_label.get_selection_original()
        if not sel:
            QMessageBox.warning(self, "오류", "영역을 드래그로 선택하세요")
            return

        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "오류", "파일명을 입력하세요")
            return

        x1, y1, x2, y2 = sel
        crop = self._bgr[y1:y2, x1:x2]

        save_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets", "templates"
        )
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, f"{name}.png")

        cv2.imwrite(path, crop)
        self._saved_path = path
        self.accept()

    @property
    def saved_path(self) -> str:
        return self._saved_path or ""
