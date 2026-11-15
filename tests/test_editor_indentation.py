"""Exercise actual keyboard events, cursor direction and undo in the editor."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from eitri.ui.editor import CodeEditor


@pytest.fixture
def editor(qt_application_lifetime):
    editor = CodeEditor()
    editor.show()
    editor.setFocus()
    yield editor
    editor.close()
    editor.deleteLater()


def select(editor, anchor, position):
    text = editor.toPlainText()
    cursor = editor.textCursor()
    cursor.setPosition(len(text[:anchor].encode('utf-16-le')) // 2)
    cursor.setPosition(len(text[:position].encode('utf-16-le')) // 2, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


@pytest.mark.parametrize('backwards', (False, True))
def test_selected_lines_indent_unindent_and_undo(editor, backwards):
    source = 'a <= b;\n    c <= d;\nlast;'
    editor.setPlainText(source)
    end = source.index('last')
    select(editor, end if backwards else 0, 0 if backwards else end)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == '    a <= b;\n        c <= d;\nlast;'
    assert (editor.textCursor().position() < editor.textCursor().anchor()) == backwards
    assert editor.textCursor().hasSelection()
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert editor.toPlainText() == source
    editor.undo()
    assert editor.toPlainText() == '    a <= b;\n        c <= d;\nlast;'
    editor.undo()
    assert editor.toPlainText() == source
    editor.redo()
    assert editor.toPlainText() == '    a <= b;\n        c <= d;\nlast;'


def test_partial_selection_and_unicode_preserved(editor):
    source = '-- 🙂 notes\n  hello\nworld'
    editor.setPlainText(source)
    select(editor, 4, source.index('hello') + 3)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == '    -- 🙂 notes\n      hello\nworld'
    assert editor.textCursor().selectedText() == ' notes\u2029      hel'


@pytest.mark.parametrize('prefix,expected', [('    ', ''), ('        ', '    '), ('      ', '     '),
                                          ('  ', ' '), ('\t', ''), ('  \t', ''), ('\t    ', '\t')])
def test_backspace_indentation_stop(editor, prefix, expected):
    editor.setPlainText(prefix + 'signal a;')
    select(editor, len(prefix), len(prefix))
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == expected + 'signal a;'
    editor.undo()
    assert editor.toPlainText() == prefix + 'signal a;'


def test_backspace_does_not_remove_code_or_expand_selection(editor):
    editor.setPlainText('    abc    ')
    select(editor, 11, 11)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == '    abc   '
    select(editor, 0, 2)
    QTest.keyClick(editor, Qt.Key.Key_Backspace)
    assert editor.toPlainText() == '  abc   '


def test_tab_to_next_stop_and_shift_tab_on_single_line(editor):
    editor.setPlainText('  value')
    select(editor, 2, 2)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == '    value'
    QTest.keyClick(editor, Qt.Key.Key_Backtab)
    assert editor.toPlainText() == 'value'
    assert editor.textCursor().position() == 0
    editor.setPlainText('  \t    value')
    select(editor, 8, 8)
    QTest.keyClick(editor, Qt.Key.Key_Backtab)
    assert editor.toPlainText() == '    value'


def test_blank_lines_and_read_only(editor):
    editor.setPlainText('a\n\nb')
    select(editor, 0, 4)
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == '    a\n    \n    b'
    editor.setReadOnly(True)
    text = editor.toPlainText()
    for key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Backspace):
        QTest.keyClick(editor, key)
    assert editor.toPlainText() == text
