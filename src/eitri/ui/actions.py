"""Project-wide actions and platform-standard shortcuts."""
from PySide6.QtGui import QAction, QKeySequence


def install_actions(window):
    file_menu = window.menuBar().addMenu('File')
    edit_menu = window.menuBar().addMenu('Edit')
    run_menu = window.menuBar().addMenu('Run')
    view_menu = window.menuBar().addMenu('View')
    for menu, title, shortcut, callback in (
        (file_menu, 'Open folder…', QKeySequence.StandardKey.Open, window.choose_folder),
        (file_menu, 'New design…', QKeySequence.StandardKey.New, window.new_file),
        (file_menu, 'Open file…', QKeySequence(), window.open_file),
        (file_menu, 'Save', QKeySequence.StandardKey.Save, window.save),
        (file_menu, 'Save as…', QKeySequence.StandardKey.SaveAs, window.save_as),
        (file_menu, 'Save all', QKeySequence('Ctrl+Alt+S'), window.documents.save_all),
        (file_menu, 'Quick open…', QKeySequence('Ctrl+P'), window.quick_open),
        (edit_menu, 'Undo', QKeySequence.StandardKey.Undo, lambda: window.editor.undo()),
        (edit_menu, 'Redo', QKeySequence.StandardKey.Redo, lambda: window.editor.redo()),
        (edit_menu, 'Find…', QKeySequence.StandardKey.Find, window.show_find),
        (edit_menu, 'Insert instance…', QKeySequence(), window.design_flow.insert_instance),
        (edit_menu, 'Create testbench…', QKeySequence(), window.design_flow.create_testbench),
        (run_menu, 'Run selected simulation', QKeySequence('F5'), lambda: window.tools.start('simulation')),
        (run_menu, 'Generate selected circuit', QKeySequence('F6'), lambda: window.tools.start('circuit')),
        (run_menu, 'Run all tests', QKeySequence('Shift+F5'), window.tools.run_all),
        (run_menu, 'Stop all runs', QKeySequence('Shift+Escape'), window.tools.stop_all),
        (view_menu, 'Component hierarchy', QKeySequence('F7'), lambda: window.switch_mode(3)),
    ):
        action = QAction(title, window)
        action.setShortcut(shortcut)
        action.triggered.connect(lambda checked=False, fn=callback: fn())
        menu.addAction(action)
        window.addAction(action)
