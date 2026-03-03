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

from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Day-of-week header labels (Monday-first)
DAY_HEADERS = ["월", "화", "수", "목", "금", "토", "일"]


class DayCell(QFrame):
    """A single day cell inside the monthly grid.

    Displays the day number and a list of event/task summaries.
    Emits *double_clicked* with the ISO date string on double-click.
    """

    double_clicked = pyqtSignal(str)  # ISO date string

    def __init__(self, iso_date: str, day: int, items: list[str], is_today: bool = False):
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

        # Day number
        day_label = QLabel(str(day))
        day_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        color = "#4FC3F7" if is_today else "#E0E0E0"
        day_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        layout.addWidget(day_label)

        # Event/task lines
        for text in items:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setFont(QFont("Segoe UI", 8))
            lbl.setStyleSheet("color: #CCCCCC; background: transparent; border: none;")
            layout.addWidget(lbl)

        layout.addStretch()

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


class MonthlyCalendarWidget(QWidget):
    """Full monthly calendar grid.

    Signals:
        date_double_clicked(str): Emitted when a day cell is double-clicked.
    """

    date_double_clicked = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._year = date.today().year
        self._month = date.today().month
        self._events: list[dict[str, Any]] = []
        self._grid: QGridLayout | None = None
        self._init_ui()

    # ---- public API --------------------------------------------------------

    @property
    def year(self) -> int:
        return self._year

    @property
    def month(self) -> int:
        return self._month

    def set_month(self, year: int, month: int) -> None:
        self._year = year
        self._month = month
        self._rebuild()

    def set_events(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self._rebuild()

    def go_prev(self) -> None:
        if self._month == 1:
            self._year -= 1
            self._month = 12
        else:
            self._month -= 1
        self._rebuild()

    def go_next(self) -> None:
        if self._month == 12:
            self._year += 1
            self._month = 1
        else:
            self._month += 1
        self._rebuild()

    # ---- internal ----------------------------------------------------------

    def _init_ui(self) -> None:
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        # Header row: ◀  2026년 3월  ▶
        header = QWidget()
        h_layout = QGridLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)

        self._btn_prev = QLabel("◀")
        self._btn_prev.setFont(QFont("Segoe UI", 14))
        self._btn_prev.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.mousePressEvent = lambda _: (self.go_prev(), self.date_double_clicked.emit("__nav__"))

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #FFFFFF; background: transparent;")

        self._btn_next = QLabel("▶")
        self._btn_next.setFont(QFont("Segoe UI", 14))
        self._btn_next.setStyleSheet("color: #FFFFFF; background: transparent;")
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.mousePressEvent = lambda _: (self.go_next(), self.date_double_clicked.emit("__nav__"))

        h_layout.addWidget(self._btn_prev, 0, 0, Qt.AlignmentFlag.AlignLeft)
        h_layout.addWidget(self._title, 0, 1, Qt.AlignmentFlag.AlignCenter)
        h_layout.addWidget(self._btn_next, 0, 2, Qt.AlignmentFlag.AlignRight)

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
            color = "#FF8A80" if col >= 5 else "#B0BEC5"
            lbl.setStyleSheet(f"color: {color}; background: transparent;")
            dow_layout.addWidget(lbl, 0, col)
        self._outer.addWidget(dow_widget)

        # Grid container
        self._grid_container = QWidget()
        self._outer.addWidget(self._grid_container, stretch=1)

        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the day-cell grid for the current year/month."""
        self._title.setText(f"{self._year}년 {self._month}월")

        # Clear old grid
        if self._grid is not None:
            while self._grid.count():
                item = self._grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            self._grid = QGridLayout(self._grid_container)
            self._grid.setSpacing(4)
            self._grid.setContentsMargins(0, 0, 0, 0)

        # Build date→items mapping
        items_by_date: dict[str, list[str]] = defaultdict(list)
        for ev in self._events:
            items_by_date[ev["date"]].append(ev["summary"])

        today = date.today()
        cal = calendar.Calendar(firstweekday=0)  # Monday first
        weeks = cal.monthdayscalendar(self._year, self._month)

        for row, week in enumerate(weeks):
            for col, day in enumerate(week):
                if day == 0:
                    cell = EmptyCell()
                else:
                    iso = f"{self._year}-{self._month:02d}-{day:02d}"
                    is_today = (self._year == today.year and self._month == today.month and day == today.day)
                    cell = DayCell(iso, day, items_by_date.get(iso, []), is_today)
                    cell.double_clicked.connect(self.date_double_clicked)
                self._grid.addWidget(cell, row, col)
