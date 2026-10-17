"""Compose the workspace and connect its widgets to application actions.

Start here for the big picture. Each imported widget owns its own layout;
documents.py handles files, and editor.py handles text-editing behavior.
"""
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QSplitter, QStackedWidget, QVBoxLayout, QWidget

from .actions import install_actions
from .app_icon import application_icon
from .code_page import CodePage
from .documents import DocumentController
from .design_flow import DesignFlow
from .simulation import SimulationPage
from .circuit import CircuitPage
from .tool_controller import ToolController
from .sidebar import Sidebar
from .sizing import fit_window
from .theme import workspace_style
from .fonts import configure_application_font
from .toolbar import Toolbar
from .widgets import label


class Workspace(QMainWindow):
    def __init__(self, run_root=None):
        super().__init__()

        configure_application_font(QApplication.instance())
        icon = application_icon()
        QApplication.instance().setWindowIcon(icon)
        self.setWindowIcon(icon)
        self.paths: list[Path | None] = [None, None]
        self.setStyleSheet(workspace_style())

        # Construct each independent page before wiring cross-page actions.
        self.documents = DocumentController(self)
        self.design_flow = DesignFlow(self)
        self.toolbar = Toolbar()
        self.sidebar = Sidebar()
        self.code_page = CodePage()
        self.views = QStackedWidget()
        self.views.setMinimumWidth(350)
        self.views.addWidget(self.code_page)
        self.simulation_page = SimulationPage()
        self.circuit_page = CircuitPage()
        self.views.addWidget(self.simulation_page)
        self.views.addWidget(self.circuit_page)
        self.tools = ToolController(self, run_root)

        # The left column owns navigation and settings. Pages span the full
        # content height, so the editor and previews gain the former header space.
        self.left_column = QWidget()
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.toolbar)
        left_layout.addWidget(self.sidebar, 1)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(3)
        self.splitter.addWidget(self.left_column)
        self.splitter.addWidget(self.views)
        self.splitter.setSizes([270, 870])
        self.splitter.setStretchFactor(1, 1)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.splitter, 1)

        self.setCentralWidget(root)
        self.page_name = label('')
        self.statusBar().addWidget(self.page_name, 1)
        self.position = label('')
        self.statusBar().addPermanentWidget(self.position)

        # Signal wiring: widgets emit intent; controllers perform the work.
        self.toolbar.mode_changed.connect(self.switch_mode)
        self.sidebar.open_design_requested.connect(self.design_flow.open_design)
        self.sidebar.open_testbench_requested.connect(self.documents.open_testbench)
        self.sidebar.save_requested.connect(self.save)
        self.sidebar.new_requested.connect(self.new_file)
        self.sidebar.save_as_requested.connect(self.save_as)
        self.code_page.create_testbench_requested.connect(self.design_flow.create_testbench)
        self.code_page.message.connect(self.statusBar().showMessage)
        self.code_page.code_tabs.currentChanged.connect(self.active_document_changed)

        for editor in self.code_page.editors:
            editor.cursorPositionChanged.connect(self.update_position)
            editor.document().modificationChanged.connect(self.update_title)

        install_actions(self)
        self.active_document_changed()
        fit_window(self)

    @property
    def editor(self):
        """The currently selected design or testbench editor."""
        return self.code_page.editor

    @property
    def path(self):
        return self.paths[self.code_page.code_tabs.currentIndex()]

    @path.setter
    def path(self, value):
        self.paths[self.code_page.code_tabs.currentIndex()] = value

    def active_document_changed(self, *_):
        self.sidebar.set_document_role(self.code_page.code_tabs.currentIndex())
        self.update_title()
        self.update_position()
        self.update_page_name()
        self.editor.setFocus()

    def switch_mode(self, index):
        self.views.setCurrentIndex(index)
        self.sidebar.options.setCurrentIndex(index)
        self.toolbar.mode_buttons.button(index).setChecked(True)
        self.update_page_name()

    def update_page_name(self):
        # The page label returns after temporary save/open/find messages expire.
        code_title = ('Code - Design', 'Code - Testbench')[self.code_page.code_tabs.currentIndex()]
        self.page_name.setText((code_title, 'Simulation and Synthesis', 'Circuit Diagram')[self.views.currentIndex()])
        self.statusBar().clearMessage()

    def update_title(self, *_):
        names = ('Design', 'Testbench')
        tabs = self.code_page.code_tabs

        for index, (title, editor) in enumerate(zip(names, self.code_page.editors)):
            suffix = ' •' if editor.document().isModified() else ''
            tabs.setTabText(index, title + suffix)
            tabs.setTabToolTip(index, str(self.paths[index]) if self.paths[index] else f'Unsaved {title.lower()} source')

        role = names[tabs.currentIndex()]
        name = self.path.name if self.path else f'Untitled {role.lower()}.vhd'
        suffix = ' •' if self.editor.document().isModified() else ''

        self.code_page.document_name.setText(name + suffix)
        self.sidebar.file_path.setText(str(self.path) if self.path else f'{role} · not saved')
        self.setWindowTitle(f'{name}{suffix} — Eitri')

    def update_position(self):
        cursor = self.editor.textCursor()
        self.position.setText(f'Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}    |    UTF-8    |    VHDL')

    # Public actions shared by toolbar buttons, menus and tests.
    def confirm_discard(self):
        return self.documents.confirm_discard()

    def new_file(self):
        return self.documents.new_file()

    def open_file(self):
        return self.documents.open_file()

    def load(self, path):
        return self.documents.load(path)

    def save(self):
        return self.documents.save()

    def save_as(self):
        return self.documents.save_as()

    def write(self, path):
        return self.documents.write(path)

    def show_find(self):
        self.switch_mode(0)
        self.code_page.show_find()

    def closeEvent(self, event):
        # Cancel tool trees before Qt destroys timers, then handle dirty files.
        if not self.tools.prepare_close():
            event.ignore()
            return
        
        tabs = self.code_page.code_tabs
        original = tabs.currentIndex()

        for index, editor in enumerate(self.code_page.editors):
            if editor.document().isModified():
                tabs.setCurrentIndex(index)
                if not self.confirm_discard():
                    self.switch_mode(0)
                    event.ignore()
                    return
                
        tabs.setCurrentIndex(original)
        event.accept()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Eitri')
    app.setOrganizationName('Eitri')
    app.setStyle('Fusion')  # type: ignore
    
    window = Workspace()
    window.show()

    # Defer onboarding until Qt has sized and displayed the parent window.
    QTimer.singleShot(0, window.design_flow.startup)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
