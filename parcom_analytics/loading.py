"""Indeterminate loading overlay for actual background network work."""

from PySide6.QtCore import Qt, QTimer, QEvent, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget


class LoadingOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.setInterval(70)
        self.timer.timeout.connect(self.advance)
        self.setAccessibleName("Znuny-Daten werden geladen …")
        parent.installEventFilter(self)
        self.hide()

    def advance(self):
        self.angle = (self.angle + 20) % 360
        self.update()

    def set_loading(self, active):
        self.setGeometry(self.parentWidget().rect())
        self.setVisible(active)
        if active:
            self.raise_()
            self.timer.start()
        else:
            self.timer.stop()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(8,17,27,235))
        x,y = self.width()/2, self.height()/2
        painter.setPen(QPen(QColor("#32D5FF"),4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        painter.drawArc(QRectF(x-20,y-50,40,40),self.angle*16,260*16)
        painter.setPen(QColor("#F4F7FA"))
        font = QFont(self.font()); font.setPixelSize(16); painter.setFont(font)
        painter.drawText(QRectF(0,y,self.width(),50),Qt.AlignmentFlag.AlignCenter,"Znuny-Daten werden geladen …")
