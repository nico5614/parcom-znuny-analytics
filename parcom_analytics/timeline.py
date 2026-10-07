"""Snapping two-handle timeline with an explicit custom interval zoom."""

from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QDateTime
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateTimeEdit, QPushButton

from .analytics import DataError
from .periods import PRESETS, TimeRange, ZURICH, now


class RangeTrack(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "normal"
        self.key = "1W"
        self.custom = None
        self.dragging = None
        self.setMinimumSize(300, 66)
        self.setMaximumHeight(66)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Zeitraum: 1 Tag bis 1 Jahr; Pfeiltasten ändern den Zeitraum")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def x(self, index):
        return 20 + (self.width() - 40) * index / 6

    def handles(self):
        return (self.x(0), self.x(6)) if self.mode == "custom" else (self.x(PRESETS.index(self.key)), self.x(6))

    def period(self):
        return self.custom if self.mode == "custom" else TimeRange.preset(self.key)

    def apply_custom(self, period):
        self.custom, self.mode = period, "custom"
        self.update()
        self.changed.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = 22
        p.setPen(QPen(QColor("#203247"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(self.x(0), y), QPointF(self.x(6), y))
        left, right = self.handles()
        p.setPen(QPen(QColor("#32D5FF"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(left, y), QPointF(right, y))
        for x in (left, right):
            p.setPen(QPen(QColor("#08111B"), 3))
            p.setBrush(QColor("#32D5FF"))
            p.drawEllipse(QPointF(x, y), 11, 11)
        p.setPen(QColor("#A6B2BF"))
        if self.mode == "custom":
            p.drawText(QRectF(12, 42, self.width()/2, 22), Qt.AlignmentFlag.AlignLeft,
                       self.custom.start.strftime("%d.%m.%Y %H:%M"))
            p.drawText(QRectF(self.width()/2-12, 42, self.width()/2, 22), Qt.AlignmentFlag.AlignRight,
                       self.custom.end.strftime("%d.%m.%Y %H:%M"))
        else:
            for index, key in enumerate((*PRESETS, "Jetzt")):
                p.setPen(QColor("#32D5FF" if key == self.key else "#A6B2BF"))
                p.drawText(QRectF(self.x(index)-20, 42, 40, 22), Qt.AlignmentFlag.AlignCenter, key)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        left, right = self.handles()
        self.dragging = "left" if abs(event.position().x()-left) <= abs(event.position().x()-right) else "right"
        self.origin = event.position().x()
        if self.mode == "normal":
            self._snap(event.position().x())

    def _snap(self, x):
        self.mode = "normal"
        # Both handles select a standard rolling duration; the end remains anchored at now.
        # Dragging the right handle left increases the lookback, then it returns to the end.
        index = min(5, max(0, round((x-20)/(max(1, self.width()-40))*6)))
        self.key = PRESETS[index]
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging and abs(event.position().x()-self.origin) > 2:
            self._snap(event.position().x())

    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = None
            self.changed.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.mode = "normal"
            index = PRESETS.index(self.key) + (-1 if event.key() == Qt.Key.Key_Left else 1)
            self.key = PRESETS[min(5, max(0, index))]
            self.update()
            self.changed.emit()
        else:
            super().keyPressEvent(event)


class Timeline(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.track = RangeTrack()
        layout.addWidget(self.track)
        row = QHBoxLayout()
        self.start_edit, self.end_edit = QDateTimeEdit(), QDateTimeEdit()
        for text, edit in (("Von", self.start_edit), ("Bis", self.end_edit)):
            row.addWidget(QLabel(text))
            edit.setDisplayFormat("dd.MM.yyyy HH:mm")
            edit.setCalendarPopup(True)
            edit.setMinimumWidth(156)
            row.addWidget(edit)
        self.apply = QPushButton("Anwenden")
        self.apply.setObjectName("secondary")
        self.apply.clicked.connect(self.apply_custom)
        row.addWidget(self.apply)
        layout.addLayout(row)
        self.error = QLabel()
        self.error.setObjectName("warning")
        self.error.hide()
        layout.addWidget(self.error)
        self.track.changed.connect(self._changed)
        self.sync_controls()

    def period(self):
        return self.track.period()

    def sync_controls(self):
        period = self.period()
        self.start_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(period.start.timestamp())).toLocalTime())
        self.end_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(period.end.timestamp())).toLocalTime())

    def _changed(self):
        self.error.hide()
        self.sync_controls()
        self.changed.emit()

    def apply_custom(self):
        from datetime import datetime
        try:
            start = datetime.fromtimestamp(self.start_edit.dateTime().toSecsSinceEpoch(), ZURICH)
            end = datetime.fromtimestamp(self.end_edit.dateTime().toSecsSinceEpoch(), ZURICH)
            self.track.apply_custom(TimeRange(start, end))
        except DataError as error:
            self.error.setText(str(error))
            self.error.show()
