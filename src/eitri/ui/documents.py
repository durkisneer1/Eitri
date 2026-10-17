"""Open/save dialogs, safe disk writes and unsaved-edit prompts.

The window selects the active editor; this controller performs file operations.
No widgets are constructed here except native dialogs.
"""
from pathlib import Path
from eitri.backend.dependencies import rebase_references
from typing import TYPE_CHECKING
from PySide6.QtCore import QIODevice, QSaveFile
from PySide6.QtWidgets import QFileDialog, QMessageBox

if TYPE_CHECKING:
    from .window import Workspace


class DocumentController:
    def __init__(self, window: 'Workspace'):
        self.window = window

    def confirm_discard(self):
        if not self.window.editor.document().isModified():
            return True
        choice = QMessageBox.warning(self.window, 'Unsaved changes', f'Save changes to {self.window.code_page.code_tabs.tabText(self.window.code_page.code_tabs.currentIndex()).rstrip(" •")} before continuing?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if choice == QMessageBox.StandardButton.Save:
            return self.window.save()
        return choice == QMessageBox.StandardButton.Discard

    def new_file(self):
        return self.window.design_flow.new_design()

    def open_file(self):
        if self.window.code_page.code_tabs.currentIndex() == 0:
            return self.window.design_flow.open_design()
        return self.open_testbench()

    def open_testbench(self):
        # Explicit action always targets the testbench, regardless of the active tab.
        self.window.switch_mode(0)
        self.window.code_page.code_tabs.setCurrentIndex(1)
        if not self.window.confirm_discard():
            return False
        filename, _ = QFileDialog.getOpenFileName(self.window, 'Open VHDL testbench', '', 'VHDL files (*.vhd *.vhdl);;All files (*)')
        if filename:
            return self.window.load(Path(filename))
        return False

    def load(self, path):
        other = 1 - self.window.code_page.code_tabs.currentIndex()
        if self.window.paths[other] and path.resolve() == self.window.paths[other].resolve():
            self.window.code_page.code_tabs.setCurrentIndex(other)
            self.window.switch_mode(0)
            self.window.statusBar().showMessage('This file is already open in the other editor tab.', 5000)
            return True
        try:
            content = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            QMessageBox.critical(self.window, 'Could not open file', str(error))
            return False
        self.window.path = path
        self.window.editor.setPlainText(content)
        self.window.editor.document().setModified(False)
        self.window.sidebar.file_path.setText(str(path))
        self.window.update_title()
        self.window.switch_mode(0)
        self.window.statusBar().showMessage(f'Opened {path.name}', 5000)
        return True

    def save(self):
        return self.window.write(self.window.path) if self.window.path else self.window.save_as()

    def save_as(self):
        filename, _ = QFileDialog.getSaveFileName(self.window, 'Save VHDL source',
            str(self.window.path) if self.window.path else ('design.vhd', 'testbench.vhd')[self.window.code_page.code_tabs.currentIndex()], 'VHDL files (*.vhd *.vhdl);;All files (*)')
        if not filename:
            return False
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix('.vhd')
            if path.exists() and QMessageBox.question(self.window, 'Replace file?', f'Replace {path.name}?') != QMessageBox.StandardButton.Yes:
                return False
        return self.window.write(path)

    def write(self, path):
        other = 1 - self.window.code_page.code_tabs.currentIndex()
        if self.window.paths[other] and path.resolve() == self.window.paths[other].resolve():
            QMessageBox.warning(self.window, 'File already open', 'Choose a different filename; the other editor tab owns this file.')
            return False
        text = self.window.editor.toPlainText()
        try:
            text = rebase_references(text, self.window.path, path)
        except ValueError as error:
            QMessageBox.warning(self.window, 'Cannot save source references', str(error))
            return False
        if not self.write_text(path, text):
            return False
        self.window.path = path
        if text != self.window.editor.toPlainText():
            self.window.editor.setPlainText(text)
        self.window.editor.document().setModified(False)
        self.window.sidebar.file_path.setText(str(path))
        self.window.update_title()
        self.window.statusBar().showMessage(f'Saved {path.name}', 5000)
        return True


    def write_text(self, path, text):
        """Commit disk contents before changing paths or clearing dirty markers."""
        target = QSaveFile(str(path))
        data = text.encode('utf-8')
        if not target.open(QIODevice.OpenModeFlag.WriteOnly):
            QMessageBox.critical(self.window, 'Could not save file', target.errorString())
            return False
        if target.write(data) != len(data):
            target.cancelWriting()
            QMessageBox.critical(self.window, 'Could not save file', target.errorString())
            return False
        if not target.commit():
            QMessageBox.critical(self.window, 'Could not save file', target.errorString())
            return False
        return True
