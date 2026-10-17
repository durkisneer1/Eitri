"""Simulation controls, signal selection and the embedded timing diagram."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem
from eitri.backend.vcd import format_value, time_label, value_at
from .job_page import JobPage
from .waveform import WaveformView


class SimulationPage(JobPage):
    def __init__(self, parent=None):
        super().__init__('Run simulation', parent)
        self.data = {'signals': [], 'end_time': 0, 'timescale': '1 fs'}
        self.wave_file = None
        # Viewer actions are distinct from Run: zooming never reruns GHDL.
        tools = QHBoxLayout()
        for title, callback in (('+', lambda: self.wave.zoom_by(2)), ('−', lambda: self.wave.zoom_by(0.5)), ('Fit', lambda: self.wave.fit())):
            item = QPushButton(title)
            item.clicked.connect(callback)
            tools.addWidget(item)
        self.radix = QComboBox()
        self.radix.addItems(['Hex', 'Binary', 'Unsigned'])
        self.radix.currentTextChanged.connect(self.change_radix)
        tools.addWidget(self.radix)
        tools.addStretch()
        self.cursor_label = QLabel('Cursor: 0')
        tools.addWidget(self.cursor_label)
        self.result_layout.addLayout(tools)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter signals by name…')
        self.filter.textChanged.connect(self.filter_signals)
        self.result_layout.addWidget(self.filter)
        # Checkbox selection avoids drawing every internal signal by default.
        split = QSplitter(Qt.Orientation.Horizontal)
        self.signals = QTreeWidget()
        self.signals.setHeaderLabels(['Signal', 'Value at cursor'])
        self.signals.setColumnWidth(0, 165)
        self.signals.setColumnWidth(1, 110)
        self.signals.itemChanged.connect(self.select_signals)
        self.wave = WaveformView()
        self.wave.cursor_changed.connect(self.update_values)
        split.addWidget(self.signals)
        split.addWidget(self.wave)
        split.setSizes([285, 600])
        split.setStretchFactor(1, 1)
        self.result_layout.addWidget(split, 1)
        exports = QHBoxLayout()
        self.save_wave = QPushButton('Export waveform…')
        self.save_wave.setEnabled(False)
        self.save_wave.clicked.connect(self.export_wave)
        self.gtkwave = QPushButton('Open in GTKWave')
        self.gtkwave.setEnabled(False)
        self.gtkwave.clicked.connect(self.open_gtkwave)
        exports.addWidget(self.save_wave)
        exports.addWidget(self.gtkwave)
        exports.addStretch()
        self.result_layout.addLayout(exports)

    def load_result(self, directory, result):
        self.data = json.loads((directory / result['waveform']).read_text())
        self.wave_file = directory / result['wave_file']
        self.signals.blockSignals(True)
        self.signals.clear()
        # Show testbench-level signals first; UUT/internal aliases remain selectable.
        shallowest = min((signal['name'].count('.') for signal in self.data['signals']), default=0)
        checked = 0
        for index, signal in enumerate(self.data['signals']):
            # Omit the common top-level scope in labels; retain it in tooltips.
            display_name = signal['name'].split('.', 1)[-1]
            item = QTreeWidgetItem([display_name, ''])
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            item.setToolTip(0, signal['name'])
            selected = signal['name'].count('.') == shallowest and checked < 16
            checked += int(selected)
            item.setCheckState(0, Qt.CheckState.Checked if selected else Qt.CheckState.Unchecked)
            self.signals.addTopLevelItem(item)
        self.signals.blockSignals(False)
        self.wave.cursor = 0
        self.wave.fit()
        self.select_signals()
        self.filter_signals(self.filter.text())
        self.save_wave.setEnabled(True)
        self.gtkwave.setEnabled(True)
        self.has_result = True
        duration = time_label(self.data['end_time'], self.data['timescale'])
        warning = self.data.get('warning', '')
        self.status.setText(f'Completed · {result["signals"]} signals · {duration}. {warning}')

    def select_signals(self, *_):
        selected = [self.data['signals'][index] for index in range(self.signals.topLevelItemCount())
                    if self.signals.topLevelItem(index).checkState(0) == Qt.CheckState.Checked]
        self.wave.set_data(selected, self.data['end_time'], self.data['timescale'])

    def filter_signals(self, text):
        for index in range(self.signals.topLevelItemCount()):
            item = self.signals.topLevelItem(index)
            item.setHidden(text.lower() not in self.data['signals'][index]['name'].lower())

    def change_radix(self, radix):
        self.wave.radix = radix
        self.wave.viewport().update()
        self.update_values(self.wave.cursor)

    def update_values(self, ticks):
        self.cursor_label.setText('Cursor: ' + time_label(ticks, self.data['timescale']))
        self.signals.blockSignals(True)
        for index, signal in enumerate(self.data['signals']):
            self.signals.topLevelItem(index).setText(1, format_value(value_at(signal, ticks), signal['width'], self.radix.currentText()))
        self.signals.blockSignals(False)

    def export_wave(self):
        if self.wave_file:
            self.export_file(self.wave_file, 'Export waveform', 'Waveform files (*.vcd *.ghw)')

    def open_gtkwave(self):
        import gtkwave
        if self.wave_file:
            try:
                gtkwave.launch(self.wave_file)
            except (OSError, RuntimeError) as error:
                QMessageBox.warning(self, 'GTKWave unavailable', str(error))
