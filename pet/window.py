"""The always-on-top transparent pet window: bubble above, bull below."""
from __future__ import annotations

import datetime
import random
import time
import webbrowser

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QMenu, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

from core import autostart
from core.db import Store
from core.feed import Feed
from core.models import CATEGORIES
from core.worker import FetchThread

from .bubble import Bubble
from .bull import BullWidget

FETCH_EVERY_MS = 15 * 60 * 1000
AUTO_EVERY_MS = 12 * 1000
ROAM_SPEED = 40.0          # px per second: a slow, lazy drift
ROAM_TICK_MS = 33


class PetWindow(QWidget):
    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self.feed = Feed(store)
        self.new_count = 0
        self._fetcher: FetchThread | None = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Mamba")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        self.bubble = Bubble()
        self.bull = BullWidget()
        lay.addWidget(self.bubble)
        # keep the bull centred under the bubble's tail
        row = QHBoxLayout()
        self._row = row
        self._bull_margin = self.bubble.TAIL_X - self.bull.width() // 2
        row.setContentsMargins(self._bull_margin, 0, 0, 0)
        row.addWidget(self.bull); row.addStretch(1)
        lay.addLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        self.setFixedWidth(self.bubble.WIDTH)

        # wiring
        self.bull.clicked.connect(self.toggle_bubble)
        self.bull.wheel.connect(lambda d: self.step(d))
        self.bull.context.connect(self.show_menu)
        self.bubble.next_clicked.connect(lambda: self.step(1))
        self.bubble.prev_clicked.connect(lambda: self.step(-1))
        self.bubble.open_clicked.connect(self.open_current)
        self.bubble.refresh_clicked.connect(self.refresh)
        self.bubble.close_clicked.connect(lambda: self.set_bubble_visible(False))
        self.bubble.filter_changed.connect(self.set_filter)
        self.bubble.auto_toggled.connect(self.set_auto)

        self.roam = True
        self._fx = self._fy = 0.0
        self._target: tuple[float, float] | None = None
        self._rest_until = time.time() + 6
        self.roam_timer = QTimer(self); self.roam_timer.timeout.connect(self._roam_tick)
        self.roam_timer.start(ROAM_TICK_MS)
        self.top_timer = QTimer(self); self.top_timer.timeout.connect(self._stay_on_top)
        self.top_timer.start(3000)
        self.auto_timer = QTimer(self); self.auto_timer.timeout.connect(self._auto_step)
        self.auto_timer.start(AUTO_EVERY_MS)
        self.fetch_timer = QTimer(self); self.fetch_timer.timeout.connect(self.refresh)
        self.fetch_timer.start(FETCH_EVERY_MS)
        self.mood_timer = QTimer(self); self.mood_timer.timeout.connect(self._update_mood)
        self.mood_timer.start(60_000); self._update_mood()

        self._build_tray()
        self.render_current()
        self._place_initial()
        self._peek()
        QTimer.singleShot(500, self.refresh)

    # ---------- layout helpers ----------
    def _place_initial(self) -> None:
        self.adjustSize()
        g = QApplication.primaryScreen().availableGeometry()
        self.move(g.right() - self.width() - 24, g.bottom() - self.height() - 16)

    def _relayout(self) -> None:
        """Resize to fit content while keeping the bull in place; clamp on screen."""
        bottom = self.geometry().bottom()
        bull_screen_x = self.x() + self._row.contentsMargins().left()
        if self.bubble.isVisible():
            margin, width = self._bull_margin, self.bubble.WIDTH
        else:                                   # just the bull: shrink the window to fit it
            margin, width = 0, self.bull.width()
        self._row.setContentsMargins(margin, 0, 0, 0)
        self.setFixedWidth(width)
        self.adjustSize()
        self.move(bull_screen_x - margin, bottom - self.height() + 1)
        self._clamp()

    # ---------- roaming ----------
    def set_roam(self, on: bool) -> None:
        self.roam = on

    def _roam_tick(self) -> None:
        now = time.time()
        busy = self.bull.dragging or self.underMouse()
        if busy:                                    # user is interacting: stand still
            self._target = None
            self._rest_until = now + 8
            return
        if not self.roam or now < self._rest_until:
            return
        cur = self.pos()
        if abs(cur.x() - round(self._fx)) > 1 or abs(cur.y() - round(self._fy)) > 1:
            self._fx, self._fy = float(cur.x()), float(cur.y())   # moved by drag / relayout
        if self._target is None:
            scr = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
            g = scr.availableGeometry()
            self._target = (random.uniform(g.left(), max(g.left(), g.right() - self.width())),
                            random.uniform(g.top(), max(g.top(), g.bottom() - self.height())))
        tx, ty = self._target
        dx, dy = tx - self._fx, ty - self._fy
        dist = (dx * dx + dy * dy) ** 0.5
        step = ROAM_SPEED * ROAM_TICK_MS / 1000
        if dist <= step:                            # arrived: rest, then pick a new spot
            self._fx, self._fy = tx, ty
            self._target = None
            self._rest_until = now + random.uniform(4, 10)
        else:
            self._fx += dx / dist * step
            self._fy += dy / dist * step
        self.move(round(self._fx), round(self._fy))

    def _stay_on_top(self) -> None:
        """Re-assert topmost so other windows can't bury the bull."""
        if self.isVisible():
            self.raise_()

    def _clamp(self) -> None:
        scr = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        g = scr.availableGeometry()
        x = min(max(self.x(), g.left() - 120), g.right() - self.width() + 120)
        y = min(max(self.y(), g.top()), g.bottom() - self.height() + 1)
        self.move(x, y)

    # ---------- feed navigation ----------
    def render_current(self) -> None:
        self.bubble.show_item(self.feed.current, self.feed.index, len(self.feed), self.new_count)
        QTimer.singleShot(0, self._relayout)

    def step(self, d: int) -> None:
        if not self.bubble.isVisible():
            self.set_bubble_visible(True)
        self.new_count = 0
        (self.feed.next if d > 0 else self.feed.prev)()
        self.render_current()
        self.auto_timer.start(AUTO_EVERY_MS)   # restart so it doesn't skip right after a manual step

    def _auto_step(self) -> None:
        if self.bubble.isVisible() and self.bubble.auto.isChecked() and not self.bubble.underMouse():
            self.feed.next()
            self.render_current()

    def set_auto(self, on: bool) -> None:
        self.auto_timer.start(AUTO_EVERY_MS) if on else self.auto_timer.stop()

    def set_filter(self, cat) -> None:
        self.feed.set_category(cat)
        self.render_current()

    def open_current(self) -> None:
        if self.feed.current:
            webbrowser.open(self.feed.current.url)

    def toggle_bubble(self) -> None:
        self.set_bubble_visible(not self.bubble.isVisible())

    def _peek(self) -> None:
        """Make sure the bubble is showing (it stays until the user closes it)."""
        self.set_bubble_visible(True)

    def set_bubble_visible(self, on: bool) -> None:
        self.bubble.setVisible(on)
        QTimer.singleShot(0, self._relayout)

    # ---------- fetching ----------
    def refresh(self) -> None:
        if self._fetcher and self._fetcher.isRunning():
            return
        self._fetcher = FetchThread(self.store, self)
        self._fetcher.done.connect(self._on_fetched)
        self._fetcher.failed.connect(self._on_fetch_failed)
        self._fetcher.start()

    def _on_fetch_failed(self, _msg: str) -> None:
        """Typically no network yet right after boot: quietly retry in a minute."""
        QTimer.singleShot(60_000, self.refresh)

    def _on_fetched(self, new: list, first_run: bool) -> None:
        self.feed.reload()
        if new and not first_run:
            self.new_count = len(new)
            best = max(new, key=lambda i: (i.priority, i.score, i.published))
            self.feed.goto(best.id)
            self._peek()
            self.bull.alert(big=best.priority >= 3)
        elif first_run:
            self.bull.alert()
            self._peek()
        self.render_current()

    # ---------- mood / tray / menu ----------
    def _update_mood(self) -> None:
        self.bull.sleepy = datetime.datetime.now().hour < 6

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(self.bull.icon_pixmap(64)), self)
        self.tray.setToolTip("Mamba — AI news bull")
        self.tray.setContextMenu(self._make_menu())
        self.tray.activated.connect(
            lambda r: self.toggle_bubble() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def _make_menu(self) -> QMenu:
        m = QMenu()
        m.addAction("Show / hide news bubble", self.toggle_bubble)
        roam = m.addAction("Roam around screen"); roam.setCheckable(True); roam.setChecked(self.roam)
        roam.toggled.connect(self.set_roam)
        m.addAction("Fetch news now", self.refresh)
        st = m.addAction("Start with Windows"); st.setCheckable(True); st.setChecked(autostart.is_enabled())
        st.toggled.connect(lambda on: autostart.enable() if on else autostart.disable())
        fm = m.addMenu("Filter")
        fm.addAction("All", lambda: self._menu_filter(None))
        for cat, (emo, _) in CATEGORIES.items():
            fm.addAction(f"{emo} {cat}", lambda c=cat: self._menu_filter(c))
        m.addSeparator()
        m.addAction("Quit", QApplication.quit)
        return m

    def _menu_filter(self, cat) -> None:
        idx = [None] + list(CATEGORIES)
        self.bubble.group.button(idx.index(cat)).setChecked(True)
        self.set_filter(cat)

    def show_menu(self, pos: QPoint) -> None:
        self._make_menu().exec(pos)
