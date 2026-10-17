"""Resolve installed font families before handing them to Qt."""
from PySide6.QtGui import QFontDatabase


def installed_family(preferred, fixed=False):
    available = {name.casefold(): name for name in QFontDatabase.families()}
    for name in preferred:
        if name.casefold() in available:
            return available[name.casefold()]
    kind = QFontDatabase.SystemFont.FixedFont if fixed else QFontDatabase.SystemFont.GeneralFont
    return QFontDatabase.systemFont(kind).family()


def monospace_family():
    return installed_family(('Menlo', 'Consolas', 'DejaVu Sans Mono', 'Liberation Mono'), fixed=True)


def configure_application_font(app):
    # Some platform plugins return a generic alias rather than an installed font.
    font = app.font()
    font.setFamily(installed_family((font.family(), 'Segoe UI', 'Helvetica Neue', 'DejaVu Sans', 'Arial')))
    app.setFont(font)
