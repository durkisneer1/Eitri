"""Optional second creation step: reuse VHDL entities as components."""
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QListWidget, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)
from eitri.backend.vhdl import Entity, entity_names, parse_entity


@dataclass
class ComponentSource:
    path: Path
    source: str
    entity: Entity
    count: int = 1


class ComponentsDialog(QDialog):
    def __init__(self, entity, parent=None):
        super().__init__(parent)
        self.top_entity = entity
        self.components = []
        self.setWindowTitle('New design — Components')
        self.resize(630, 390)
        layout = QVBoxLayout(self)
        help_text = QLabel('Optionally add existing VHDL entities and choose an instance count.\n'
                           'Declarations and instance templates will be generated. Replace port placeholders in the editor.\n'
                           'Source files stay separate. Eitri tracks references and compiles dependencies.')
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.sources = QListWidget()
        layout.addWidget(self.sources, 1)
        controls = QHBoxLayout()
        add = QPushButton('Add component…')
        add.clicked.connect(self.add_component)
        remove = QPushButton('Remove selected')
        remove.clicked.connect(self.remove_component)
        controls.addWidget(add)
        controls.addWidget(remove)
        controls.addStretch()
        controls.addWidget(QLabel('Instances'))
        self.count = QSpinBox()
        self.count.setRange(1, 256)
        self.count.setEnabled(False)
        self.count.valueChanged.connect(self.change_count)
        controls.addWidget(self.count)
        layout.addLayout(controls)
        self.sources.currentRowChanged.connect(self.select_component)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Create…')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Back')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_component(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Import component source', '', 'VHDL files (*.vhd *.vhdl)')
        if not filename:
            return
        try:
            path = Path(filename)
            source = path.read_text(encoding='utf-8')
            names = entity_names(source)
            selected = names[0] if names else None
            if len(names) > 1:
                selected, accepted = QInputDialog.getItem(self, 'Choose component', 'Entity', names, 0, False)
                if not accepted:
                    return
            entity = parse_entity(source, selected)
            # Copy each source only once and reject conflicting design units.
            used = {self.top_entity.name.lower()}
            for component in self.components:
                used.update(name.lower() for name in entity_names(component.source))
            conflicts = used.intersection(name.lower() for name in names)
            if conflicts:
                raise ValueError('Entity already included: ' + ', '.join(sorted(conflicts)))
            self.components.append(ComponentSource(path, source, entity))
            self.sources.addItem(f'{entity.name} — {path.name}')
            self.sources.setCurrentRow(len(self.components) - 1)
        except (ValueError, OSError, UnicodeError) as error:
            QMessageBox.warning(self, 'Cannot add component', str(error))

    def select_component(self, row):
        self.count.setEnabled(row >= 0)
        self.count.blockSignals(True)
        self.count.setValue(self.components[row].count if row >= 0 else 1)
        self.count.blockSignals(False)

    def change_count(self, count):
        row = self.sources.currentRow()
        if row >= 0:
            self.components[row].count = count

    def remove_component(self):
        row = self.sources.currentRow()
        if row >= 0:
            self.sources.blockSignals(True)
            self.components.pop(row)
            self.sources.takeItem(row)
            self.sources.blockSignals(False)
            self.select_component(self.sources.currentRow())
