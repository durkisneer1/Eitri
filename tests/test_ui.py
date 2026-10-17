"""Headless checks for editing behavior and document safety."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox
from eitri.ui.window import Workspace


@pytest.fixture(scope='module')
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def window(app):
    widget = Workspace()
    yield widget
    for editor in widget.code_page.editors:
        editor.document().setModified(False)
    widget.close()
    widget.deleteLater()
    app.processEvents()


def test_mode_switch_keeps_editor_and_parameters(window):
    window.editor.setPlainText('entity demo is end;')
    window.sidebar.testbench.setText('demo_tb')
    for index in (1, 2, 0):
        window.switch_mode(index)
        assert window.views.currentIndex() == index
        assert window.sidebar.options.currentIndex() == index
        assert window.toolbar.mode_buttons.checkedId() == index
    assert window.editor.toPlainText() == 'entity demo is end;'
    assert window.sidebar.testbench.text() == 'demo_tb'


def test_save_roundtrip_and_undo_dirty_state(window, tmp_path):
    target = tmp_path / 'unicode source.vhd'
    window.editor.setPlainText('-- café 🛠\nentity demo is end;\n')
    assert window.write(target)
    assert not window.editor.document().isModified()
    cursor = window.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText('-- change')
    assert window.editor.document().isModified()
    window.editor.undo()
    assert not window.editor.document().isModified()
    assert window.load(target)
    assert window.editor.toPlainText() == target.read_text(encoding='utf-8')


def test_cancel_and_failed_save_preserve_document(window, monkeypatch):
    window.editor.insertPlainText('-- unsaved\n')
    before = window.editor.toPlainText()
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Cancel)
    window.new_file()
    assert window.editor.toPlainText() == before
    assert not window.close()
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(window, 'save', lambda: False)
    assert not window.confirm_discard()
    assert window.editor.toPlainText() == before


def test_find_wraps_without_destroying_selection_on_miss(window):
    window.editor.setPlainText('entity demo is end entity;')
    window.code_page.search.setText('entity')
    window.code_page.find_next()
    assert window.editor.textCursor().selectionStart() == 0
    window.code_page.find_next()
    assert window.editor.textCursor().selectionStart() == 19
    window.code_page.find_next()
    assert window.editor.textCursor().selectionStart() == 0
    window.code_page.search.setText('missing')
    window.code_page.find_next()
    assert window.editor.textCursor().selectedText() == 'entity'


def color_at(block, offset):
    for span in block.layout().formats():
        if span.start <= offset < span.start + span.length:
            return span.format.foreground().color().name()
    return None


def test_vhdl_comments_strings_case_and_utf16_offsets(window):
    text = 'ENTITY demo IS\nreport "🛠 -- not a comment"; -- actual comment\n/* multi\nline */ signal value : std_logic;'
    window.editor.setPlainText(text)
    window.editor.highlighter.rehighlight()
    document = window.editor.document()
    assert color_at(document.firstBlock(), 0) == '#bba7c4'
    block = document.findBlockByNumber(1)
    assert color_at(block, 12) == '#c9bc91'
    comment_offset = len(block.text()[:block.text().rfind('--')].encode('utf-16-le')) // 2
    assert color_at(block, comment_offset) == '#928c81'
    assert document.findBlockByNumber(2).userState() == 1
    block = document.findBlockByNumber(3)
    assert color_at(block, 0) == '#928c81'
    assert color_at(block, 8) == '#bba7c4'
    assert block.userState() == 0


def test_tabs_keep_independent_paths_undo_and_cursor(window, tmp_path):
    design = tmp_path / 'design.vhd'
    bench = tmp_path / 'testbench.vhd'
    window.editor.setPlainText('entity design is end;')
    assert window.write(design)
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText('\n-- design edit')
    design_cursor = window.editor.textCursor().position()
    window.code_page.code_tabs.setCurrentIndex(1)
    assert window.path is None
    assert window.editor.toPlainText() == ''
    window.editor.setPlainText('entity bench is end;')
    assert window.write(bench)
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText('\n-- bench edit')
    window.editor.undo()
    assert not window.editor.document().isModified()
    window.code_page.code_tabs.setCurrentIndex(0)
    assert window.path == design
    assert window.editor.document().isModified()
    assert window.editor.textCursor().position() == design_cursor
    assert window.code_page.code_tabs.tabText(0).endswith(' •')
    window.editor.undo()
    assert window.editor.toPlainText() == 'entity design is end;'
    window.code_page.code_tabs.setCurrentIndex(1)
    assert window.path == bench
    assert window.editor.toPlainText() == 'entity bench is end;'


def test_close_checks_both_tabs_and_cancel_keeps_edits(window, monkeypatch):
    window.code_page.editors[0].insertPlainText('-- edited design\n')
    window.code_page.editors[1].insertPlainText('-- edited testbench\n')
    choices = iter([QMessageBox.StandardButton.Discard, QMessageBox.StandardButton.Cancel])
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: next(choices))
    assert not window.close()
    assert window.code_page.code_tabs.currentIndex() == 1
    assert all(editor.document().isModified() for editor in window.code_page.editors)


def test_cannot_overwrite_other_tabs_file(window, tmp_path, monkeypatch):
    path = tmp_path / 'design.vhd'
    assert window.write(path)
    original = path.read_text()
    window.code_page.code_tabs.setCurrentIndex(1)
    window.editor.insertPlainText('-- testbench')
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Ok)
    assert not window.write(path)
    assert path.read_text() == original
    assert window.editor.document().isModified()


@pytest.mark.parametrize('width,height', [(1440, 820), (1280, 700), (1024, 600)])
def test_launch_size_leaves_screen_clearance(width, height):
    from PySide6.QtCore import QSize
    from eitri.ui.sizing import launch_size
    size = launch_size(QSize(width, height))
    assert size.width() <= min(1140, width - 80)
    assert size.height() <= min(620, height - 100)
    assert size.height() <= height * 0.82


def test_document_dialogs_use_window_parent(window, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    def cancel(parent, *args):
        assert parent is window
        return '', ''

    monkeypatch.setattr(QFileDialog, 'getOpenFileName', cancel)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', cancel)
    window.open_file()
    assert not window.save_as()

    def reject(parent, *args):
        assert parent is window
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, 'warning', reject)
    window.editor.insertPlainText('-- edit')
    assert not window.confirm_discard()


def test_toolbar_signals_and_find_menu(window):
    from PySide6.QtGui import QAction
    window.toolbar.mode_buttons.button(2).click()
    assert window.views.currentIndex() == 2
    assert window.sidebar.options.currentIndex() == 2
    find = next(action for action in window.findChildren(QAction) if action.text() == 'Find…')
    find.trigger()
    assert window.views.currentIndex() == 0
    assert not window.code_page.find_bar.isHidden()


def test_explicit_testbench_open_preserves_design(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    design = window.code_page.editors[0]
    design.setPlainText('-- design remains')
    target = tmp_path / 'sample_TB.vhd'
    target.write_text('-- opened testbench')
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(target), ''))
    window.sidebar.open_testbench_requested.emit()
    assert design.toPlainText() == '-- design remains'
    assert window.code_page.code_tabs.currentIndex() == 1
    assert window.paths[1] == target
    assert window.sidebar.save_button.text() == 'Save testbench'
    window.code_page.code_tabs.setCurrentIndex(0)
    assert window.sidebar.save_button.text() == 'Save design'


def test_centered_icon_navigation(window, app):
    from PySide6.QtWidgets import QPushButton
    window.resize(1140, 620)
    window.show()
    app.processEvents()
    buttons = window.toolbar.mode_buttons.buttons()
    assert len(window.toolbar.findChildren(QPushButton)) == 3
    for item, title in zip(buttons, ('Code', 'Simulation', 'Circuit')):
        assert not item.text()
        assert not item.icon().isNull()
        assert item.toolTip() == title
        assert item.accessibleName() == title
    left = buttons[0].mapTo(window.toolbar, buttons[0].rect().topLeft()).x()
    right = buttons[-1].mapTo(window.toolbar, buttons[-1].rect().topRight()).x()
    assert abs((left + right) / 2 - window.toolbar.width() / 2) <= 1

    # Header and settings share the left split; all pages use the full right height.
    assert window.splitter.widget(0) is window.left_column
    assert window.views.y() == 0
    assert window.views.height() == window.splitter.height()
    assert window.toolbar.width() == window.left_column.width()
