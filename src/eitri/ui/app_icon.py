"""The approved Ehwaz artwork, shared by the wordmark and native app icon."""
from importlib.resources import files
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def application_icon():
    # Include raster sizes for native Dock/taskbar integrations that do not
    # request SVG rendering themselves. Keep the SVG as the source artwork.
    artwork = files('eitri').joinpath('assets/eitri.svg').read_bytes()
    renderer = QSvgRenderer(artwork)
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256, 512, 1024):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
