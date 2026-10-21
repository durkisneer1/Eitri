"""One visible editor; document buffers retain their cursor and undo history."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QListWidget, QHBoxLayout, QLineEdit, QTabWidget, QVBoxLayout, QWidget
from .widgets import button, label


class CodePage(QWidget):
    message = Signal(str, int)
    create_testbench_requested = Signal()
    insert_instance_requested = Signal()
    editor_added = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QHBoxLayout()
        title.setContentsMargins(16, 10, 16, 4)
        self.document_name = label('Open a folder to begin')
        self.document_name.setWordWrap(True)
        title.addWidget(self.document_name, 1)
        title.addWidget(button('Insert instance…', self.insert_instance_requested.emit))
        self.create_testbench = button('Create testbench…', self.create_testbench_requested.emit)
        title.addWidget(self.create_testbench)
        layout.addLayout(title)
        self.conflict_bar = QWidget()
        row = QHBoxLayout(self.conflict_bar)
        self.conflict_message = label('File changed outside Eitri.')
        row.addWidget(self.conflict_message, 1)
        self.reload_button = button('Reload from disk', lambda: None)
        self.keep_button = button('Keep my edits', lambda: None)
        row.addWidget(self.reload_button)
        row.addWidget(self.keep_button)
        self.conflict_bar.hide()
        layout.addWidget(self.conflict_bar)
        self.find_bar = QWidget()
        find = QHBoxLayout(self.find_bar)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find in this file…')
        self.search.returnPressed.connect(self.find_next)
        find.addWidget(self.search)
        find.addWidget(button('Next', self.find_next))
        find.addWidget(button('Close', self.find_bar.hide))
        self.find_bar.hide()
        layout.addWidget(self.find_bar)
        self.code_tabs = QTabWidget()
        self.code_tabs.tabBar().hide()
        self.editors = []
        layout.addWidget(self.code_tabs, 1)
        self.problems = QListWidget()
        self.problems.setMaximumHeight(140)
        self.problems.hide()
        layout.addWidget(self.problems)
        footer = QHBoxLayout()
        self.assistance = QCheckBox('VHDL assistance')
        self.assistance.setChecked(True)
        self.lsp_status = label('Open a folder · diagnostics, hover and F12 definition')
        self.lsp_status.setWordWrap(True)
        footer.addWidget(self.assistance)
        footer.addWidget(self.lsp_status, 1)
        layout.addLayout(footer)

    @property
    def editor(self):
        return self.code_tabs.currentWidget()

    def add_editor(self, editor, name):
        self.editors.append(editor)
        index = self.code_tabs.addTab(editor, name)
        self.editor_added.emit(editor)
        self.code_tabs.setCurrentIndex(index)

    def show_find(self):
        self.find_bar.show()
        self.search.setFocus()
        self.search.selectAll()

    def find_next(self):
        if not self.editor or not self.search.text():
            return
        found = self.editor.document().find(self.search.text(), self.editor.textCursor())
        if found.isNull():
            found = self.editor.document().find(self.search.text(), 0)
        if found.isNull():
            self.message.emit('No matches in this file.', 4000)
        else:
            self.editor.setTextCursor(found)
            self.editor.ensureCursorVisible()
