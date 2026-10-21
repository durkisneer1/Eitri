"""Named project targets, immutable run snapshots and sequential test suites."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import re
from PySide6.QtCore import QObject, Qt, QTimer, QEvent
from PySide6.QtWidgets import QMessageBox, QTreeWidgetItem
from .jobs import JobRunner


class ToolController(QObject):
    def __init__(self, window, run_root=None):
        super().__init__(window)
        self.window = window
        self.close_when_idle = False
        self.requests = {}
        self.pages = {'simulation': window.simulation_page, 'circuit': window.circuit_page}
        self.runners = {}
        self.queue = []
        window.circuit_page.expand_requested.connect(self.expand_component)
        window.circuit_page.collapse_requested.connect(lambda: self.expand_component(None))
        self.batch_item = None
        self.results = []
        for kind, page in self.pages.items():
            runner = JobRunner(self, run_root)
            self.runners[kind] = runner
            page.run_requested.connect(lambda k=kind: self.start(k))
            page.stop_requested.connect(lambda k=kind: self.stop(k))
            runner.output.connect(page.append_log)
            runner.finished.connect(lambda ok, message, result, k=kind: self.finished(k, ok, message, result))
            page.log.viewport().installEventFilter(self)
            page.log.setToolTip('Double-click a compiler error or assertion location to open its source.')
        window.simulation_page.signals.itemChanged.connect(self.remember_signals)
        self.wave_timer = QTimer(self)
        self.wave_timer.setSingleShot(True)
        self.wave_timer.setInterval(500)
        self.wave_timer.timeout.connect(self.save_signals)

    def snapshot(self, kind, target=None):
        window = self.window
        if not window.project:
            raise ValueError('Open a folder before running a target.')
        window.project.refresh(window.documents.overlays())
        target = target or window.selected_target(kind)
        request = window.project.snapshot(target)
        request['cache_root'] = str(self.runners[kind].run_root.parent / 'analysis-cache')
        return request

    def start(self, kind, target=None, request=None):
        page = self.pages[kind]
        self.window.switch_mode(1 if kind == 'simulation' else 2)
        try:
            if self.runners[kind].running:
                raise ValueError('This page already has a running target. Stop it before starting another.')
            request = request or self.snapshot(kind, target)
            self.runners[kind].start(request)
        except (ValueError, RuntimeError, OSError) as error:
            page.status.setText(str(error))
            page.append_log(str(error) + '\n')
            return False
        self.requests[kind] = request
        page.set_busy(True)
        page.append_log(f'Target: {request["target"]["name"]}\nUsing {len(request["sources"])} source buffers, including unsaved edits.\n')
        from eitri.backend.project import Target
        self.window.persist_target(Target(**request['target']))
        return True

    def finished(self, kind, success, message, result):
        page = self.pages[kind]
        directory = self.runners[kind].directory
        page.result_dir = directory
        page.set_busy(False)
        page.status.setText(message + (' Previous results remain visible.' if page.has_result and not success else ''))
        request = self.requests[kind]
        entry = {'success': success, 'directory': str(directory), 'request': request, 'result': result, 'message': message}
        self.results.append(entry)
        if kind == 'simulation':
            item = self.batch_item or QTreeWidgetItem(self.window.sidebar.tests, [request['target']['name'], ''])
            item.setText(1, 'Stopped' if self.runners[kind].cancelled else ('Passed' if success else 'Failed'))
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            self.batch_item = None
        if success:
            self.load_result(entry)
        self.mark_stale()
        if kind == 'simulation' and self.queue:
            QTimer.singleShot(0, self.next_test)
        if self.close_when_idle and not self.running:
            self.close_when_idle = False
            self.window.close()

    def load_result(self, entry):
        request, result = entry['request'], entry['result']
        if request['kind'] == 'circuit':
            self.displayed_circuit = entry
        page = self.pages[request['kind']]
        try:
            page.load_result(Path(entry['directory']), result)
            page.status.setText(request['target']['name'] + ' · ' + page.status.text())
            if request['kind'] == 'simulation':
                names = request['target'].get('signals')
                if names is not None:
                    page.signals.blockSignals(True)
                    for index, signal in enumerate(page.data['signals']):
                        page.signals.topLevelItem(index).setCheckState(0, Qt.CheckState.Checked if signal['name'] in names else Qt.CheckState.Unchecked)
                    page.signals.blockSignals(False)
                    page.select_signals()
                self.displayed_simulation = entry
        except (OSError, ValueError, KeyError) as error:
            page.status.setText(f'Run completed, but preview failed: {error}')

    def expand_component(self, name):
        entry = getattr(self, 'displayed_circuit', None)
        if not entry or self.runners['circuit'].running:
            return
        request = dict(entry['request'])
        request['circuit_detail'] = 'Simple'
        request['expand_instances'] = list(dict.fromkeys([*request.get('expand_instances', []), name])) if name else []
        # Expand exactly the displayed immutable source snapshot.
        self.start('circuit', request=request)

    def run_all(self):
        if self.running or self.queue:
            self.window.statusBar().showMessage('Stop the current run before starting a test suite.', 6000)
            return
        if not self.window.project:
            self.window.statusBar().showMessage('Open a project folder first.', 6000)
            return
        self.window.refresh_project()
        self.window.sidebar.tests.clear()
        self.window.sidebar.explorer_tabs.setCurrentWidget(self.window.sidebar.tests)
        # Snapshot all tests now: later edits do not change a suite in progress.
        for target in self.window.project.targets('simulation'):
            item = QTreeWidgetItem(self.window.sidebar.tests, [target.name, 'Queued'])
            try:
                request = self.snapshot('simulation', target)
            except (ValueError, OSError) as error:
                item.setText(1, 'Cannot build')
                item.setToolTip(0, str(error))
                continue
            self.queue.append((item, request))
        if not self.queue:
            self.window.statusBar().showMessage('No buildable tests found. Testbench entities normally have no ports.', 7000)
        self.next_test()

    def next_test(self):
        if not self.queue:
            return
        item, request = self.queue.pop(0)
        item.setText(1, 'Running')
        self.batch_item = item
        if not self.start('simulation', request=request):
            item.setText(1, 'Failed to start')
            self.batch_item = None
            QTimer.singleShot(0, self.next_test)

    def stop(self, kind):
        if kind == 'simulation':
            for item, _ in self.queue:
                item.setText(1, 'Cancelled')
            self.queue.clear()
        self.runners[kind].stop()

    def stop_all(self):
        for kind in self.runners:
            self.stop(kind)

    def open_result(self, entry):
        if not entry or self.running:
            return
        request = entry['request']
        page = self.pages[request['kind']]
        self.window.switch_mode(1 if request['kind'] == 'simulation' else 2)
        page.result_dir = Path(entry['directory'])
        page.log.setPlainText((page.result_dir / 'run.log').read_text(encoding='utf-8', errors='replace'))
        page.export_button.setEnabled(True)
        if entry['success']:
            self.load_result(entry)
        else:
            page.status.setText(entry['request']['target']['name'] + ' · ' + entry['message'])

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            for page in self.pages.values():
                if watched is page.log.viewport():
                    text = page.log.cursorForPosition(event.position().toPoint()).block().text()
                    match = re.search(r'(.+?\.vhdl?):(\d+)(?::\d+)?', text, re.I)
                    if match:
                        path = Path(match[1].strip())
                        if path.is_file():
                            self.window.documents.load(path, int(match[2]) - 1)
                            return True
        return super().eventFilter(watched, event)

    def remember_signals(self, *_):
        if hasattr(self, 'displayed_simulation'):
            self.wave_timer.start()

    def save_signals(self):
        entry = getattr(self, 'displayed_simulation', None)
        if not entry or not self.window.project:
            return
        if entry['request']['project_root'] != str(self.window.project.root):
            return
        page = self.window.simulation_page
        names = [s['name'] for i, s in enumerate(page.data['signals']) if page.signals.topLevelItem(i).checkState(0) == Qt.CheckState.Checked]
        from eitri.backend.project import Target
        target = Target(**{**entry['request']['target'], 'signals': names})
        self.window.persist_target(target)

    @property
    def running(self):
        return any(r.running for r in self.runners.values())

    def mark_stale(self, *_):
        project = self.window.project
        if project:
            current = {**project.sources, **self.window.documents.overlays()}
            for kind, request in self.requests.items():
                if request['standard'] != self.window.sidebar.standard.currentText() or any(current.get(s['path']) != s['source'] for s in request['sources']):
                    self.pages[kind].mark_stale()

    def prepare_close(self):
        if not self.running:
            self.stop_all()
            return True
        if self.close_when_idle:
            return False
        if QMessageBox.question(self.window, 'Tools are running', 'Stop running tools and close Eitri?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.close_when_idle = True
            self.stop_all()
        return False
