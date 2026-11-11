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
QLabel#error { color: #d4a093; }
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
    style = themed_text(STYLE)
    if current_mode() == 'Light':
        style += '\nQLabel#brand, QLabel#eyebrow { color: #80602c; }'
    return (style
        .replace('".AppleSystemUIFont", "Segoe UI", sans-serif',
                 '"' + QApplication.font().family() + '"')
        .replace('"Copperplate", "Palatino Linotype", "Georgia", serif',
                 '"' + installed_family(('Copperplate', 'Palatino Linotype', 'Georgia')) + '"')
        .replace('"Menlo", "Consolas", monospace', '"' + monospace_family() + '"'))


# One palette translation is shared by Qt styles, custom painters and SVGs.
# Keys are the original charcoal palette, preserving existing run artifacts.
LIGHT_COLORS = {
    '#242423': '#faf9f6', '#242424': '#f5f3ee', '#202020': '#eeece6',
    '#2b2b2b': '#eeece6', '#302f2c': '#e9e6de', '#343330': '#e5e1d7',
    '#3b3935': '#e4dfd3', '#41403b': '#ddd6c7', '#4c4942': '#d3c9b6',
    '#252524': '#fffefa', '#37352f': '#fff9e9', '#30302d': '#ede9df',
    '#dedbd5': '#302e29', '#e5dfd3': '#292620', '#eee7da': '#282e31',
    '#aaa59b': '#645f54', '#a6a29a': '#645f54', '#89857e': '#787267',
    '#45433f': '#c9c3b7', '#45423c': '#ccc5b8', '#504d47': '#b9b0a0',
    '#827b6e': '#84745b', '#716044': '#d9c9a7', '#c9b58c': '#d6bd88',
    '#292620': '#292620', '#575145': '#d6c8aa', '#514b40': '#c4baa8',
    '#746c5d': '#9d907a', '#5c5850': '#b6ad9d', '#71695b': '#a69578',
    '#bba7c4': '#774789', '#a9b9a1': '#3d6841', '#c9bc91': '#806015',
    '#c39e83': '#995021', '#928c81': '#746e62', '#c9bb9f': '#6d5429',
    '#817c73': '#797367', '#e58c7c': '#b43829', '#d1b578': '#8a6213',
    '#9c9588': '#706757', '#3c3933': '#ddd8cd', '#c8877c': '#aa3e32',
    '#a49aac': '#78568b', '#b9c4a1': '#41652c', '#d4a093': '#a64735',
    '#3c4a50': '#e2eaf0', '#623f38': '#f3d5cd', '#a4b2b7': '#506873',
    '#c4b48e': '#735c2e', '#bfa779': '#80602c', '#91ad98': '#356444',
    '#bec9cd': '#52616a', '#35453b': '#e3eee2',
}


def current_mode():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    return (app.property('eitri_theme') if app else None) or 'Dark'


def theme_color(dark_color):
    return LIGHT_COLORS.get(dark_color, dark_color) if current_mode() == 'Light' else dark_color


def themed_text(text):
    import re
    return re.sub(r'#[0-9a-fA-F]{6}', lambda m: theme_color(m[0].lower()), text)


def apply_theme(mode):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QPalette
    app = QApplication.instance()
    app.setProperty('eitri_theme', mode if mode in ('Dark', 'Light') else 'Dark')
    palette = QPalette()
    for role, color in {
        'Window': '#242424', 'WindowText': '#dedbd5', 'Base': '#242423',
        'AlternateBase': '#2b2b2b', 'Text': '#dedbd5', 'Button': '#343330',
        'ButtonText': '#dedbd5', 'Highlight': '#575145', 'HighlightedText': '#e5dfd3',
        'ToolTipBase': '#37352f', 'ToolTipText': '#e5dfd3', 'PlaceholderText': '#aaa59b',
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(theme_color(color)))
    app.setPalette(palette)
    app.setStyleSheet(workspace_style())
