"""Desktop Calendar Widget — main entry point.

Launches a frameless, transparent PyQt6 window showing a monthly calendar
grid with live Google Calendar & Tasks data.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPainterPath, QPen
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

# Debounce delay for navigation sync (milliseconds).
NAV_SYNC_DELAY_MS = 500

# Edge resize grip size (pixels).
RESIZE_MARGIN = 6

# Minimum window size.
MIN_WIDTH, MIN_HEIGHT = 400, 400

# Geometry persistence file.
_GEOMETRY_PATH = Path(__file__).resolve().parent / ".window_geometry.json"


class _SyncWorker(QThread):
    """Runs Google API fetch in a background thread."""

    done = pyqtSignal(int, int, list)  # year, month, events

    def __init__(self, year: int, month: int, parent=None):
        super().__init__(parent)
        self._year = year
        self._month = month

    def run(self):
        try:
            events = google_service.fetch_all(self._year, self._month)
        except Exception:
            log.warning("Sync failed for %d-%02d", self._year, self._month, exc_info=True)
            events = []
        self.done.emit(self._year, self._month, events)


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
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setMouseTracking(True)
        self.resize(820, 660)

        # Dragging / resizing state
        self._drag_pos: QPoint | None = None
        self._resize_edge: str | None = None
        self._resize_origin_geo: QRect | None = None

        # Sync state
        self._sync_worker: _SyncWorker | None = None

        # Navigation debounce timer
        self._nav_timer = QTimer(self)
        self._nav_timer.setSingleShot(True)
        self._nav_timer.timeout.connect(self._sync)

        # ── Layout ────────────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN)

        self._calendar = MonthlyCalendarWidget(self)
        self._calendar.date_double_clicked.connect(self._on_date_action)
        self._calendar.nav_clicked.connect(self._on_nav)
        self._calendar.close_clicked.connect(self._quit)
        root.addWidget(self._calendar)

        # ── System tray ──────────────────────────────────────────────────────
        self._tray = SystemTrayManager(
            self,
            on_sync=self._sync,
            on_quit=self._quit,
            on_opacity=self._set_opacity,
        )

        # ── Restore saved geometry ────────────────────────────────────────────
        self._load_geometry()

        # ── Initial data load ────────────────────────────────────────────────
        self._sync()

        # ── Periodic auto-sync ───────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sync)
        self._timer.start(SYNC_INTERVAL_MS)

    # ── Paint background so edges receive mouse events ────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw a rounded-rect background covering the whole window.
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 8.0, 8.0)
        painter.fillPath(path, QBrush(QColor(20, 20, 20, 170)))

        # Subtle border
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
        painter.drawPath(path)
        painter.end()

    # ── Geometry persistence ──────────────────────────────────────────────────

    def _save_geometry(self) -> None:
        geo = self.geometry()
        data = {"x": geo.x(), "y": geo.y(), "w": geo.width(), "h": geo.height()}
        try:
            _GEOMETRY_PATH.write_text(json.dumps(data))
        except Exception:
            log.warning("Failed to save geometry", exc_info=True)

    def _load_geometry(self) -> None:
        try:
            if _GEOMETRY_PATH.exists():
                data = json.loads(_GEOMETRY_PATH.read_text())
                self.setGeometry(data["x"], data["y"], data["w"], data["h"])
                log.info("Restored window geometry: %s", data)
        except Exception:
            log.warning("Failed to load geometry", exc_info=True)

    # ── Data sync (threaded) ──────────────────────────────────────────────────

    def _sync(self) -> None:
        """Fetch events+tasks for the currently displayed month in background."""
        if self._sync_worker is not None and self._sync_worker.isRunning():
            log.info("Sync already in progress — skipping")
            return

        year, month = self._calendar.year, self._calendar.month
        log.info("Syncing %d-%02d …", year, month)

        worker = _SyncWorker(year, month, self)
        worker.done.connect(self._on_sync_done)
        self._sync_worker = worker
        worker.start()

    def _on_sync_done(self, year: int, month: int, events: list) -> None:
        # Only apply if the user hasn't navigated away
        if self._calendar.year == year and self._calendar.month == month:
            self._calendar.set_events(events)
            log.info("Loaded %d items for %d-%02d", len(events), year, month)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_nav(self) -> None:
        """Debounce sync after navigation."""
        self._nav_timer.start(NAV_SYNC_DELAY_MS)

    def _on_date_action(self, iso_date: str) -> None:
        """Handle double-click on a day cell."""
        # Gather existing events for this date
        existing = [e for e in self._calendar.events if e["date"] == iso_date]
        dialog = AddEventDialog(iso_date, existing_events=existing, parent=self)
        dialog.exec()
        if dialog.was_accepted:
            self._sync()

    def _set_opacity(self, value: float) -> None:
        self.setWindowOpacity(value)

    def _quit(self) -> None:
        self._save_geometry()
        QApplication.instance().quit()

    # ── Edge detection for resize ─────────────────────────────────────────────

    def _edge_at(self, pos: QPoint) -> str | None:
        """Return edge/corner identifier if pos is within the resize margin."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = RESIZE_MARGIN

        on_left = x < m
        on_right = x > w - m
        on_top = y < m
        on_bottom = y > h - m

        if on_top and on_left:
            return "top-left"
        if on_top and on_right:
            return "top-right"
        if on_bottom and on_left:
            return "bottom-left"
        if on_bottom and on_right:
            return "bottom-right"
        if on_left:
            return "left"
        if on_right:
            return "right"
        if on_top:
            return "top"
        if on_bottom:
            return "bottom"
        return None

    # ── Mouse events: drag + resize ──────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if not event or event.button() != Qt.MouseButton.LeftButton:
            return

        edge = self._edge_at(event.position().toPoint())
        if edge:
            self._resize_edge = edge
            self._drag_pos = event.globalPosition().toPoint()
            self._resize_origin_geo = self.geometry()
        else:
            self._resize_edge = None
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if not event:
            return

        if not (event.buttons() & Qt.MouseButton.LeftButton):
            # Update cursor shape on hover
            edge = self._edge_at(event.position().toPoint())
            cursor_map = {
                "left": Qt.CursorShape.SizeHorCursor,
                "right": Qt.CursorShape.SizeHorCursor,
                "top": Qt.CursorShape.SizeVerCursor,
                "bottom": Qt.CursorShape.SizeVerCursor,
                "top-left": Qt.CursorShape.SizeFDiagCursor,
                "bottom-right": Qt.CursorShape.SizeFDiagCursor,
                "top-right": Qt.CursorShape.SizeBDiagCursor,
                "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursor_map.get(edge, Qt.CursorShape.ArrowCursor))
            return

        if self._drag_pos is None:
            return

        if self._resize_edge:
            self._handle_resize(event.globalPosition().toPoint())
        else:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _handle_resize(self, global_pos: QPoint) -> None:
        dx = global_pos.x() - self._drag_pos.x()
        dy = global_pos.y() - self._drag_pos.y()
        geo = self._resize_origin_geo
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()

        edge = self._resize_edge
        if "right" in edge:
            w = max(MIN_WIDTH, geo.width() + dx)
        if "bottom" in edge:
            h = max(MIN_HEIGHT, geo.height() + dy)
        if "left" in edge:
            new_w = max(MIN_WIDTH, geo.width() - dx)
            x = geo.x() + geo.width() - new_w
            w = new_w
        if "top" in edge:
            new_h = max(MIN_HEIGHT, geo.height() - dy)
            y = geo.y() + geo.height() - new_h
            h = new_h

        self.setGeometry(x, y, w, h)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if self._resize_edge is not None:
            self._save_geometry()
        self._drag_pos = None
        self._resize_edge = None
        self._resize_origin_geo = None

    # ── Close event ──────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)


def main() -> None:
    # Optional: register for Windows auto-start
    register_autostart()

    # Allow Ctrl+C in the terminal to quit the app
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # keep running in tray

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
