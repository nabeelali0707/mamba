"""Speech bubble that shows the current news item with next / prev controls."""
from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from core.models import CATEGORIES, NewsItem

TAIL_H = 14
ACCENT = {
    "model": "#ff5a5f", "product": "#ffa63d", "research": "#5ad1ff", "paper": "#b69cff",
    "open_source": "#5be37d", "funding": "#ffd23f", "buzz": "#ff7ac6", "news": "#9aa4b5",
}
LABELS = {"model": "NEW MODEL", "product": "PRODUCT", "research": "RESEARCH", "paper": "PAPER",
          "open_source": "OPEN SOURCE", "funding": "FUNDING", "buzz": "BUZZ", "news": "NEWS"}

STYLE = """
QLabel#tag { font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#count { color: #8890a0; font-size: 11px; }
QLabel#title { color: #f4f5f8; font-size: 13px; font-weight: 700; }
QLabel#summary { color: #aab0bd; font-size: 11px; }
QLabel#meta { color: #7d8595; font-size: 11px; }
QPushButton { background: rgba(255,255,255,0.08); color: #e6e8ee; border: none;
              border-radius: 8px; padding: 4px 8px; font-size: 12px; }
QPushButton:hover { background: rgba(255,255,255,0.18); }
QPushButton#chip { padding: 1px 4px; font-size: 11px; border-radius: 9px; }
QPushButton#chip:checked { background: rgba(255,255,255,0.28); }
QPushButton#auto:checked { background: #2f7d4f; }
QPushButton#open { background: #3b6df0; font-weight: 600; }
QPushButton#open:hover { background: #5280ff; }
"""


def ago(ts: float) -> str:
    s = max(0, time.time() - ts)
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    return f"{int(s // 86400)}d ago"


class ClickLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class Bubble(QWidget):
    WIDTH = 300
    TAIL_X = 242

    next_clicked = Signal()
    prev_clicked = Signal()
    open_clicked = Signal()
    refresh_clicked = Signal()
    auto_toggled = Signal(bool)
    filter_changed = Signal(object)   # category str or None
    close_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self.WIDTH)
        self.setStyleSheet(STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9 + TAIL_H)
        root.setSpacing(6)

        head = QHBoxLayout()
        self.tag = QLabel(); self.tag.setObjectName("tag")
        self.count = QLabel(); self.count.setObjectName("count")
        close = QPushButton("✕"); close.setObjectName("chip"); close.setToolTip("Hide bubble")
        close.clicked.connect(self.close_clicked)
        head.addWidget(self.tag); head.addStretch(1); head.addWidget(self.count); head.addWidget(close)
        root.addLayout(head)

        self.title = ClickLabel(); self.title.setObjectName("title")
        self.title.setWordWrap(True); self.title.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title.clicked.connect(self.open_clicked)
        root.addWidget(self.title)

        self.summary = QLabel(); self.summary.setObjectName("summary"); self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.meta = QLabel(); self.meta.setObjectName("meta"); root.addWidget(self.meta)

        # category chips
        chips = QHBoxLayout(); chips.setSpacing(2)
        self.group = QButtonGroup(self); self.group.setExclusive(True)
        self._chip_cat: dict[int, str | None] = {}
        for n, (cat, label) in enumerate([(None, "All")] + [(c, v[0]) for c, v in CATEGORIES.items()]):
            b = QPushButton(label); b.setObjectName("chip"); b.setCheckable(True)
            b.setToolTip(LABELS.get(cat, "All categories"))
            if cat is None:
                b.setChecked(True)
            self.group.addButton(b, n); self._chip_cat[n] = cat
            chips.addWidget(b)
        chips.addStretch(1)
        self.group.idClicked.connect(lambda i: self.filter_changed.emit(self._chip_cat[i]))
        root.addLayout(chips)

        # controls
        row = QHBoxLayout()
        prev = QPushButton("◀"); prev.setToolTip("Previous"); prev.clicked.connect(self.prev_clicked)
        nxt = QPushButton("▶"); nxt.setToolTip("Next story (or scroll wheel)"); nxt.clicked.connect(self.next_clicked)
        self.auto = QPushButton("Auto"); self.auto.setObjectName("auto"); self.auto.setCheckable(True)
        self.auto.setChecked(True); self.auto.setToolTip("Rotate stories automatically")
        self.auto.toggled.connect(self.auto_toggled)
        refresh = QPushButton("↻"); refresh.setToolTip("Fetch fresh news now"); refresh.clicked.connect(self.refresh_clicked)
        op = QPushButton("Open"); op.setObjectName("open"); op.clicked.connect(self.open_clicked)
        for w in (prev, nxt, self.auto, refresh):
            row.addWidget(w)
        row.addStretch(1); row.addWidget(op)
        root.addLayout(row)

    # ---- content ----
    def show_item(self, item: NewsItem | None, index: int, total: int, new_count: int = 0) -> None:
        if item is None:
            self.tag.setText("NO NEWS YET"); self.tag.setStyleSheet("color:#9aa4b5")
            self.title.setText("Sniffing around the internet… 🐂")
            self.summary.setText(""); self.meta.setText(""); self.count.setText("")
            return
        color = ACCENT.get(item.category, "#9aa4b5")
        lab = f" · {item.lab}" if item.lab else ""
        self.tag.setText(f"{item.emoji} {LABELS.get(item.category, 'NEWS')}{lab}".upper())
        self.tag.setStyleSheet(f"color:{color}")
        self.title.setText(item.title)
        s = item.summary
        self.summary.setText((s[:190] + "…") if len(s) > 190 else s)
        self.summary.setVisible(bool(s))
        self.meta.setText(f"{item.source} · {ago(item.published)}")
        extra = f"  ·  ● {new_count} new" if new_count else ""
        self.count.setText(f"{index + 1}/{total}{extra}")

    # ---- look ----
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(1, 1, self.width() - 2, self.height() - TAIL_H - 2)
        path = QPainterPath(); path.addRoundedRect(body, 16, 16)
        tail = QPainterPath()
        tail.addPolygon(QPolygonF([QPointF(self.TAIL_X - 11, body.bottom() - 1),
                                   QPointF(self.TAIL_X + 11, body.bottom() - 1),
                                   QPointF(self.TAIL_X, body.bottom() + TAIL_H)]))
        path = path.united(tail)
        p.setPen(QPen(QColor(255, 255, 255, 45), 1)); p.setBrush(QColor(22, 24, 33, 242))
        p.drawPath(path)

    def wheelEvent(self, e) -> None:
        (self.next_clicked if e.angleDelta().y() < 0 else self.prev_clicked).emit()
