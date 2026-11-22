"""The bull: a cartoon face drawn with QPainter (no image assets needed)."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

BROWN = QColor("#8a5528")
BROWN_DARK = QColor("#5e3716")
TUFT = QColor("#b07a45")
SNOUT = QColor("#f1c9a2")
HORN = QColor("#f6e7c6")
OUTLINE = QColor("#3b200b")
GOLD = QColor("#f2b705")


class BullWidget(QWidget):
    clicked = Signal()
    wheel = Signal(int)          # +1 / -1
    context = Signal(object)     # global QPoint

    W, H = 170, 160

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._t0 = time.time()
        self._jump_start = -10.0
        self._shake_start = -10.0
        self._blink_at = 2.5
        self._press_pos = None
        self._press_win = None
        self._dragged = False
        self.sleepy = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(33)

    # ---- public ----
    def alert(self, big: bool = False) -> None:
        """Hop (and shake horns if it's big news)."""
        now = self._now()
        self._jump_start = now
        if big:
            self._shake_start = now

    def icon_pixmap(self, size: int = 64) -> QPixmap:
        pm = QPixmap(self.W, self.H)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw(p, 0.0, QPointF(0, 0), static=True)
        p.end()
        return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

    # ---- time helpers ----
    def _now(self) -> float:
        return time.time() - self._t0

    # ---- painting ----
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        now = self._now()
        look = QPointF(0, 0)
        c = self.mapFromGlobal(QCursor.pos())
        dx, dy = c.x() - self.W / 2, c.y() - self.H / 2
        dist = math.hypot(dx, dy)
        if dist > 1:
            k = min(dist / 80.0, 1.0) * 4.0
            look = QPointF(dx / dist * k, dy / dist * k)
        self._draw(p, now, look)

    def _draw(self, p: QPainter, now: float, look: QPointF, static: bool = False) -> None:
        # hop
        hop = 0.0
        jt = now - self._jump_start
        if 0 <= jt < 1.2:
            hop = -abs(math.sin(jt / 1.2 * math.pi * 2)) * 26 * (1 - jt / 1.2)
        # horn shake (rotate whole head a little)
        rot = 0.0
        st = now - self._shake_start
        if 0 <= st < 1.2:
            rot = math.sin(st * 28) * 7 * (1 - st / 1.2)
        breathe = 1.0 + (0 if static else math.sin(now * 2.0) * 0.012)

        p.save()
        p.translate(self.W / 2, self.H - 6)          # pivot at chin
        p.translate(0, hop)
        p.rotate(rot)
        p.scale(breathe, breathe)
        p.translate(-self.W / 2, -(self.H - 6))

        outline = QPen(OUTLINE, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        # shoulders / neck
        p.setPen(outline); p.setBrush(BROWN_DARK)
        p.drawEllipse(QRectF(25, 120, 120, 60))

        # horns (behind head)
        for sign in (-1, 1):
            cx = 85
            path = QPainterPath()
            path.moveTo(cx + sign * 38, 62)
            path.cubicTo(cx + sign * 62, 62, cx + sign * 78, 44, cx + sign * 70, 10)
            path.cubicTo(cx + sign * 60, 36, cx + sign * 52, 44, cx + sign * 32, 48)
            path.closeSubpath()
            p.setBrush(HORN); p.drawPath(path)

        # ears
        for sign in (-1, 1):
            p.save()
            p.translate(85 + sign * 54, 72)
            p.rotate(sign * 22)
            p.setBrush(BROWN); p.drawEllipse(QRectF(-20, -10, 40, 20))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#e9a08a"))
            p.drawEllipse(QRectF(-12, -5, 24, 10))
            p.restore()
        p.setPen(outline)

        # head
        p.setBrush(BROWN); p.drawEllipse(QRectF(32, 36, 106, 100))
        # forehead tuft
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(TUFT)
        p.drawEllipse(QRectF(68, 38, 34, 22))
        p.setPen(outline)

        # snout
        p.setBrush(SNOUT); p.drawEllipse(QRectF(52, 96, 66, 42))
        p.setBrush(OUTLINE); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(68, 112, 8, 11)); p.drawEllipse(QRectF(94, 112, 8, 11))
        # nose ring
        p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(GOLD, 3.2))
        p.drawArc(QRectF(74, 118, 22, 24), 200 * 16, 140 * 16)
        p.setPen(QPen(QColor("#9a7000"), 1))
        p.drawArc(QRectF(74, 118, 22, 24), 200 * 16, 140 * 16)

        # cheeks
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255, 120, 120, 70))
        p.drawEllipse(QRectF(40, 98, 18, 12)); p.drawEllipse(QRectF(112, 98, 18, 12))

        # eyes
        blink = 0.0
        if not static:
            if now > self._blink_at:
                blink = (now - self._blink_at) / 0.16
                if blink >= 1.0:
                    self._blink_at = now + 2.5 + (hash(int(now)) % 30) / 10.0
                    blink = 0.0
            blink = 1 - abs(blink * 2 - 1) if blink else 0.0
        lid = 0.55 if self.sleepy else 0.0
        open_amt = max(0.08, 1.0 - max(blink, lid))
        for ex in (62, 108):
            p.setPen(QPen(OUTLINE, 2)); p.setBrush(QColor("white"))
            p.drawEllipse(QRectF(ex - 11, 80 - 12 * open_amt, 22, 24 * open_amt))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#1a1008"))
            ph = 13 * open_amt
            p.drawEllipse(QRectF(ex - 6.5 + look.x(), 80 - ph / 2 + look.y() * open_amt, 13, ph))
            if open_amt > 0.6:
                p.setBrush(QColor("white"))
                p.drawEllipse(QRectF(ex - 3 + look.x(), 76 + look.y(), 4, 4))
        # brows
        p.setPen(QPen(OUTLINE, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(48, 63), QPointF(72, 68)); p.drawLine(QPointF(122, 63), QPointF(98, 68))
        p.restore()

        if self.sleepy and not static:
            p.setPen(QColor(200, 210, 255, 220)); f = QFont("Segoe UI", 13, QFont.Weight.Bold); p.setFont(f)
            off = (now * 12) % 20
            p.drawText(QPointF(135, 40 - off * 0.6), "z")
            p.drawText(QPointF(147, 26 - off * 0.6), "Z")

    # ---- mouse: drag window, click, wheel, right-click ----
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_pos = e.globalPosition().toPoint()
            self._press_win = self.window().pos()
            self._dragged = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif e.button() == Qt.MouseButton.RightButton:
            self.context.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e) -> None:
        if self._press_pos is not None and e.buttons() & Qt.MouseButton.LeftButton:
            delta = e.globalPosition().toPoint() - self._press_pos
            if self._dragged or delta.manhattanLength() > 5:
                self._dragged = True
                self.window().move(self._press_win + delta)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if not self._dragged:
                self.clicked.emit()
            self._press_pos = None

    def wheelEvent(self, e) -> None:
        self.wheel.emit(1 if e.angleDelta().y() < 0 else -1)
