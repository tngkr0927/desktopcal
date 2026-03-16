"""Pop-up dialog for managing events on a specific day.

Shows existing events with delete buttons and a form to add new events.
Triggered by double-clicking a day cell in the monthly grid.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src import google_service

# Shared dark-theme stylesheet
_STYLESHEET = """
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
QComboBox QAbstractItemView {
    background-color: #3C3C3C;
    color: #FFFFFF;
    selection-background-color: #4FC3F7;
    selection-color: #000;
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
QPushButton#btnDelete {
    background-color: #EF5350;
    color: #FFF;
    padding: 2px 10px;
    font-size: 11px;
}
QPushButton#btnDelete:hover {
    background-color: #F44336;
}
QPushButton#btnEdit {
    background-color: #4FC3F7;
    color: #FFFFFF;
    padding: 2px 10px;
    font-size: 11px;
}
QPushButton#btnEdit:hover {
    background-color: #29B6F6;
}
QScrollArea {
    border: none;
    background: transparent;
}
QCheckBox {
    color: #E0E0E0;
    font-size: 11px;
    spacing: 4px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #555;
    border-radius: 3px;
    background-color: #3C3C3C;
}
QCheckBox::indicator:checked {
    background-color: #4FC3F7;
    border-color: #4FC3F7;
}
"""


def _build_time_options() -> list[str]:
    """Generate time options in 5-minute intervals: '', '00:00', '00:05', ... '23:55'."""
    options = [""]  # empty = all-day
    for h in range(24):
        for m in range(0, 60, 5):
            options.append(f"{h:02d}:{m:02d}")
    return options


class AddEventDialog(QDialog):
    """Day event manager: shows existing events with delete, and add-new form."""

    def __init__(
        self,
        iso_date: str,
        existing_events: list[dict[str, Any]] | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._iso_date = iso_date
        self._accepted = False
        self._changed = False
        self._existing = existing_events or []
        self._editing_event: dict[str, Any] | None = None

        self.setWindowTitle(f"일정 관리 — {iso_date}")
        self.setFixedWidth(420)
        self.setStyleSheet(_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 16, 20, 16)

        # Header
        header = QLabel(f"📅 {iso_date}")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # ── Existing events section ──
        if self._existing:
            divider_label = QLabel("기존 일정")
            divider_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            divider_label.setStyleSheet("color: #4FC3F7; border: none;")
            layout.addWidget(divider_label)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(180)
            scroll_content = QWidget()
            scroll_content.setStyleSheet("background: transparent;")
            self._events_layout = QVBoxLayout(scroll_content)
            self._events_layout.setContentsMargins(0, 0, 0, 0)
            self._events_layout.setSpacing(4)

            for ev in self._existing:
                self._add_event_row(ev)

            self._events_layout.addStretch()
            scroll.setWidget(scroll_content)
            layout.addWidget(scroll)

        # ── Separator ──
        self._form_label = QLabel("새 일정 추가")
        self._form_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._form_label.setStyleSheet("color: #4FC3F7; border: none; margin-top: 4px;")
        layout.addWidget(self._form_label)

        # Type selector
        type_row = QHBoxLayout()
        lbl_type = QLabel("유형")
        lbl_type.setFixedWidth(40)
        type_row.addWidget(lbl_type)
        self._type_combo = QComboBox()
        self._type_combo.addItems(["캘린더 일정", "할 일 (Task)"])
        type_row.addWidget(self._type_combo)
        layout.addLayout(type_row)

        # Title input
        title_row = QHBoxLayout()
        lbl_title = QLabel("제목")
        lbl_title.setFixedWidth(40)
        title_row.addWidget(lbl_title)
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("일정 또는 할 일 제목을 입력하세요")
        title_row.addWidget(self._title_edit)
        layout.addLayout(title_row)

        # Time row: label, dropdown, manual check, 종일 check (at end)
        self._time_row = QHBoxLayout()
        self._time_label = QLabel("시간")
        self._time_label.setFixedWidth(40)
        self._time_row.addWidget(self._time_label)

        self._time_combo = QComboBox()
        # Only timed options (no empty/all-day entry)
        self._time_combo.addItems(_build_time_options()[1:])
        self._time_combo.setEditable(False)
        self._time_combo.setMaximumWidth(140)
        self._time_row.addWidget(self._time_combo)

        self._time_edit = QLineEdit()
        self._time_edit.setInputMask("99:99")
        self._time_edit.setMaximumWidth(140)
        self._time_edit.setVisible(False)
        self._time_row.addWidget(self._time_edit)

        self._manual_check = QCheckBox("직접입력")
        self._manual_check.toggled.connect(self._on_manual_toggled)
        self._time_row.addWidget(self._manual_check)

        self._time_row.addStretch()

        self._allday_check = QCheckBox("종일")
        self._allday_check.setChecked(False)
        self._allday_check.toggled.connect(self._on_allday_toggled)
        self._time_row.addWidget(self._allday_check)

        layout.addLayout(self._time_row)

        # Toggle time field visibility
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("닫기")
        btn_cancel.setObjectName("btnCancel")
        btn_cancel.clicked.connect(self._on_close)
        btn_row.addWidget(btn_cancel)

        self._btn_ok = QPushButton("추가")
        self._btn_ok.setObjectName("btnOk")
        self._btn_ok.clicked.connect(self._on_ok)
        btn_row.addWidget(self._btn_ok)
        layout.addLayout(btn_row)

        # Adjust dialog height based on content
        min_h = 300 if not self._existing else 420
        self.setMinimumHeight(min_h)

    def _add_event_row(self, ev: dict[str, Any]) -> None:
        """Add a row for an existing event with summary and delete button."""
        row_widget = QWidget()
        row_widget.setStyleSheet(
            "background-color: rgba(60, 60, 60, 0.8); border-radius: 4px;"
        )
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 4, 8, 4)
        row_layout.setSpacing(8)

        summary_label = QLabel(ev["summary"])
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet("color: #E0E0E0; border: none; background: transparent;")
        summary_label.setFont(QFont("Segoe UI", 10))
        row_layout.addWidget(summary_label, stretch=1)

        btn_edit = QPushButton("수정")
        btn_edit.setObjectName("btnEdit")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setFixedWidth(50)
        btn_edit.clicked.connect(lambda _, e=ev: self._on_edit(e))
        row_layout.addWidget(btn_edit)

        btn_del = QPushButton("삭제")
        btn_del.setObjectName("btnDelete")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setFixedWidth(50)
        btn_del.clicked.connect(lambda _, e=ev, w=row_widget: self._on_delete(e, w))
        row_layout.addWidget(btn_del)

        self._events_layout.addWidget(row_widget)

    # ── Slots ──

    def _on_allday_toggled(self, checked: bool) -> None:
        """Toggle time inputs when 종일 is checked."""
        self._time_combo.setVisible(not checked and not self._manual_check.isChecked())
        self._time_edit.setVisible(not checked and self._manual_check.isChecked())
        self._manual_check.setVisible(not checked)

    def _on_manual_toggled(self, checked: bool) -> None:
        """Switch between dropdown and manual text input for time."""
        allday = self._allday_check.isChecked()
        self._time_combo.setVisible(not checked and not allday)
        self._time_edit.setVisible(checked and not allday)
        if checked and not allday:
            self._time_edit.setFocus()

    def _on_type_changed(self, index: int) -> None:
        is_calendar = index == 0
        allday = self._allday_check.isChecked()
        is_manual = self._manual_check.isChecked()
        self._time_combo.setVisible(is_calendar and not allday and not is_manual)
        self._time_edit.setVisible(is_calendar and not allday and is_manual)
        self._time_label.setVisible(is_calendar)
        self._allday_check.setVisible(is_calendar)
        self._manual_check.setVisible(is_calendar and not allday)

    @staticmethod
    def _parse_summary(summary: str, source: str) -> tuple[str, str]:
        """Extract (title, time_str) from a display summary.

        Timed calendar events look like '[HH:MM] title'.
        Tasks look like '[x] title' or '[ ] title'.
        All-day events have no prefix.
        """
        import re

        if source == "calendar":
            m = re.match(r"^\[(\d{2}:\d{2})\]\s*(.*)$", summary)
            if m:
                return m.group(2), m.group(1)
            # [연속] prefix for multi-day continuation
            m2 = re.match(r"^\[연속\]\s*(.*)$", summary)
            if m2:
                return m2.group(1), ""
        elif source == "tasks":
            m = re.match(r"^\[[ x]\]\s*(.*)$", summary)
            if m:
                return m.group(1), ""

        return summary, ""

    def _on_edit(self, ev: dict[str, Any]) -> None:
        """Populate the form with the event data for editing."""
        self._editing_event = ev
        self._form_label.setText("일정 수정")
        self._btn_ok.setText("수정")

        title, time_str = self._parse_summary(ev["summary"], ev["source"])

        # Fill title
        self._title_edit.setText(title)

        # Set type
        if ev["source"] == "tasks":
            self._type_combo.setCurrentIndex(1)
        else:
            self._type_combo.setCurrentIndex(0)
            if time_str:
                self._allday_check.setChecked(False)
                # Try to find the time in the combo box first
                idx = self._time_combo.findText(time_str)
                if idx >= 0:
                    self._manual_check.setChecked(False)
                    self._time_combo.setCurrentIndex(idx)
                else:
                    self._manual_check.setChecked(True)
                    self._time_edit.setText(time_str)
            else:
                self._allday_check.setChecked(True)
                self._manual_check.setChecked(False)

        self._title_edit.setFocus()

    def _cancel_edit(self) -> None:
        """Reset form back to add mode."""
        self._editing_event = None
        self._form_label.setText("새 일정 추가")
        self._btn_ok.setText("추가")
        self._title_edit.clear()
        self._type_combo.setCurrentIndex(0)
        self._allday_check.setChecked(False)
        self._time_combo.setCurrentIndex(0)
        self._manual_check.setChecked(False)
        self._time_edit.clear()

    def _on_delete(self, ev: dict[str, Any], row_widget: QWidget) -> None:
        """Delete an event after confirmation."""
        msg = QMessageBox(self)
        msg.setWindowTitle("일정 삭제")
        msg.setText(f"'{ev['summary']}' 을(를) 삭제하시겠습니까?")
        msg.setIcon(QMessageBox.Icon.Question)

        btn_yes = msg.addButton("네", QMessageBox.ButtonRole.YesRole)
        btn_no = msg.addButton("아니요", QMessageBox.ButtonRole.NoRole)
        msg.setDefaultButton(btn_no)

        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2B2B2B;
            }
            QMessageBox QLabel {
                color: #FFFFFF;
                font-size: 13px;
            }
            QPushButton {
                border-radius: 4px;
                padding: 6px 20px;
                font-size: 12px;
                font-weight: bold;
                min-width: 70px;
            }
        """)
        btn_yes.setStyleSheet("background-color: #EF5350; color: #FFFFFF;")
        btn_no.setStyleSheet("background-color: #616161; color: #FFFFFF;")
        btn_yes.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_no.setCursor(Qt.CursorShape.PointingHandCursor)

        msg.exec()
        if msg.clickedButton() != btn_yes:
            return

        try:
            if ev["source"] == "calendar":
                google_service.delete_event(ev["id"])
            else:
                google_service.delete_task(ev["id"])
            row_widget.setParent(None)
            row_widget.deleteLater()
            self._changed = True
        except Exception as exc:
            QMessageBox.critical(self, "API 오류", f"삭제 실패:\n{exc}")

    def _on_ok(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "입력 오류", "제목을 입력해 주세요.")
            return

        is_calendar = self._type_combo.currentIndex() == 0
        time_text = None
        if is_calendar and not self._allday_check.isChecked():
            if self._manual_check.isChecked():
                time_text = self._time_edit.text().strip() or None
            else:
                time_text = self._time_combo.currentText()

        try:
            if self._editing_event:
                ev = self._editing_event
                if ev["source"] == "calendar":
                    google_service.update_event(ev["id"], title, self._iso_date, time_text)
                else:
                    google_service.update_task(ev["id"], title, self._iso_date)
                self._changed = True
                self._cancel_edit()
                self.accept()
            else:
                if is_calendar:
                    google_service.create_event(title, self._iso_date, time_text)
                else:
                    google_service.create_task(title, self._iso_date)
                self._accepted = True
                self._changed = True
                self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "API 오류", f"Google API 호출 실패:\n{exc}")

    def _on_close(self) -> None:
        if self._changed:
            self.accept()
        else:
            self.reject()

    @property
    def was_accepted(self) -> bool:
        return self._changed or self._accepted
