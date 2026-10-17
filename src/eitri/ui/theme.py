"""A charcoal, iron and aged-brass palette shared by the Qt workspace."""
STYLE = '''
/* Tool pages: selection and progress stay within the charcoal/brass palette. */
QTableWidget { background: #242423; gridline-color: #45433f; selection-background-color: #575145; }
QTreeWidget, QListWidget { background: #242423; border: 1px solid #45433f; alternate-background-color: #2b2b2b; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #575145; color: #e5dfd3; }
QHeaderView::section { background: #302f2c; color: #dedbd5; padding: 4px; border: none; border-right: 1px solid #45433f; }
QProgressBar { border: none; background: #343330; }
QProgressBar::chunk { background: #c9b58c; }

QTabWidget::pane { border: none; border-top: 1px solid #45433f; }
QTabBar::tab { background: #2b2b2b; color: #aaa59b; padding: 9px 22px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #e5dfd3; background: #343330; border-bottom-color: #c9b58c; }
QTabBar::tab:hover { background: #3b3935; }
QWidget { background: #242424; color: #dedbd5; font-family: ".AppleSystemUIFont", "Segoe UI", sans-serif; font-size: 13px; }
QLabel { background: transparent; }
QMainWindow { background: #202020; }
QFrame#toolbar { background: #2b2b2b; border-bottom: 1px solid #716044; }
QLabel#brand { color: #c9b58c; font-family: "Copperplate", "Palatino Linotype", "Georgia", serif; font-size: 28px; font-weight: 700; letter-spacing: 4px; }
QLabel#muted { color: #a6a29a; }
QLabel#eyebrow { color: #c9b58c; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
QLabel#heading { font-size: 22px; font-weight: 600; }
QFrame#sidebar { background: #2b2b2b; border: none; border-radius: 0; }
QFrame#sidebar QLabel, QFrame#sidebar QWidget { background: transparent; }
QFrame#document { border: none; border-radius: 0; }
QPushButton { background: #343330; border: 1px solid #504d47; border-radius: 2px; padding: 8px 14px; }
QPushButton:hover { background: #41403b; border-color: #827b6e; }
QPushButton:pressed { background: #4c4942; }
QPushButton:checked, QPushButton#primary { background: #c9b58c; color: #292620; border-color: #c9b58c; font-weight: 600; }
QPushButton:disabled { color: #89857e; background: #302f2c; border-color: #45423c; }
QLineEdit, QComboBox { background: #252524; border: 1px solid #504d47; border-radius: 2px; padding: 8px; selection-background-color: #575145; }
QLineEdit:focus, QComboBox:focus { border-color: #c9b58c; }
QComboBox QAbstractItemView { background: #343330; selection-background-color: #575145; }
QPlainTextEdit { font-family: "Menlo", "Consolas", monospace; font-size: 14px; background: #242423; color: #dedbd5; border: none; selection-background-color: #575145; padding: 8px 0; }
QSplitter::handle { background: #514b40; }
QSplitter::handle:hover { background: #746c5d; }
QStatusBar { color: #aaa59b; background: #2b2b2b; border-top: 1px solid #45433f; }
QStatusBar::item { border: none; }
QScrollBar:vertical { background: #242423; width: 10px; }
QScrollBar::handle:vertical { background: #5c5850; border-radius: 2px; min-height: 24px; }
QScrollBar:horizontal { background: #242423; height: 10px; }
QScrollBar::handle:horizontal { background: #5c5850; border-radius: 2px; min-width: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QToolTip { color: #e5dfd3; background: #37352f; border: 1px solid #71695b; padding: 6px; }
'''


def workspace_style():
    # QSS fallback lists can trigger expensive missing-family alias searches.
    from PySide6.QtWidgets import QApplication
    from .fonts import installed_family, monospace_family
    return (STYLE
        .replace('".AppleSystemUIFont", "Segoe UI", sans-serif',
                 '"' + QApplication.font().family() + '"')
        .replace('"Copperplate", "Palatino Linotype", "Georgia", serif',
                 '"' + installed_family(('Copperplate', 'Palatino Linotype', 'Georgia')) + '"')
        .replace('"Menlo", "Consolas", monospace', '"' + monospace_family() + '"'))
