"""Named run settings without asking learners to write a build configuration."""
from dataclasses import replace
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTableWidget, QTableWidgetItem, QDialogButtonBox, QLabel, QPushButton
from eitri.backend.pipeline import IDENTIFIER


class TargetDialog(QDialog):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target
        self.setWindowTitle('Save run target')
        self.resize(460, 360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(target.name)
        form.addRow('Name', self.name)
        form.addRow('Top-level design', QLabel(f'{target.library}.{target.entity} ({target.architecture})'))
        layout.addLayout(form)
        layout.addWidget(QLabel('Generic overrides — leave empty to use VHDL defaults.'))
        self.generics = QTableWidget(0, 2)
        self.generics.setHorizontalHeaderLabels(['Generic name', 'Value'])
        self.generics.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.generics)
        for key, value in target.generics.items():
            self.add_row(key, str(value))
        b = QPushButton('Add generic')
        b.clicked.connect(lambda: self.add_row())
        layout.addWidget(b)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_row(self, name='', value=''):
        row = self.generics.rowCount()
        self.generics.insertRow(row)
        self.generics.setItem(row, 0, QTableWidgetItem(name))
        self.generics.setItem(row, 1, QTableWidgetItem(value))

    def accept(self):
        generics = {}
        for row in range(self.generics.rowCount()):
            key, value = (self.generics.item(row, c).text().strip() for c in (0, 1))
            if not key and not value:
                continue
            if not IDENTIFIER.fullmatch(key) or not value or key.lower() in {k.lower() for k in generics}:
                self.error.setText('Each override needs a unique VHDL name and a value.')
                return
            generics[key] = value
        if not self.name.text().strip():
            self.error.setText('Give this target a name.')
            return
        self.target = replace(self.target, name=self.name.text().strip(), generics=generics)
        super().accept()
