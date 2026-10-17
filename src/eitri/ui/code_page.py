"""Design/Testbench editors and the shared find bar."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QTabWidget, QVBoxLayout, QWidget
from .editor import CodeEditor
from .widgets import button, label


class CodePage(QWidget):
    message = Signal(str, int)
    create_testbench_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        code_layout = QVBoxLayout(self)
        code_layout.setContentsMargins(0, 0, 0, 0)
        # Filename header is separate from tabs so long names do not resize tabs.
        title_row = QHBoxLayout()
        title_row.setContentsMargins(18, 12, 18, 4)
        self.document_name = label('Untitled.vhd')
        title_row.addWidget(self.document_name)
        title_row.addStretch()
        self.create_testbench = button('Create Testbench', lambda: self.create_testbench_requested.emit())
        title_row.addWidget(self.create_testbench)
        title_row.addWidget(label('VHDL', 'eyebrow'))
        code_layout.addLayout(title_row)
        # Find controls are shared, but search always targets the selected editor.
        self.find_bar = QWidget()
        find_layout = QHBoxLayout(self.find_bar)
        find_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Find in document…')
        self.search.returnPressed.connect(self.find_next)
        find_layout.addWidget(self.search)
        find_layout.addWidget(button('Next', self.find_next))
        find_layout.addWidget(button('Close', self.find_bar.hide))
        self.find_bar.hide()
        code_layout.addWidget(self.find_bar)
        # Separate widgets preserve each document’s cursor and undo history.
        self.code_tabs = QTabWidget()
        self.code_tabs.setDocumentMode(True)
        self.code_tabs.tabBar().setDrawBase(False)
        self.editors = [CodeEditor(), CodeEditor()]
        for title, editor in zip(('Design', 'Testbench'), self.editors):
            self.code_tabs.addTab(editor, title)
        code_layout.addWidget(self.code_tabs, 1)
        # Both buffers start empty; onboarding supplies a design, then the user
        # explicitly generates or opens a matching testbench.
        self.editors[0].setPlaceholderText('Open a design or choose New design to get started.')
        self.editors[1].setPlaceholderText('Use Create Testbench on the Design tab, or open an existing testbench.')
        self.code_tabs.currentChanged.connect(self.refresh_create_button)
        self.editors[0].textChanged.connect(self.refresh_create_button)
        self.refresh_create_button()

    def refresh_create_button(self, *_):
        self.create_testbench.setVisible(self.code_tabs.currentIndex() == 0)
        self.create_testbench.setEnabled(bool(self.editors[0].toPlainText().strip()))

    @property
    def editor(self):
        return self.editors[self.code_tabs.currentIndex()]

    def show_find(self):
        self.find_bar.show()
        self.search.setFocus()
        self.search.selectAll()

    def find_next(self):
        query = self.search.text()
        if not query:
            return
        found = self.editor.document().find(query, self.editor.textCursor())
        if found.isNull():
            found = self.editor.document().find(query, 0)
        if found.isNull():
            self.message.emit(f'No matches for “{query}”', 4000)
        else:
            self.editor.setTextCursor(found)
            self.editor.ensureCursorVisible()

