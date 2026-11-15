"""Small vector controls that follow the active workspace palette."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from .theme import theme_color

PATHS = {
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    'moon': '<path d="M20 14A8.5 8.5 0 0 1 10 3a8.5 8.5 0 1 0 10 11Z"/>',
    'dock_right': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16M6 12h6m-2-2 2 2-2 2"/>',
    'dock_bottom': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 15h18M12 6v6m-2-2 2 2 2-2"/>',
    'close': '<path d="m6 6 12 12M6 18 18 6"/>',
}


def control_icon(name):
    color = theme_color('#dedbd5')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    with QPainter(pixmap) as painter:
        QSvgRenderer(svg.encode()).render(painter)
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
