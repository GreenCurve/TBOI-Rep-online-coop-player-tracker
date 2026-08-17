"""
The overlay window.

Key trick: Windows gets a special "does not steal focus" style
(WS_EX_NOACTIVATE) applied to it after it's created. That means you can
click its buttons and it will show/scroll/etc, but the OS never makes it
the foreground window - so the game keeps thinking it's focused and never
pauses or minimizes. This is the same trick overlays like RTSS/MSI
Afterburner or old-school Discord overlays use.

Toggle it with a global hotkey (default F9, see config.py) that works even
while the game has focus.
"""

import sys
import threading

from PyQt6 import QtCore, QtGui, QtWidgets

import win32gui
import win32con
import win32api

import keyboard  # global hotkey hook, works while another app is focused

import Setup
import db


WS_EX_NOACTIVATE = 0x08000000


def make_noactivate(hwnd: int):
    """Apply WS_EX_NOACTIVATE + WS_EX_TOOLWINDOW so this window never steals
    focus from the game and never shows in alt-tab."""
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    ex_style |= WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
    # keep it above the (borderless-windowed) game without becoming active
    win32gui.SetWindowPos(
        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
    )


class PlayerRow(QtWidgets.QFrame):
    def __init__(self, steam_id, username, parent=None):
        super().__init__(parent)
        self.steam_id = steam_id
        self.setStyleSheet(
            "PlayerRow { background: rgba(30,30,30,180); border-radius: 6px; }"
            "QLabel { color: white; }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)

        top = QtWidgets.QHBoxLayout()
        name_lbl = QtWidgets.QLabel(f"<b>{username}</b>  <span style='color:#999'>({steam_id})</span>")
        top.addWidget(name_lbl)
        top.addStretch()

        add_btn = QtWidgets.QToolButton()
        add_btn.setText("+ tag")
        add_btn.clicked.connect(self.show_tag_menu)
        top.addWidget(add_btn)
        layout.addLayout(top)

        self.tags_layout = QtWidgets.QHBoxLayout()
        self.tags_layout.setSpacing(4)
        layout.addLayout(self.tags_layout)

        self.refresh_tags()

    def refresh_tags(self):
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for tag in db.get_tags_for_player(self.steam_id):
            chip = QtWidgets.QToolButton()
            chip.setText(f"{tag}  ✕")
            chip.setStyleSheet(
                "QToolButton { background: #3a6ea5; color: white; border-radius: 8px; padding: 2px 8px; }"
            )
            chip.clicked.connect(lambda _=False, t=tag: self.remove_tag(t))
            self.tags_layout.addWidget(chip)
        self.tags_layout.addStretch()

    def remove_tag(self, tag):
        db.remove_tag_from_player(self.steam_id, tag)
        self.refresh_tags()

    def show_tag_menu(self):
        menu = QtWidgets.QMenu(self)
        existing = set(db.get_tags_for_player(self.steam_id))
        for tag in db.list_tags():
            if tag in existing:
                continue
            action = menu.addAction(tag)
            action.triggered.connect(lambda _=False, t=tag: self.add_tag(t))
        menu.addSeparator()
        new_action = menu.addAction("New tag…")
        new_action.triggered.connect(self.create_and_add_tag)
        menu.exec(QtGui.QCursor.pos())

    def add_tag(self, tag):
        db.add_tag_to_player(self.steam_id, tag)
        self.refresh_tags()

    def create_and_add_tag(self):
        text, ok = QtWidgets.QInputDialog.getText(self, "New tag", "Tag name:")
        if ok and text.strip():
            tag = text.strip()
            db.create_tag(tag)
            db.add_tag_to_player(self.steam_id, tag)
            self.refresh_tags()


class Overlay(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(360, 420)
        self.move(60, 60)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QtWidgets.QFrame()
        container.setStyleSheet(
            "QFrame { background: rgba(15,15,15,215); border-radius: 10px; }"
        )
        outer.addWidget(container)
        inner = QtWidgets.QVBoxLayout(container)

        title = QtWidgets.QLabel("Current Lobby")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        inner.addWidget(title)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.list_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_widget)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_widget)
        inner.addWidget(self.scroll)

        hint = QtWidgets.QLabel(f"Toggle with {Setup.HOTKEY.upper()} · drag titlebar-free window with Alt+drag")
        hint.setStyleSheet("color: #888; font-size: 10px;")
        inner.addWidget(hint)

        self._rows = {}
        self._drag_pos = None

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    # -- allow dragging the borderless window around -----------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # -- data refresh --------------------------------------------------------
    def refresh(self):
        members = db.get_current_lobby_members()
        local_id = db.get_state("local_steam_id")
        current_ids = set()
        for lobby_id, steam_id, username, joined_at in members:
            if steam_id == local_id:
                continue
            current_ids.add(steam_id)
            if steam_id not in self._rows:
                row = PlayerRow(steam_id, username)
                self._rows[steam_id] = row
                self.list_layout.insertWidget(self.list_layout.count() - 1, row)
            else:
                self._rows[steam_id].refresh_tags()

        for steam_id in list(self._rows.keys()):
            if steam_id not in current_ids:
                self._rows[steam_id].deleteLater()
                del self._rows[steam_id]

        if not members:
            pass  # (left empty; could show "no one else in your lobby yet")

    # -- apply the win32 no-activate style once the native handle exists ----
    def showEvent(self, event):
        super().showEvent(event)
        hwnd = int(self.winId())
        make_noactivate(hwnd)


class _HotkeyBridge(QtCore.QObject):
    """keyboard's hotkey callback fires on its own background thread.
    Calling Qt widget methods directly from there is unsafe and can
    silently no-op. Routing through a signal/slot (QueuedConnection,
    which is the default across threads) hands the actual toggle back
    to the Qt event loop on the main thread."""
    fired = QtCore.pyqtSignal()


def install_hotkey(overlay: Overlay, app: QtWidgets.QApplication):
    bridge = _HotkeyBridge()
    bridge.fired.connect(lambda: overlay.setVisible(not overlay.isVisible()))

    keyboard.add_hotkey(Setup.HOTKEY, bridge.fired.emit)

    # keep a reference alive on the app object so it isn't garbage collected
    app._hotkey_bridge = bridge
    return bridge


def main():
    db.init_db()
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = Overlay()
    overlay.show()
    install_hotkey(overlay, app)

    tray = QtWidgets.QSystemTrayIcon(QtGui.QIcon.fromTheme("applications-games"))
    tray_menu = QtWidgets.QMenu()
    toggle_action = tray_menu.addAction("Show/Hide overlay")
    toggle_action.triggered.connect(lambda: overlay.setVisible(not overlay.isVisible()))
    quit_action = tray_menu.addAction("Quit")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(tray_menu)
    tray.setToolTip(f"Isaac Player Tracker (toggle: {Setup.HOTKEY.upper()})")
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
