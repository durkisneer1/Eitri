"""Persistent document buffers, safe writes and external-change protection."""
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import QIODevice, QSaveFile
from PySide6.QtWidgets import QFileDialog, QMessageBox
from .editor import CodeEditor


@dataclass
class Document:
    path: Path | None
    editor: CodeEditor
    disk_text: str = ''
    conflict: bool = False


class DocumentController:
    def __init__(self, window):
        self.window = window
        self.records = []

    @property
    def active(self):
        return next((d for d in self.records if d.editor is self.window.editor), None)

    def add(self, path=None, text='', readonly=False):
        editor = CodeEditor()
        editor.setPlainText(text)
        editor.document().setModified(False)
        editor.setReadOnly(readonly)
        record = Document(Path(path).resolve() if path else None, editor, text)
        self.records.append(record)
        self.window.code_page.add_editor(editor, path.name if path else 'Untitled.vhd')
        self.window.connect_editor(editor)
        return record

    def overlays(self):
        return {str(d.path): d.editor.toPlainText() for d in self.records if d.path and not d.editor.isReadOnly()}

    def load(self, path, line=None):
        path = Path(path).resolve()
        record = next((d for d in self.records if d.path == path), None)
        if record is None:
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeError) as error:
                QMessageBox.warning(self.window, 'Could not open file', str(error))
                return False
            readonly = bool(self.window.project and not path.is_relative_to(self.window.project.root))
            scratch = next((d for d in self.records if d.path is None and not d.editor.toPlainText() and not d.editor.document().isModified()), None)
            if scratch:
                record = scratch
                record.path, record.disk_text = path, text
                record.editor.setPlainText(text)
                record.editor.document().setModified(False)
                record.editor.setReadOnly(readonly)
            else:
                record = self.add(path, text, readonly)
        self.window.code_page.code_tabs.setCurrentWidget(record.editor)
        if line is not None:
            from .language_server import cursor_at
            record.editor.setTextCursor(cursor_at(record.editor, {'line': line, 'character': 0}))
            record.editor.centerCursor()
        self.window.switch_mode(0)
        self.window.update_title()
        self.refresh_conflict()
        return True

    def confirm_discard(self, record=None):
        record = record or self.active
        if not record or not record.editor.document().isModified():
            return True
        self.window.code_page.code_tabs.setCurrentWidget(record.editor)
        choice = QMessageBox.warning(self.window, 'Unsaved changes', f'Save changes to {record.path.name if record.path else "Untitled"}?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if choice == QMessageBox.StandardButton.Save:
            return self.window.save()
        return choice == QMessageBox.StandardButton.Discard

    def confirm_all(self):
        return all(self.confirm_discard(record) for record in self.records)

    def clear(self):
        for record in self.records:
            self.window.code_page.code_tabs.removeTab(0)
            record.editor.deleteLater()
        self.records.clear()
        self.window.code_page.editors.clear()

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(self.window, 'Open source', str(self.window.project.root) if self.window.project else '', 'VHDL files (*.vhd *.vhdl)')
        return self.load(Path(filename)) if filename else False

    def save(self):
        if not self.active:
            return False
        return self.write(self.active.path) if self.active.path else self.save_as()

    def save_as(self):
        filename, _ = QFileDialog.getSaveFileName(self.window, 'Save source', str(self.active.path or (self.window.project.root / 'untitled.vhd' if self.window.project else 'untitled.vhd')), 'VHDL files (*.vhd *.vhdl)')
        if not filename:
            return False
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix('.vhd')
        return self.write(path)

    def save_all(self):
        original = self.window.editor
        for record in self.records:
            if record.editor.document().isModified():
                self.window.code_page.code_tabs.setCurrentWidget(record.editor)
                if not self.save():
                    return False
        self.window.code_page.code_tabs.setCurrentWidget(original)
        return True

    def write(self, path):
        record = self.active
        if not record or record.editor.isReadOnly():
            return False
        path = Path(path).resolve()
        if any(d is not record and d.path == path for d in self.records):
            QMessageBox.warning(self.window, 'File already open', 'That file already has an editor buffer. Choose another filename.')
            return False
        try:
            disk = path.read_text(encoding='utf-8') if path.exists() else None
        except (OSError, UnicodeError) as error:
            QMessageBox.warning(self.window, 'Cannot read destination', str(error))
            return False
        if disk is not None and ((path == record.path and disk != record.disk_text) or path != record.path):
            if QMessageBox.question(self.window, 'Replace disk contents?', f'{path.name} already exists or changed outside Eitri. Replace its disk contents with this buffer?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return False
        from eitri.backend.dependencies import rebase_references
        text = rebase_references(record.editor.toPlainText(), record.path, path)
        if not self.write_text(path, text):
            return False
        record.path, record.disk_text, record.conflict = path, text, False
        if text != record.editor.toPlainText():
            record.editor.setPlainText(text)
        record.editor.document().setModified(False)
        self.window.refresh_project()
        self.window.update_title()
        self.refresh_conflict()
        return True

    def write_text(self, path, text):
        target = QSaveFile(str(path))
        data = text.encode('utf-8')
        if not target.open(QIODevice.OpenModeFlag.WriteOnly) or target.write(data) != len(data) or not target.commit():
            QMessageBox.critical(self.window, 'Could not save file', target.errorString())
            return False
        return True

    def check_external(self):
        changed = False
        for record in self.records:
            if not record.path:
                continue
            try:
                disk = record.path.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                record.conflict = True
                continue
            if disk == record.disk_text:
                continue
            changed = True
            if record.editor.document().isModified():
                record.conflict = True
            else:
                cursor = record.editor.textCursor().position()
                scroll = record.editor.verticalScrollBar().value()
                record.editor.setPlainText(disk)
                record.editor.document().setModified(False)
                c = record.editor.textCursor()
                c.setPosition(min(cursor, record.editor.document().characterCount() - 1))
                record.editor.setTextCursor(c)
                record.editor.verticalScrollBar().setValue(scroll)
                record.disk_text = disk
                record.conflict = False
        self.refresh_conflict()
        return changed

    def refresh_conflict(self):
        self.window.code_page.conflict_bar.setVisible(bool(self.active and self.active.conflict))

    def reload_active(self):
        record = self.active
        if not record or not record.path:
            return
        if record.editor.document().isModified() and QMessageBox.question(self.window, 'Discard buffer edits?', 'Reloading replaces your unsaved edits with the disk version.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            text = record.path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            QMessageBox.warning(self.window, 'Cannot reload', str(error))
            return
        record.editor.setPlainText(text)
        record.editor.document().setModified(False)
        record.disk_text, record.conflict = text, False
        self.refresh_conflict()

    def keep_active(self):
        record = self.active
        if record and record.path:
            try:
                record.disk_text = record.path.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                record.disk_text = ''
            record.conflict = False
            record.editor.document().setModified(True)
        self.refresh_conflict()
