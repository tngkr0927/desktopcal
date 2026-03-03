"""Desktop Calendar Widget — main entry point.

Launches a frameless, transparent PyQt6 window showing a monthly calendar
grid with live Google Calendar & Tasks data.
"""

from __future__ import annotations

import logging
import sys
from datetime import date

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src import google_service
from src.add_event_dialog import AddEventDialog
from src.calendar_widget import MonthlyCalendarWidget
from src.system_tray import SystemTrayManager, register_autostart

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

# Auto-sync interval (milliseconds).  Default: 10 minutes.
SYNC_INTERVAL_MS = 10 * 60 * 1000


class MainWindow(QWidget):
    """Top-level frameless, transparent window containing the calendar grid."""

    def __init__(self) -> None:
        super().__init__()

        # ── Window flags: frameless, always on bottom (desktop), transparent ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnBottomHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Desktop Calendar Widget")
        self.resize(820, 660)

        # Dragging state
        self._drag_pos: QPoint | None = None

        # ── Layout ────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        self._calendar = MonthlyCalendarWidget(self)
        self._calendar.date_double_clicked.connect(self._on_date_action)
        root.addWidget(self._calendar)

        # ── System tray ──────────────────────────────────────────────────────
        self._tray = SystemTrayManager(
            self,
            on_sync=self._sync,
            on_quit=self._quit,
            on_opacity=self._set_opacity,
        )

        # ── Initial data load ────────────────────────────────────────────────
        self._sync()

        # ── Periodic auto-sync ───────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sync)
        self._timer.start(SYNC_INTERVAL_MS)

    # ── Data sync ────────────────────────────────────────────────────────────

    def _sync(self) -> None:
        """Fetch events+tasks for the currently displayed month."""
        year, month = self._calendar.year, self._calendar.month
        log.info("Syncing %d-%02d …", year, month)
        events = google_service.fetch_all(year, month)
        self._calendar.set_events(events)
        log.info("Loaded %d items for %d-%02d", len(events), year, month)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_date_action(self, iso_date: str) -> None:
        """Handle double-click on a day cell (or navigation)."""
        if iso_date == "__nav__":
            self._sync()
            return
        dialog = AddEventDialog(iso_date, self)
        dialog.exec()
        if dialog.was_accepted:
            self._sync()

    def _set_opacity(self, value: float) -> None:
        self.setWindowOpacity(value)

    def _quit(self) -> None:
        QApplication.instance().quit()

    # ── Dragging ─────────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event and event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event and self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        self._drag_pos = None


def main() -> None:
    # Optional: register for Windows auto-start
    register_autostart()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running in tray

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
