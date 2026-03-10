"""Monthly calendar grid widget (PyQt6).

Renders a 7-column (Mon–Sun) grid where each cell shows the day number
and the raw text of all Google Calendar events / Tasks for that day.
The widget is frameless, transparent, and draggable.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.holidays import get_holidays

# Day-of-week header labels (Sunday-first)
DAY_HEADERS = ["일", "월", "화", "수", "목", "금", "토"]


class DayCell(QFrame):
    """A single day cell inside the monthly grid.

    Displays the day number and a list of event/task summaries.
    Emits *double_clicked* with the ISO date string on double-click.
    """

    double_clicked = pyqtSignal(str)  # ISO date string

    def __init__(
        self,
        iso_date: str,
        day: int,
        items: list[str],
        is_today: bool = False,
        is_sunday: bool = False,
        holiday_name: str | None = None,
    ):
        super().__init__()
        self._iso_date = iso_date
        self.setFrameShape(QFrame.Shape.Box)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(90)

        border_color = "#4FC3F7" if is_today else "rgba(255,255,255,0.15)"
        self.setStyleSheet(
            f"""
            DayCell {{
                border: 1px solid {border_color};
                border-radius: 4px;
                background-color: rgba(30, 30, 30, 0.65);
                padding: 2px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        # Day number — red for Sundays and holidays
        is_red = is_sunday or holiday_name is not None
        day_label = QLabel(str(day))
        day_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        if is_today:
            color = "#4FC3F7"
        elif is_red:
            color = "#FF6B6B"
        else:
            color = "#E0E0E0"
        day_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        layout.addWidget(day_label)

        # Holiday name
        if holiday_name:
            h_lbl = QLabel(holiday_name)
            h_lbl.setFont(QFont("Segoe UI", 7))
            h_lbl.setStyleSheet("color: #FF8A80; background: transparent; border: none;")
            layout.addWidget(h_lbl)

        # Event/task lines
        for text in items:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setFont(QFont("Segoe UI", 8))
            lbl.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
            layout.addWidget(lbl)

        layout.addStretch()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.MiddleButton:
            event.ignore()  # Pass to parent for window drag
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:
        self.double_clicked.emit(self._iso_date)


class EmptyCell(QFrame):
    """Blank cell for days outside the current month."""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(90)
        self.setStyleSheet(
            "background-color: rgba(20, 20, 20, 0.35); border: 1px solid rgba(255,255,255,0.05); border-radius: 4px;"
        )

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.MiddleButton:
            event.ignore()
            return
        super().mousePressEvent(event)


class MonthlyCalendarWidget(QWidget):
    """Full monthly calendar grid.

    Signals:
        date_double_clicked(str): Emitted when a day cell is double-clicked.
        nav_clicked(): Emitted when prev/next month buttons are clicked.
    """

    date_double_clicked = pyqtSignal(str)
    nav_clicked = pyqtSignal()
    close_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._year = date.today().year
        self._month = date.today().month
        self._events: list[dict[str, Any]] = []
        self._grid: QGridLayout | None = None
        self._rebuilding = False
        self._cells: list[QWidget] = []
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._init_ui()

    # ---- public API --------------------------------------------------------

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    @property
    def events(self) -> list[dict[str, Any]]:
        return self._events

    def set_month(self, year: int, month: int) -> None:
        self._year = year
        self._month = month
        self._rebuild()

    def set_events(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self._rebuild()

    def go_prev(self) -> None:
        if self._rebuilding:
            return
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1

    def go_next(self) -> None:
        if self._rebuilding:
            return
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.MiddleButton:
            event.ignore()
            return
        super().mousePressEvent(event)

    # ---- internal ----------------------------------------------------------

    def _init_ui(self) -> None:
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        # Header row: ◀  2026년 3월  ▶
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(4, 0, 4, 0)

        btn_style = """
            QPushButton {
                color: #FFFFFF; background: transparent; border: none;
                font-size: 14px; padding: 4px 12px;
            }
            QPushButton:hover { color: #4FC3F7; }
        """

        self._btn_prev = QPushButton("◀")
        self._btn_prev.setStyleSheet(btn_style)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.clicked.connect(self._on_prev)

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #FFFFFF; background: transparent;")

        self._btn_next = QPushButton("▶")
        self._btn_next.setStyleSheet(btn_style)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.clicked.connect(self._on_next)

        close_style = """
            QPushButton {
                color: #888888; background: transparent; border: none;
                font-size: 14px; padding: 4px 8px;
            }
            QPushButton:hover { color: #FF5252; }
        """
        self._btn_close = QPushButton("✕")
        self._btn_close.setStyleSheet(close_style)
        self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_close.clicked.connect(self.close_clicked)

        h_layout.addWidget(self._btn_prev)
        h_layout.addStretch()
        h_layout.addWidget(self._title)
        h_layout.addStretch()
        h_layout.addWidget(self._btn_next)
        h_layout.addWidget(self._btn_close)

        self._outer.addWidget(header)

        # Day-of-week headers
        dow_widget = QWidget()
        dow_layout = QGridLayout(dow_widget)
        dow_layout.setContentsMargins(0, 0, 0, 0)
        dow_layout.setSpacing(4)
        for col, name in enumerate(DAY_HEADERS):
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            # Sunday (col 0) and Saturday (col 6) in red
            color = "#FF8A80" if col == 0 or col == 6 else "#B0BEC5"
            lbl.setStyleSheet(f"color: {color}; background: transparent;")
            dow_layout.addWidget(lbl, 0, col)
        self._outer.addWidget(dow_widget)

        # Grid container
        self._grid_container = QWidget()
        self._outer.addWidget(self._grid_container, stretch=1)

        self._rebuild()

    def _on_prev(self) -> None:
        self.go_prev()
        self.nav_clicked.emit()

    def _on_next(self) -> None:
        self.go_next()
        self.nav_clicked.emit()

    def _rebuild(self) -> None:
        """Rebuild the day-cell grid for the current year/month."""
        if self._rebuilding:
            return
        self._rebuilding = True

        try:
            self._title.setText(f"{self._year}년 {self._month}월")

            # Destroy old cells immediately (not deleteLater)
            for cell in self._cells:
                cell.setParent(None)
                cell.deleteLater()
            self._cells.clear()

            # Create grid layout if first time
            if self._grid is None:
                self._grid = QGridLayout(self._grid_container)
                self._grid.setSpacing(4)
                self._grid.setContentsMargins(0, 0, 0, 0)

            # Build date→items mapping
            items_by_date: dict[str, list[str]] = defaultdict(list)
            for ev in self._events:
                items_by_date[ev["date"]].append(ev["summary"])

            today = date.today()
            holidays = get_holidays(self._year, self._month)
            cal = calendar.Calendar(firstweekday=6)  # Sunday first
            weeks = cal.monthdayscalendar(self._year, self._month)

            for row, week in enumerate(weeks):
                for col, day in enumerate(week):
                    if day == 0:
                        cell = EmptyCell()
                    else:
                        iso = f"{self._year}-{self._month:02d}-{day:02d}"
                        is_today = (self._year == today.year and self._month == today.month and day == today.day)
                        is_sunday = col == 0  # Sunday-first layout
                        holiday_name = holidays.get(day)
                        cell = DayCell(
                            iso, day, items_by_date.get(iso, []),
                            is_today=is_today,
                            is_sunday=is_sunday,
                            holiday_name=holiday_name,
                        )
                        cell.double_clicked.connect(self.date_double_clicked)
                    self._cells.append(cell)
                    self._grid.addWidget(cell, row, col)
        finally:
            self._rebuilding = False
