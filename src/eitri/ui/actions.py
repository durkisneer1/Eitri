"""Application menus and platform-standard keyboard shortcuts."""
from PySide6.QtGui import QAction, QKeySequence


def install_actions(window):
    file_menu = window.menuBar().addMenu('File')
    edit_menu = window.menuBar().addMenu('Edit')
    tools_menu = window.menuBar().addMenu('Run')
    for menu, title, shortcut, callback in (
        (file_menu, 'New design…', QKeySequence.StandardKey.New, window.new_file),
        (file_menu, 'Open design…', QKeySequence.StandardKey.Open, window.design_flow.open_design),
        (file_menu, 'Open testbench…', QKeySequence(), window.documents.open_testbench),
        (file_menu, 'Save', QKeySequence.StandardKey.Save, window.save),
        (file_menu, 'Save as…', QKeySequence.StandardKey.SaveAs, window.save_as),
        (edit_menu, 'Undo', QKeySequence.StandardKey.Undo, lambda: window.editor.undo()),
        (edit_menu, 'Redo', QKeySequence.StandardKey.Redo, lambda: window.editor.redo()),
        (edit_menu, 'Find…', QKeySequence.StandardKey.Find, window.show_find),
        (tools_menu, 'Run simulation', QKeySequence('F5'), lambda: window.tools.start('simulation')),
        (tools_menu, 'Generate circuit', QKeySequence('F6'), lambda: window.tools.start('circuit')),
    ):
        action = QAction(title, window)
        action.setShortcut(shortcut)
        action.triggered.connect(callback)
        menu.addAction(action)
        window.addAction(action)

