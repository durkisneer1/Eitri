"""Qt text editor with a line-number gutter and VHDL lexical highlighting."""
from .theme import theme_color
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
    source_changed = Signal()
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
        self._source_text = self.toPlainText()
        self.textChanged.connect(self.check_source_change)

    def check_source_change(self):
        # Qt also emits textChanged for formatting (including rehighlighting).
        # Builds and diagnostics must only react to changes in the VHDL source.
        text = self.toPlainText()
        if text != self._source_text:
            self._source_text = text
            self.source_changed.emit()

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
        selection.format.setBackground(QColor(theme_color('#30302d')))
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
            mark.format.setUnderlineColor(QColor(theme_color('#e58c7c' if diagnostic.get('severity', 1) == 1 else '#d1b578')))
            mark.format.setToolTip(diagnostic['message'])
            selections.append(mark)
        self.setExtraSelections(selections)
        self.gutter.update()

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(theme_color('#242423')))
        painter.setFont(self.font())
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                active = block.blockNumber() == self.textCursor().blockNumber()
                painter.setPen(QColor(theme_color('#c9bb9f' if active else '#817c73')))
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

    TAB_WIDTH = 4

    def indent_lines(self, unindent=False):
        """Indent whole selected lines as one edit, preserving selection direction."""
        if self.isReadOnly():
            return
        cursor = self.textCursor()
        selected = cursor.hasSelection()
        backwards = cursor.position() < cursor.anchor()
        start = QTextCursor(self.document())
        start.setPosition(cursor.selectionStart())
        start.setKeepPositionOnInsert(True)
        end = QTextCursor(self.document())
        end.setPosition(cursor.selectionEnd())
        first = self.document().findBlock(cursor.selectionStart())
        # A selection ending at the next line's start does not include that line.
        last = self.document().findBlock(cursor.selectionEnd() - (1 if selected else 0))
        edits = []
        block = first
        while block.isValid() and block.blockNumber() <= last.blockNumber():
            remove = 0
            if unindent:
                columns = 0
                for char in block.text():
                    if char not in ' \t' or columns >= self.TAB_WIDTH:
                        break
                    columns += self.TAB_WIDTH - columns % self.TAB_WIDTH if char == '\t' else 1
                    remove += 1
            if remove or not unindent:
                edits.append((block.position(), remove, '' if unindent else ' ' * self.TAB_WIDTH))
            block = block.next()
        if not edits:
            return
        edit = QTextCursor(self.document())
        edit.beginEditBlock()
        for position, remove, replacement in reversed(edits):
            edit.setPosition(position)
            edit.setPosition(position + remove, QTextCursor.MoveMode.KeepAnchor)
            edit.insertText(replacement)
        edit.endEditBlock()
        if selected:
            cursor.setPosition(end.position() if backwards else start.position())
            cursor.setPosition(start.position() if backwards else end.position(), QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(end.position())
        self.setTextCursor(cursor)

    def backspace_indent(self):
        cursor = self.textCursor()
        if cursor.hasSelection() or self.isReadOnly():
            return False
        # Work in Qt positions when slicing text containing non-BMP characters.
        prefix = cursor.block().text().encode('utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le')
        if not prefix or prefix.strip(' \t'):
            return False
        columns = len(prefix.expandtabs(self.TAB_WIDTH))
        if columns % self.TAB_WIDTH:
            return False
        target, keep, width = columns - self.TAB_WIDTH, 0, 0
        for char in prefix:
            if width >= target:
                break
            width += self.TAB_WIDTH - width % self.TAB_WIDTH if char == '\t' else 1
            keep += 1
        cursor.beginEditBlock()
        cursor.setPosition(cursor.block().position() + keep, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        return True

    def keyPressEvent(self, event):
        plain = not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier |
                    Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier))
        if event.key() == Qt.Key.Key_F12:
            self.definition_requested.emit()
        elif self.isReadOnly():
            super().keyPressEvent(event)
        elif plain and (event.key() == Qt.Key.Key_Backtab or
                        (event.key() == Qt.Key.Key_Tab and event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self.indent_lines(unindent=True)
        elif plain and event.key() == Qt.Key.Key_Tab:
            if self.textCursor().hasSelection():
                self.indent_lines()
            else:
                cursor = self.textCursor()
                prefix = cursor.block().text().encode('utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le')
                self.insertPlainText(' ' * (self.TAB_WIDTH - len(prefix.expandtabs(self.TAB_WIDTH)) % self.TAB_WIDTH))
        elif plain and event.key() == Qt.Key.Key_Backspace and self.backspace_indent():
            pass
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self.textCursor().hasSelection():
            cursor = self.textCursor()
            prefix = cursor.block().text().encode('utf-16-le')[:cursor.positionInBlock() * 2].decode('utf-16-le')
            indent = re.match(r'[ \t]*', prefix).group()
            cursor.beginEditBlock()
            cursor.insertText('\n' + indent)
            cursor.endEditBlock()
            self.setTextCursor(cursor)
        else:
            super().keyPressEvent(event)
