"""Common run controls, status and diagnostics for the two tool pages."""
from pathlib import Path
import shutil
import zipfile

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSplitter, QVBoxLayout, QWidget


class JobPage(QWidget):
    run_requested = Signal()
    stop_requested = Signal()

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.result_dir = None
        self.busy = False
        self.has_result = False
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 10)
        # The command row remains available while either results or logs scroll.
        controls = QHBoxLayout()
        self.run_button = QPushButton(action)
        self.run_button.setObjectName('primary')
        self.run_button.clicked.connect(lambda: self.run_requested.emit())
        self.stop_button = QPushButton('Stop')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit())
        self.export_button = QPushButton('Export run…')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_run)
        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()
        controls.addWidget(self.export_button)
        self.layout.addLayout(controls)
        self.status = QLabel('Ready. Runs use the current editor contents, including unsaved changes.')
        self.status.setWordWrap(True)
        self.layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.layout.addWidget(self.progress)
        # A vertical splitter lets users enlarge diagnostics when a tool fails.
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.layout.addWidget(self.splitter, 1)
        self.results = QWidget()
        self.result_layout = QVBoxLayout(self.results)
        self.result_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.results)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('Compiler, simulator, and synthesis diagnostics appear here.')
        self.log.document().setMaximumBlockCount(3000)
        self.splitter.addWidget(self.log)
        self.splitter.setSizes([350, 110])

    def append_log(self, text):
        from PySide6.QtGui import QTextCursor
        if self.busy:
            stages = [line.strip('= ').strip() for line in text.splitlines() if line.startswith('=== ')]
            if stages:
                self.status.setText(stages[-1] + '…')
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def set_busy(self, busy):
        self.busy = busy
        self.run_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)
        self.progress.setVisible(busy)
        self.export_button.setEnabled(not busy and self.result_dir is not None)
        if busy:
            self.log.clear()
            self.status.setText('Running editor snapshot… Previous results remain visible until the run succeeds.')

    def mark_stale(self):
        if self.has_result and not self.busy:
            self.status.setText('Inputs changed — displayed results are from an earlier run. Run again to update.')

    def export_run(self):
        if self.result_dir is None:
            return
        filename, _ = QFileDialog.getSaveFileName(self, 'Export run and source snapshot', 'eitri-run.zip', 'ZIP archive (*.zip)')
        if not filename:
            return
        try:
            target = Path(filename).resolve()
            if target.is_relative_to(self.result_dir.resolve()):
                raise ValueError('Choose a destination outside the run directory.')
            with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
                for path in self.result_dir.iterdir():
                    if path.is_file():
                        archive.write(path, path.name)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, 'Export failed', str(error))

    def export_file(self, source, title, file_filter):
        filename, _ = QFileDialog.getSaveFileName(self, title, source.name, file_filter)
        if filename:
            try:
                if Path(filename).resolve() != source.resolve():
                    shutil.copy2(source, filename)
            except OSError as error:
                QMessageBox.critical(self, 'Export failed', str(error))
