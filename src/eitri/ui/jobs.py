"""Keep tool processes outside Qt and poll their logs without blocking events."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import QObject, QStandardPaths, QTimer, Signal
from eitri.backend.pipeline import validate


class JobRunner(QObject):
    output = Signal(str)
    finished = Signal(bool, str, object)

    def __init__(self, parent=None, run_root=None):
        super().__init__(parent)
        self.run_root = Path(run_root) if run_root else Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / 'runs'
        self.process = None
        self.directory = None
        self.reader = None
        self.writer = None
        self.cancelled = False
        self.killer = None
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll)

    @property
    def running(self):
        return self.process is not None

    def start(self, request):
        if self.running:
            raise RuntimeError('A job is already running on this page.')
        validate(request)
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=request['kind'] + '-', dir=self.run_root))
        (self.directory / 'request.json').write_text(json.dumps(request), encoding='utf-8')
        self.writer = (self.directory / 'run.log').open('wb')
        self.reader = (self.directory / 'run.log').open(encoding='utf-8', errors='replace')
        # A private process group lets Stop terminate the worker AND tool children.
        options = {'start_new_session': True} if os.name != 'nt' else {
            'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
        try:
            self.process = subprocess.Popen(
                [sys.executable, '-u', '-m', 'eitri.backend.pipeline', str(self.directory)],
                stdout=self.writer, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **options)
        except Exception:
            self.reader.close()
            self.writer.close()
            raise
        self.cancelled = False
        self.started = time.monotonic()
        self.timer.start()

    def stop(self):
        if not self.running or self.cancelled:
            return
        self.cancelled = True
        self.output.emit('\nStopping tool processes…\n')
        self._kill_tree()

    def _kill_tree(self):
        if os.name == 'nt':
            # taskkill may take time; keep it asynchronous just like the tool job.
            self.killer = subprocess.Popen(
                ['taskkill', '/PID', str(self.process.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def poll(self):
        if not self.running:
            return
        # Reading a regular file cannot block waiting for child-process output.
        text = self.reader.read(64 * 1024)
        if text:
            self.output.emit(text)
        if time.monotonic() - self.started > 600 and not self.cancelled:
            self.output.emit('\nJob exceeded the 10 minute safety limit.\n')
            self.stop()
        wave = self.directory / 'wave.vcd'
        if wave.exists() and wave.stat().st_size > 256 * 1024 * 1024 and not self.cancelled:
            self.output.emit('\nWaveform exceeded 256 MB; use a shorter stop time.\n')
            self.stop()
        code = self.process.poll()
        if code is None:
            return
        if self.killer is not None and self.killer.poll() is None:
            return
        self.killer = None
        if os.name != 'nt':
            self._kill_tree()  # Reap descendants left by a timed-out adapter.
        self.output.emit(self.reader.read())
        self.reader.close()
        self.writer.close()
        self.process = None
        self.timer.stop()
        result = {}
        success = code == 0 and not self.cancelled
        if success:
            try:
                result = json.loads((self.directory / 'result.json').read_text())
            except (OSError, ValueError) as error:
                self.output.emit(f'Could not read job results: {error}\n')
                success = False
        message = 'Stopped.' if self.cancelled else ('Completed.' if success else 'Failed — see tool output below.')
        self.finished.emit(success, message, result)
