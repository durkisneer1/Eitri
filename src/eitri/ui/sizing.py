"""Window defaults in logical pixels, bounded by usable screen space."""
from PySide6.QtCore import QSize

PREFERRED_WIDTH = 1140
PREFERRED_HEIGHT = 620


def launch_size(available: QSize) -> QSize:
    """Leave room around the window and for the native title bar.

    Qt's available screen geometry already excludes the menu bar and Dock.
    The additional margin avoids opening an almost-fullscreen window.
    """
    return QSize(
        max(1, min(PREFERRED_WIDTH, available.width() - 80)),
        max(1, min(PREFERRED_HEIGHT, available.height() - 100,
                   int(available.height() * 0.82))),
    )


def fit_window(window):
    screen = window.screen()
    if screen is None:
        window.resize(PREFERRED_WIDTH, PREFERRED_HEIGHT)
        return
    area = screen.availableGeometry()
    size = launch_size(area.size())
    window.setMinimumSize(min(720, size.width()), min(420, size.height()))
    window.resize(size)
    window.move(area.x() + (area.width() - size.width()) // 2,
                area.y() + (area.height() - size.height()) // 2)
