"""Translate editor/settings snapshots into jobs and deliver results to pages."""
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox
from .jobs import JobRunner
from eitri.backend.dependencies import snapshot_dependencies


class ToolController(QObject):
    def __init__(self, window, run_root=None):
        super().__init__(window)
        self.window = window
        self.close_when_idle = False
        self.requests = {}
        self.pages = {'simulation': window.simulation_page, 'circuit': window.circuit_page}
        self.runners = {}
        for kind, page in self.pages.items():
            runner = JobRunner(self, run_root)
            self.runners[kind] = runner
            # Capture the loop variable explicitly; each page has its own job.
            page.run_requested.connect(lambda name=kind: self.start(name))
            page.stop_requested.connect(runner.stop)
            runner.output.connect(page.append_log)
            runner.finished.connect(lambda ok, message, result, name=kind: self.finished(name, ok, message, result))

        # Editing does not modify a running job's sources. It only marks its
        # result out of date, making comparisons against later edits unambiguous.
        for editor in window.code_page.editors:
            editor.textChanged.connect(self.mark_stale)
        for control in (window.sidebar.entity, window.sidebar.testbench, window.sidebar.stop_time):
            control.textChanged.connect(self.mark_stale)
        window.sidebar.standard.currentTextChanged.connect(self.mark_stale)
        window.sidebar.wave_format.currentTextChanged.connect(self.mark_stale)
        window.sidebar.circuit_detail.currentTextChanged.connect(self.mark_stale)

    def snapshot(self, kind):
        sidebar = self.window.sidebar
        roots = [(self.window.paths[0], self.window.code_page.editors[0].toPlainText())]
        if kind == 'simulation':
            roots.append((self.window.paths[1], self.window.code_page.editors[1].toPlainText()))
        dependencies = snapshot_dependencies(roots)
        return {'dependencies': dependencies, 'kind': kind,
                'circuit_detail': sidebar.circuit_detail.currentText() if kind == 'circuit' else 'Detailed', 'standard': sidebar.standard.currentText(),
                'entity': sidebar.entity.text().strip(),
                'testbench': sidebar.testbench.text().strip() if kind == 'simulation' else '',
                'stop_time': sidebar.stop_time.text().strip().replace(' ', '') if kind == 'simulation' else '',
                'wave_format': sidebar.wave_format.currentText() if kind == 'simulation' else '',
                'design': self.window.code_page.editors[0].toPlainText(),
                'bench': self.window.code_page.editors[1].toPlainText() if kind == 'simulation' else ''}

    def start(self, kind):
        page = self.pages[kind]
        self.window.switch_mode(1 if kind == 'simulation' else 2)
        try:
            request = self.snapshot(kind)
            self.runners[kind].start(request)
        except (ValueError, RuntimeError, OSError) as error:
            page.status.setText(str(error))
            return
        self.requests[kind] = request
        page.set_busy(True)
        page.append_log('Source snapshot: design.vhd = Design tab; testbench.vhd = Testbench tab.\n')

    def finished(self, kind, success, message, result):
        page = self.pages[kind]
        page.result_dir = self.runners[kind].directory
        page.set_busy(False)
        page.status.setText(message + (' Previous results remain visible.' if page.has_result and not success else ''))
        if success:
            try:
                page.load_result(page.result_dir, result)
                if self.snapshot(kind) != self.requests[kind]:
                    page.mark_stale()
            except (OSError, ValueError, KeyError) as error:
                page.status.setText(f'Tool run completed, but its preview failed: {error}')
                page.append_log(f'Preview error: {error}\nExport run still contains the tool artifacts.\n')
        if self.close_when_idle and not self.running:
            self.close_when_idle = False
            self.window.close()

    @property
    def running(self):
        return any(runner.running for runner in self.runners.values())

    def mark_stale(self, *_):
        for kind, page in self.pages.items():
            if kind in self.requests:
                try:
                    stale = self.snapshot(kind) != self.requests[kind]
                except (ValueError, OSError):
                    stale = True
                if stale:
                    page.mark_stale()

    def prepare_close(self):
        """Let Qt finish cancellation before destroying objects and their timers."""
        if not self.running:
            return True
        if self.close_when_idle:
            return False
        answer = QMessageBox.question(self.window, 'Tools are running', 'Stop the running tools and close Eitri?',
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.close_when_idle = True
            for runner in self.runners.values():
                runner.stop()
        return False
