"""Scrollable digital timing diagram, rendered only for the visible time range."""
from bisect import bisect_left, bisect_right
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QAbstractScrollArea
from eitri.backend.vcd import format_value, time_label, value_at


class WaveformView(QAbstractScrollArea):
    cursor_changed = Signal(float)
    LEFT = 145
    TOP = 30
    ROW = 38

    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = []
        self.end = 1
        self.timescale = '1 fs'
        self.zoom = 1.0
        self.cursor = 0
        self.radix = 'Hex'
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)
        self.horizontalScrollBar().setSingleStep(40)
        self.verticalScrollBar().setSingleStep(self.ROW)
        self.setMinimumHeight(100)

    def set_data(self, signals, end_time, timescale):
        self.signals = signals
        self.end = max(1, end_time)
        self.timescale = timescale
        self.cursor = min(self.cursor, self.end)
        self.update_ranges()
        self.viewport().update()
        self.cursor_changed.emit(self.cursor)

    def update_ranges(self):
        width = max(1, self.viewport().width() - self.LEFT)
        self.horizontalScrollBar().setRange(0, int(width * (self.zoom - 1)))
        self.horizontalScrollBar().setPageStep(width)
        self.verticalScrollBar().setRange(0, max(0, len(self.signals) * self.ROW + self.TOP - self.viewport().height()))
        self.verticalScrollBar().setPageStep(self.viewport().height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_ranges()

    def zoom_by(self, factor):
        self.zoom = max(1, min(1000, self.zoom * factor))
        self.update_ranges()
        width = max(1, self.viewport().width() - self.LEFT)
        self.horizontalScrollBar().setValue(int(self.cursor / self.end * width * self.zoom - width / 2))
        self.viewport().update()

    def fit(self):
        self.zoom = 1
        self.update_ranges()
        self.viewport().update()

    def wheelEvent(self, event):
        # QAbstractScrollArea's default wheel handling uses angle steps. Honor
        # high-resolution trackpad pixels directly, on both axes.
        delta = event.pixelDelta()
        if not delta.isNull():
            for bar, distance in ((self.horizontalScrollBar(), delta.x()),
                                  (self.verticalScrollBar(), delta.y())):
                bar.setValue(bar.value() - distance)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if event.position().x() >= self.LEFT:
            width = max(1, self.viewport().width() - self.LEFT)
            ticks = (event.position().x() - self.LEFT + self.horizontalScrollBar().value()) / (width * self.zoom) * self.end
            self.cursor = max(0, min(self.end, ticks))
            self.cursor_changed.emit(self.cursor)
            self.viewport().update()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        with QPainter(self.viewport()) as painter:
            self._paint_waveform(painter)

    def _paint_waveform(self, painter):
        painter.fillRect(self.viewport().rect(), QColor('#242423'))
        if not self.signals:
            painter.setPen(QColor('#aaa59b'))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, 'Run a simulation, then select signals to display.')
            return
        width = max(1, self.viewport().width() - self.LEFT)
        scale = width * self.zoom / self.end
        offset = self.horizontalScrollBar().value()
        start, stop = offset / scale, (offset + width) / scale

        def x(tick):
            return self.LEFT + tick * scale - offset

        # The ruler stays fixed while signal rows scroll vertically.
        painter.setPen(QColor('#9c9588'))
        for index in range(6):
            tick = start + (stop - start) * index / 5
            xpos = x(tick)
            painter.drawText(QRectF(xpos + 3, 0, 100, self.TOP), time_label(tick, self.timescale))
            painter.setPen(QColor('#3c3933'))
            painter.drawLine(QPointF(xpos, self.TOP), QPointF(xpos, self.viewport().height()))
            painter.setPen(QColor('#9c9588'))

        painter.setClipRect(0, self.TOP, self.viewport().width(), self.viewport().height() - self.TOP)
        for row, signal in enumerate(self.signals):
            y = self.TOP + row * self.ROW - self.verticalScrollBar().value()
            if y + self.ROW < self.TOP or y > self.viewport().height():
                continue
            painter.setPen(QColor('#dedbd5'))
            name = painter.fontMetrics().elidedText(signal['name'].split('.', 1)[-1], Qt.TextElideMode.ElideLeft, self.LEFT - 14)
            painter.drawText(QRectF(6, y, self.LEFT - 12, self.ROW), Qt.AlignmentFlag.AlignVCenter, name)
            events = signal['events']
            first = max(0, bisect_right(events, start, key=lambda item: item[0]) - 1)
            last = bisect_left(events, stop, key=lambda item: item[0])
            painter.save()
            try:
                painter.setClipRect(self.LEFT, self.TOP, width, self.viewport().height() - self.TOP)
                # Dense traces need zooming; drawing hundreds of thousands of edges
                # on each mouse click would stall the GUI with no useful detail.
                if last - first > 2000:
                    painter.fillRect(QRectF(self.LEFT, y + 8, width, 20), QColor('#716044'))
                    painter.setPen(QColor('#e5dfd3'))
                    painter.drawText(QRectF(self.LEFT + 8, y, width - 8, self.ROW), Qt.AlignmentFlag.AlignVCenter, 'Dense transitions — zoom in')
                    continue
                segments = events[first:last + 1] if events else [[0, 'X']]
                if segments and segments[0][0] > start:
                    segments = [[start, 'X']] + segments
                for index, (timestamp, value) in enumerate(segments):
                    end = segments[index + 1][0] if index + 1 < len(segments) else self.end
                    left, right = max(self.LEFT, x(timestamp)), min(self.viewport().width(), x(end))
                    if right <= left:
                        continue
                    color = '#c8877c' if any(bit in value for bit in 'UXW-') else ('#a49aac' if 'Z' in value else '#b9c4a1')
                    painter.setPen(QPen(QColor(color), 1.4))
                    high, low = y + 8, y + 28
                    if signal['width'] == 1 and value in ('0', '1'):
                        level = high if value == '1' else low
                        painter.drawLine(QPointF(left, level), QPointF(right, level))
                        if timestamp > 0:
                            painter.drawLine(QPointF(left, high), QPointF(left, low))
                    else:
                        inset = min(4, (right - left) / 3)
                        painter.drawPolygon(QPolygonF([QPointF(left, y + 18), QPointF(left + inset, high),
                            QPointF(right - inset, high), QPointF(right, y + 18),
                            QPointF(right - inset, low), QPointF(left + inset, low)]))
                        text = format_value(value, signal['width'], self.radix)
                        if right - left > painter.fontMetrics().horizontalAdvance(text) + 12:
                            painter.drawText(QRectF(left + 5, high, right - left - 10, 20), Qt.AlignmentFlag.AlignCenter, text)
            finally:
                painter.restore()
        painter.setClipping(False)
        cursor_x = x(self.cursor)
        if self.LEFT <= cursor_x <= self.viewport().width():
            painter.setPen(QPen(QColor('#d1b578'), 1))
            painter.drawLine(QPointF(cursor_x, self.TOP), QPointF(cursor_x, self.viewport().height()))
