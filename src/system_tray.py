"""System tray icon, context menu, and Windows auto-start registration."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

log = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
TRAY_ICON = str(ASSETS_DIR / "tray_icon.png")


class SystemTrayManager:
    """Creates and manages the system-tray icon and its context menu.

    Menu items:
      - 투명도 조절 (25% / 50% / 75% / 100%)
      - 강제 동기화
      - 종료
    """

    def __init__(
        self,
        parent: QWidget,
        *,
        on_sync: callable,
        on_quit: callable,
        on_opacity: callable,
    ):
        self._parent = parent
        self._on_sync = on_sync
        self._on_quit = on_quit
        self._on_opacity = on_opacity

        icon = QIcon(TRAY_ICON) if os.path.exists(TRAY_ICON) else QIcon()
        self._tray = QSystemTrayIcon(icon, parent)
        self._tray.setToolTip("Desktop Calendar Widget")

        self._menu = QMenu()
        self._build_menu()
        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def _build_menu(self) -> None:
        # Opacity submenu
        opacity_menu = self._menu.addMenu("투명도 조절")
        for pct in (25, 50, 75, 100):
            action = QAction(f"{pct}%", self._parent)
            action.triggered.connect(lambda checked, p=pct: self._on_opacity(p / 100))
            opacity_menu.addAction(action)

        # Force sync
        sync_action = QAction("강제 동기화", self._parent)
        sync_action.triggered.connect(self._on_sync)
        self._menu.addAction(sync_action)

        self._menu.addSeparator()

        # Quit
        quit_action = QAction("종료", self._parent)
        quit_action.triggered.connect(self._on_quit)
        self._menu.addAction(quit_action)


# ---------------------------------------------------------------------------
# Windows auto-start helpers
# ---------------------------------------------------------------------------

def register_autostart(app_name: str = "DesktopCalWidget") -> bool:
    """Register this script in the Windows registry for auto-start at login.

    Returns True on success, False on non-Windows or on error.
    """
    if sys.platform != "win32":
        log.info("Auto-start registration skipped (not Windows).")
        return False

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe_path = f'"{sys.executable}" "{Path(__file__).resolve().parent.parent / "main.py"}"'

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)

        log.info("Auto-start registered: %s → %s", app_name, exe_path)
        return True
    except Exception:
        log.warning("Failed to register auto-start", exc_info=True)
        return False


def unregister_autostart(app_name: str = "DesktopCalWidget") -> bool:
    """Remove the auto-start registry entry."""
    if sys.platform != "win32":
        return False

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, app_name)
        log.info("Auto-start entry removed: %s", app_name)
        return True
    except Exception:
        log.warning("Failed to remove auto-start entry", exc_info=True)
        return False
