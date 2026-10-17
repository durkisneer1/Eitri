"""Wordmark and centered, icon-only workspace navigation."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QButtonGroup, QFrame, QVBoxLayout, QHBoxLayout, QPushButton
from .widgets import label

# Small vector drawings avoid platform-dependent icon fonts and bundled assets.
PATHS = (
    '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
    '<path d="M2 16h4V6h6v12h6V8h4"/>',
    '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4"/>',
)


def mode_icon(index):
    icon = QIcon()
    for state, color in ((QIcon.State.Off, '#dedbd5'), (QIcon.State.On, '#292620')):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[index]}</g></svg>'
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(svg.encode()).render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(2)
        icon.addPixmap(pixmap, QIcon.Mode.Normal, state)
    return icon


class Toolbar(QFrame):
    mode_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('toolbar')
        row = QVBoxLayout(self)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(12)
        brand = label('EITRI', 'brand')
        row.addWidget(brand, 0, Qt.AlignmentFlag.AlignHCenter)
        nav = QHBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.setSpacing(6)
        nav.addStretch()
        self.mode_buttons = QButtonGroup(self)
        self.mode_buttons.setExclusive(True)
        for index, title in enumerate(('Code', 'Simulation', 'Circuit')):
            item = QPushButton()
            item.setIcon(mode_icon(index))
            item.setIconSize(QSize(24, 24))
            item.setToolTip(title)
            item.setAccessibleName(title)
            item.setCheckable(True)
            item.setFixedSize(54, 40)
            self.mode_buttons.addButton(item, index)
            nav.addWidget(item)
        nav.addStretch()
        row.addLayout(nav)
        self.mode_buttons.idClicked.connect(self.mode_changed.emit)
        self.mode_buttons.button(0).setChecked(True)
