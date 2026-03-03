"""Pop-up dialog for adding a new Google Calendar event or Task.

Triggered by double-clicking a day cell in the monthly grid.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src import google_service


class AddEventDialog(QDialog):
    """Simple input dialog: type selector, title, optional time, confirm/cancel."""

    def __init__(self, iso_date: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._iso_date = iso_date
        self._accepted = False

        self.setWindowTitle(f"일정 추가 — {iso_date}")
        self.setFixedSize(380, 220)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #2B2B2B;
            }
            QLabel {
                color: #E0E0E0;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            QPushButton {
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton#btnOk {
                background-color: #4FC3F7;
                color: #000;
            }
            QPushButton#btnCancel {
                background-color: #616161;
                color: #E0E0E0;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 16, 20, 16)

        # Title
        header = QLabel(f"📅 {iso_date}")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Type selector
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("유형"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["캘린더 일정", "할 일 (Task)"])
        type_row.addWidget(self._type_combo)
        layout.addLayout(type_row)

        # Title input
        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("제목"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("일정 또는 할 일 제목을 입력하세요")
        title_row.addWidget(self._title_edit)
        layout.addLayout(title_row)

        # Time input (only relevant for calendar events)
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("시간"))
        self._time_edit = QLineEdit()
        self._time_edit.setPlaceholderText("HH:MM (비워두면 종일 일정)")
        self._time_edit.setMaximumWidth(140)
        time_row.addWidget(self._time_edit)
        layout.addLayout(time_row)

        # Toggle time field visibility
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("취소")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("추가")
        btn_ok.setObjectName("btnOk")
        btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    # ---- slots -------------------------------------------------------------

    def _on_type_changed(self, index: int) -> None:
        is_calendar = index == 0
        self._time_edit.setVisible(is_calendar)

    def _on_ok(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "입력 오류", "제목을 입력해 주세요.")
            return

        is_calendar = self._type_combo.currentIndex() == 0
        time_text = self._time_edit.text().strip() or None

        try:
            if is_calendar:
                google_service.create_event(title, self._iso_date, time_text)
            else:
                google_service.create_task(title, self._iso_date)
            self._accepted = True
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "API 오류", f"Google API 호출 실패:\n{exc}")

    @property
    def was_accepted(self) -> bool:
        return self._accepted
