"""First-launch choices and the entity/port form for a new VHDL design."""
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QStackedWidget, QWidget,
)
from eitri.backend.vhdl import Entity, Port, validate_entity


class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice = None
        self.setWindowTitle('Welcome to Eitri')
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        heading = QLabel('Start a design')
        heading.setObjectName('heading')
        layout.addWidget(heading)
        layout.addWidget(QLabel('Open a VHDL design or create an entity and its ports.'))
        for text, choice in (('Open existing design…', 'open'), ('Create new design…', 'new')):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, value=choice: self.choose(value))
            layout.addWidget(button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose(self, choice):
        self.choice = choice
        self.accept()


class NewDesignDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entity = None
        self.setWindowTitle('Create VHDL design')
        self.resize(630, 390)
        layout = QVBoxLayout(self)
        # The entity field and port table directly describe the generated entity.
        form = QFormLayout()
        self.entity_name = QLineEdit()
        self.entity_name.setPlaceholderText('e.g. adder')
        form.addRow('Entity name', self.entity_name)
        layout.addLayout(form)
        layout.addWidget(QLabel('Ports / properties — vectors use (size − 1 downto 0).'))
        self.ports = QTableWidget(0, 4)
        self.ports.setHorizontalHeaderLabels(['Name', 'Direction', 'Type', 'Vector size'])
        self.ports.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ports.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.ports.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ports.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(self.ports, 1)
        controls = QHBoxLayout()
        add = QPushButton('Add port')
        add.clicked.connect(self.add_port)
        remove = QPushButton('Remove selected')
        remove.clicked.connect(self.remove_port)
        controls.addWidget(add)
        controls.addWidget(remove)
        controls.addStretch()
        layout.addLayout(controls)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #d4a093;')
        layout.addWidget(self.error)
        # Validation leaves the dialog open and preserves everything entered.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Create source…')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_port(self):
        row = self.ports.rowCount()
        self.ports.insertRow(row)
        self.ports.setItem(row, 0, QTableWidgetItem(''))
        direction = QComboBox()
        direction.addItems(['in', 'out'])
        self.ports.setCellWidget(row, 1, direction)
        data_type = QComboBox()
        data_type.addItems(['STD_LOGIC', 'STD_LOGIC_VECTOR'])
        self.ports.setCellWidget(row, 2, data_type)
        size = QSpinBox()
        size.setRange(1, 65536)
        size.setValue(8)
        # Keep the scalar cell empty, retaining the last width when switching types.
        size_cell = QStackedWidget()
        size_cell.addWidget(QWidget())
        size_cell.addWidget(size)
        data_type.currentTextChanged.connect(
            lambda value: size_cell.setCurrentIndex(1 if value == 'STD_LOGIC_VECTOR' else 0))
        self.ports.setCellWidget(row, 3, size_cell)
        self.ports.setCurrentCell(row, 0)
        self.ports.editItem(self.ports.item(row, 0))

    def remove_port(self):
        if self.ports.currentRow() >= 0:
            self.ports.removeRow(self.ports.currentRow())

    def read_entity(self):
        ports = []
        for row in range(self.ports.rowCount()):
            name = self.ports.item(row, 0).text().strip()
            direction = self.ports.cellWidget(row, 1).currentText()
            data_type = self.ports.cellWidget(row, 2).currentText()
            if data_type == 'STD_LOGIC_VECTOR':
                size = self.ports.cellWidget(row, 3).widget(1).value()
                data_type += f'({size - 1} downto 0)'
            ports.append(Port(name, direction, data_type))
        entity = Entity(self.entity_name.text().strip(), ports)
        validate_entity(entity)
        return entity

    def accept(self):
        try:
            self.entity = self.read_entity()
        except ValueError as error:
            self.error.setText(str(error))
            return
        super().accept()
