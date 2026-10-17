"""Small shared widget constructors; visual styles live in theme.py."""
from PySide6.QtWidgets import QLabel, QPushButton


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if name:
        widget.setObjectName(name)
    return widget


def field(layout, title, widget):
    layout.addWidget(label(title, 'muted'))
    layout.addWidget(widget)
    layout.addSpacing(8)
    return widget


