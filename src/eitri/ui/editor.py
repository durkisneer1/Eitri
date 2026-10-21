"""Qt text editor with a line-number gutter and VHDL lexical highlighting."""
import re

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QTextFormat, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget
from .highlighting import VhdlHighlighter
from .fonts import monospace_family

class LineNumbers(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class CodeEditor(QPlainTextEdit):
    hover_requested = Signal(object, object)
    definition_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setFamily(monospace_family())
        font.setPointSize(13)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setPlaceholderText('Write VHDL here, or open a source file…')
        self.diagnostics = []
        self.gutter = LineNumbers(self)
        self.highlighter = VhdlHighlighter(self.document())
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.highlight_line)
        self.update_gutter_width()
        self.highlight_line()

    def gutter_width(self):
        return 24 + self.fontMetrics().horizontalAdvance('9') * len(str(max(1, self.blockCount())))

    def update_gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.gutter.setGeometry(QRect(rect.left(), rect.top(), self.gutter_width(), rect.height()))

    def highlight_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor('#30302d'))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        selections = [selection]
        from .language_server import cursor_at
        for diagnostic in self.diagnostics:
            mark = QTextEdit.ExtraSelection()
            mark.cursor = cursor_at(self, diagnostic['range']['start'])
            end = cursor_at(self, diagnostic['range']['end']).position()
            if end <= mark.cursor.position():
                end = min(mark.cursor.position() + 1, self.document().characterCount() - 1)
            mark.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            mark.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            mark.format.setUnderlineColor(QColor('#e58c7c' if diagnostic.get('severity', 1) == 1 else '#d1b578'))
            mark.format.setToolTip(diagnostic['message'])
            selections.append(mark)
        self.setExtraSelections(selections)
        self.gutter.update()

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor('#242423'))
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                active = block.blockNumber() == self.textCursor().blockNumber()
                painter.setPen(QColor('#c9bb9f' if active else '#817c73'))
                painter.drawText(0, top, self.gutter.width() - 12, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block.blockNumber() + 1))
            top += height
            block = block.next()

    def set_diagnostics(self, diagnostics):
        self.diagnostics = diagnostics
        self.highlight_line()

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            from .language_server import server_position
            self.hover_requested.emit(server_position(self.cursorForPosition(event.pos())), event.globalPos())
            return True
        return super().viewportEvent(event)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        action = menu.addAction('Go to definition (F12)')
        action.triggered.connect(self.definition_requested.emit)
        menu.exec(event.globalPos())
        menu.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F12:
            self.definition_requested.emit()
        elif event.key() == Qt.Key.Key_Tab and not self.textCursor().hasSelection():
            self.insertPlainText('    ')
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self.textCursor().hasSelection():
            cursor = self.textCursor()
            prefix = cursor.block().text()[:cursor.positionInBlock()]
            indent = re.match(r'\s*', prefix).group()
            cursor.beginEditBlock()
            cursor.insertText('\n' + indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
        else:
            super().keyPressEvent(event)
