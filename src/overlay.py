"""
The overlay window.

Key trick: Windows gets a special "does not steal focus" style
(WS_EX_NOACTIVATE) applied to it after it's created. That means you can
click its buttons and it will show/scroll/etc, but the OS never makes it
the foreground window - so the game keeps thinking it's focused and never
pauses or minimizes. This is the same trick overlays like RTSS/MSI
Afterburner or old-school Discord overlays use.

Toggle the lobby panel with a global hotkey (default F9, see config.py)
that works even while the game has focus. The "Recent Players" panel is a
separate window you can toggle from the button on the lobby panel or from
the tray menu; it shows the last 10 players seen across all sessions, not
just people currently in your lobby.
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


class _NoActivateDraggableWindow(QtWidgets.QWidget):
    """Shared behavior for the frameless, click-through-safe overlay
    windows: draggable by clicking anywhere on the window, and never steals
    focus from the game once shown."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = int(self.winId())
        make_noactivate(hwnd)


class PlayerRow(QtWidgets.QFrame):
    def __init__(self, steam_id, username, parent=None, subtitle=None):
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

        self.subtitle_lbl = None
        if subtitle:
            self.subtitle_lbl = QtWidgets.QLabel(subtitle)
            self.subtitle_lbl.setStyleSheet("color: #999; font-size: 10px;")
            layout.addWidget(self.subtitle_lbl)

        self.tags_layout = QtWidgets.QHBoxLayout()
        self.tags_layout.setSpacing(4)
        layout.addLayout(self.tags_layout)

        self.refresh_tags()

    def update_subtitle(self, subtitle):
        if subtitle is None:
            return
        if self.subtitle_lbl is None:
            self.subtitle_lbl = QtWidgets.QLabel(subtitle)
            self.subtitle_lbl.setStyleSheet("color: #999; font-size: 10px;")
            # insert right after the top row (index 0), before the tags row
            self.layout().insertWidget(1, self.subtitle_lbl)
        else:
            self.subtitle_lbl.setText(subtitle)

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


class Overlay(_NoActivateDraggableWindow):
    """Single docked window: the current-lobby list always shown up top,
    plus a collapsible 'Recent Players' section below it that expands the
    same window (so both sections move together when you drag it) rather
    than opening a second floating window."""

    RECENT_LIMIT = 10
    BASE_HEIGHT = 420
    RECENT_SECTION_HEIGHT = 260

    def __init__(self):
        super().__init__()
        self.resize(360, self.BASE_HEIGHT)
        self.move(60, 60)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QtWidgets.QFrame()
        container.setStyleSheet(
            "QFrame { background: rgba(15,15,15,215); border-radius: 10px; }"
        )
        outer.addWidget(container)
        inner = QtWidgets.QVBoxLayout(container)

        # -- lobby section --------------------------------------------------
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Current Lobby")
        title.setStyleSheet("color: white; font-size: 16px; font-weight: bold;")
        title_row.addWidget(title)
        title_row.addStretch()

        self.recent_btn = QtWidgets.QToolButton()
        self.recent_btn.setText("Recent Players")
        self.recent_btn.setCheckable(True)
        self.recent_btn.setStyleSheet(
            "QToolButton { color: white; background: rgba(60,60,60,180); border-radius: 6px; padding: 3px 8px; }"
            "QToolButton:checked { background: #3a6ea5; }"
        )
        self.recent_btn.clicked.connect(self.toggle_recent_section)
        title_row.addWidget(self.recent_btn)
        inner.addLayout(title_row)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.list_widget = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_widget)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_widget)
        inner.addWidget(self.scroll)

        hint = QtWidgets.QLabel(f"Toggle with {Setup.HOTKEY.upper()} · drag anywhere to move")
        hint.setStyleSheet("color: #888; font-size: 10px;")
        inner.addWidget(hint)

        self._rows = {}

        # -- recent-players section (docked below, collapsible) -------------
        self.recent_section = QtWidgets.QWidget()
        recent_layout = QtWidgets.QVBoxLayout(self.recent_section)
        recent_layout.setContentsMargins(0, 8, 0, 0)

        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        divider.setStyleSheet("color: rgba(255,255,255,40);")
        recent_layout.addWidget(divider)

        recent_title = QtWidgets.QLabel(f"Recent Players (last {self.RECENT_LIMIT})")
        recent_title.setStyleSheet("color: white; font-size: 14px; font-weight: bold; margin-top: 4px;")
        recent_layout.addWidget(recent_title)

        self.recent_scroll = QtWidgets.QScrollArea()
        self.recent_scroll.setWidgetResizable(True)
        self.recent_scroll.setStyleSheet("background: transparent; border: none;")
        self.recent_list_widget = QtWidgets.QWidget()
        self.recent_list_layout = QtWidgets.QVBoxLayout(self.recent_list_widget)
        self.recent_list_layout.addStretch()
        self.recent_scroll.setWidget(self.recent_list_widget)
        recent_layout.addWidget(self.recent_scroll)

        inner.addWidget(self.recent_section)
        self.recent_section.setVisible(False)
        self._recent_rows = {}

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    def toggle_recent_section(self):
        visible = not self.recent_section.isVisible()
        self.recent_section.setVisible(visible)
        self.recent_btn.setChecked(visible)
        self.resize(self.width(), self.BASE_HEIGHT + (self.RECENT_SECTION_HEIGHT if visible else 0))
        if visible:
            self.refresh_recent()

    # -- data refresh --------------------------------------------------------
    def refresh(self):
        self.refresh_lobby()
        if self.recent_section.isVisible():
            self.refresh_recent()

    def refresh_lobby(self):
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

    def refresh_recent(self):
        recent = db.get_recent_players(self.RECENT_LIMIT)
        current_ids = {r[0] for r in recent}

        for steam_id in list(self._recent_rows.keys()):
            if steam_id not in current_ids:
                self._recent_rows[steam_id].deleteLater()
                del self._recent_rows[steam_id]

        for idx, (steam_id, username, first_seen, last_seen) in enumerate(recent):
            subtitle = f"last seen {last_seen}"
            if steam_id not in self._recent_rows:
                row = PlayerRow(steam_id, username, subtitle=subtitle)
                self._recent_rows[steam_id] = row
            else:
                row = self._recent_rows[steam_id]
                row.update_subtitle(subtitle)
                row.refresh_tags()
            # keep list ordered newest-first without destroying/recreating rows
            self.recent_list_layout.removeWidget(row)
            self.recent_list_layout.insertWidget(idx, row)


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
    toggle_recent_action = tray_menu.addAction("Show/Hide recent players")
    toggle_recent_action.triggered.connect(overlay.toggle_recent_section)
    quit_action = tray_menu.addAction("Quit")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(tray_menu)
    tray.setToolTip(f"Isaac Player Tracker (toggle: {Setup.HOTKEY.upper()})")
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()