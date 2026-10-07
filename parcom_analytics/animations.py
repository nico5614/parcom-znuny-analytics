"""Short, interruptible Qt transitions that never alter analytics values."""

import math

from matplotlib.patches import Rectangle, Wedge
from PySide6.QtCore import QEasingCurve, QObject, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


class Animator(QObject):
    def __init__(self, parent=None, reduced=False):
        super().__init__(parent)
        self.reduced = reduced
        self.active = {}

    def stop(self, target):
        entry = self.active.pop(target, None)
        if entry:
            animation, update = entry
            animation.stop()
            update(1.0)
            animation.deleteLater()

    def finish_all(self):
        for target in list(self.active):
            self.stop(target)

    def run(self, target, update, duration=300):
        self.stop(target)
        if self.reduced or not target.isVisible():
            update(1.0)
            return
        animation = QVariantAnimation(target)
        animation.setDuration(duration)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.valueChanged.connect(update)
        self.active[target] = (animation, update)
        animation.finished.connect(lambda: self.stop(target))
        target.destroyed.connect(lambda: self.active.pop(target, None))
        update(0.0)
        animation.start()

    def fade(self, widget):
        self.stop(widget)
        if self.reduced or not widget.isVisible():
            return
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        def update(progress):
            if progress >= 1:
                # Remove the compositor cache so native table viewports repaint normally.
                widget.setGraphicsEffect(None)
                widget.update()
            else:
                effect.setOpacity(.3+.7*progress)
        self.run(widget, update, 180)

    def count(self, widget, old, new, formatter):
        self.run(widget, lambda progress: widget.setText(formatter(old+(new-old)*progress)), 300)

    def chart(self, canvas):
        self.stop(canvas)
        if self.reduced or not canvas.isVisible():
            canvas.draw_idle()
            return
        rectangles, wedges, lines = [], [], []
        for axis in canvas.figure.axes:
            for patch in axis.patches:
                if isinstance(patch, Rectangle):
                    rectangles.append((patch, patch.get_height()))
                elif isinstance(patch, Wedge):
                    wedges.append((patch, patch.theta1, patch.theta2))
            for line in axis.lines:
                if line.get_marker() == "o" and len(line.get_xdata()) >= 2:
                    lines.append((line, line.get_xdata().copy(), line.get_ydata().copy()))
        def update(progress):
            for patch, height in rectangles:
                patch.set_height(height*progress)
            for patch, first, second in wedges:
                patch.set_theta1(90+(first-90)*progress)
                patch.set_theta2(90+(second-90)*progress)
            for line, x, y in lines:
                count = max(1, math.ceil(len(x)*progress))
                line.set_data(x[:count], y[:count])
            canvas.draw_idle()
        self.run(canvas, update, 420 if wedges else 320)


class ScoreRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self.value = 0.0
        self.progress = 1.0
        self.color = "#59bd8b"

    def set_progress(self, progress):
        self.progress = progress
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(9, 9, -9, -9)
        painter.setPen(QPen(QColor("#35404d"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 0, 360*16)
        painter.setPen(QPen(QColor(self.color), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90*16, -round(self.value/100*360*16*self.progress))
