"""Persistent, dockable diagnostics that never resize themselves to their contents."""
import random
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
                              QStackedWidget, QPushButton, QSplitter, QSizePolicy)
from .icons import control_icon

FORGE_MESSAGES = (
    'Well wrought, master of the forge.',
    'Brokkr would nod at such craftsmanship.',
    'A fine day at the anvil. Onward, smith.',
    'Keep Loki away from the bellows.',
    'Another worthy design from the halls of the dwarves.',
    'Your craft grows wiser with every pass.',
    'Even Sindri might pause to admire your work.',
    'Mjölnir began with a spark, too.',
)


def icon_button(parent, name, tooltip):
    button = QPushButton(parent)
    button.setObjectName('iconButton')
    button.setFixedSize(32, 32)
    button.setIconSize(QSize(20, 20))
    button.setIcon(control_icon(name))
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    return button


class AssistancePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('assistancePanel')
        self.setMinimumSize(220, 110)
        self._had_diagnostics = False
        self.forge_message = FORGE_MESSAGES[0]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(4)
        header = QHBoxLayout()
        self.heading = QLabel('Problems')
        header.addWidget(self.heading)
        header.addStretch()
        self.dock_button = icon_button(self, 'dock_right', 'Move assistance to the right')
        self.hide_button = icon_button(self, 'close', 'Hide assistance panel')
        header.addWidget(self.dock_button)
        header.addWidget(self.hide_button)
        layout.addLayout(header)
        self.pages = QStackedWidget()
        self.problems = QListWidget()
        self.problems.setWordWrap(True)
        self.problems.setMinimumSize(0, 0)
        self.problems.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.pages.addWidget(self.problems)
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(12, 4, 12, 4)
        empty_layout.addStretch()
        self.empty_title = QLabel('The forge is ready')
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setWordWrap(True)
        self.empty_message = QLabel('Open a VHDL file to begin.')
        self.empty_message.setObjectName('muted')
        self.empty_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_message.setWordWrap(True)
        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_message)
        empty_layout.addStretch()
        self.pages.addWidget(empty)
        self.pages.setCurrentIndex(1)
        layout.addWidget(self.pages, 1)

    def update_state(self, *, enabled=True, available=True, checking=False, checked=False):
        count = self.problems.count()
        self.heading.setText(f'Problems · {count}' if count else 'Problems')
        self.pages.setCurrentIndex(0 if count else 1)
        if count:
            self._had_diagnostics = True
            return
        if not enabled:
            title, message = 'Assistance is off', 'Enable VHDL assistance below to check your work.'
        elif not available:
            title, message = 'The forge needs attention', 'VHDL assistance is unavailable. Toggle assistance below to retry.'
        elif checking:
            title, message = 'Checking your changes…', 'The forge is still at work.'
        elif checked:
            if self._had_diagnostics:
                self.forge_message = random.choice([m for m in FORGE_MESSAGES if m != self.forge_message])
                self._had_diagnostics = False
            title, message = 'No diagnostics', self.forge_message
        else:
            title, message = 'The forge is ready', 'Open or edit a VHDL file to begin.'
        self.empty_title.setText(title)
        self.empty_message.setText(message)

    def reset_feedback(self):
        self._had_diagnostics = False

    def refresh_theme(self, dock):
        target = 'bottom' if dock == 'right' else 'right'
        self.dock_button.setIcon(control_icon('dock_' + target))
        self.dock_button.setToolTip('Move assistance to the ' + target)
        self.dock_button.setAccessibleName(self.dock_button.toolTip())
        self.hide_button.setIcon(control_icon('close'))


class AssistanceSplit(QSplitter):
    panel_visibility_changed = Signal(bool)

    def __init__(self, editor, panel, settings=None, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.settings = settings
        self.dock = self._value('dock', 'bottom')
        if self.dock not in ('bottom', 'right'):
            self.dock = 'bottom'
        self.panel_sizes = {side: max(110 if side == 'bottom' else 220, self._value(side + 'Size', default, int))
                            for side, default in (('bottom', 180), ('right', 360))}
        self.setOrientation(Qt.Orientation.Horizontal if self.dock == 'right' else Qt.Orientation.Vertical)
        self.panel = panel
        self.addWidget(editor)
        self.addWidget(panel)
        self.setChildrenCollapsible(False)
        self.setStretchFactor(0, 1)
        self.setStretchFactor(1, 0)
        self.setHandleWidth(5)
        panel.setVisible(self._value('visible', True, bool))
        panel.refresh_theme(self.dock)
        panel.dock_button.clicked.connect(self.toggle_dock)
        panel.hide_button.clicked.connect(lambda: self.set_panel_visible(False))
        self.splitterMoved.connect(self.remember_size)

    def _value(self, key, default, value_type=None):
        if self.settings is None:
            return default
        try:
            return self.settings.value('assistance/' + key, default, type=value_type or str)
        except (ValueError, TypeError):
            return default

    def _save(self, key, value):
        if self.settings is not None:
            self.settings.setValue('assistance/' + key, value)

    def remember_size(self, *_):
        if not self.panel.isHidden():
            self.panel_sizes[self.dock] = self.sizes()[1]
            self._save(self.dock + 'Size', self.sizes()[1])

    def restore_size(self):
        if self.panel.isHidden():
            return
        available = (self.width() if self.dock == 'right' else self.height()) - self.handleWidth()
        target = min(self.panel_sizes[self.dock], max(110, available - 120))
        self.setSizes([max(120, available - target), target])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.restore_size()

    def set_panel_visible(self, visible):
        self.panel.setVisible(visible)
        self._save('visible', visible)
        self.restore_size()
        self.panel_visibility_changed.emit(visible)

    def toggle_dock(self):
        self.dock = 'bottom' if self.dock == 'right' else 'right'
        self.setOrientation(Qt.Orientation.Horizontal if self.dock == 'right' else Qt.Orientation.Vertical)
        self._save('dock', self.dock)
        self.panel.refresh_theme(self.dock)
        self.restore_size()
