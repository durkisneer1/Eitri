"""GHDL LSP connection and editor integration, isolated from Qt's process.

GHDL LS uses Latin-1 byte columns (one byte per Python character after
replacement), rather than UTF-16 columns. Convert only at the editor boundary.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, QTimer, QUrl, Signal, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QListWidgetItem, QToolTip
from eitri.backend.dependencies import snapshot_dependencies
from eitri.backend.pipeline import STANDARDS


def frame(message):
    data = json.dumps(message, ensure_ascii=False).encode('utf-8')
    return f'Content-Length: {len(data)}\r\n\r\n'.encode() + data


class MessageReader:
    def __init__(self):
        self.buffer = b''

    def feed(self, data):
        self.buffer += data
        messages = []
        while b'\r\n\r\n' in self.buffer:
            header, body = self.buffer.split(b'\r\n\r\n', 1)
            headers = dict(line.split(b':', 1) for line in header.split(b'\r\n'))
            length = int(next(value for key, value in headers.items() if key.lower() == b'content-length'))
            if not 0 <= length <= 16 * 1024 * 1024:
                raise ValueError('Invalid LSP message size')
            if len(body) < length:
                break
            messages.append(json.loads(body[:length]))
            self.buffer = body[length:]
        return messages


class LanguageServer(QObject):
    ready = Signal()
    notification = Signal(str, object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_errors)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.process.started.connect(self.initialize)
        self.reader = MessageReader()
        self.pending = {}
        self.serial = 0
        self.running = False
        self.stopping = False
        self.stderr = ''
        self.root = None
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(lambda: self.failed.emit('Language server initialization timed out.'))

    def process_error(self, _):
        if not self.stopping:
            self.failed.emit(self.process.errorString())

    def start(self, root):
        self.root = Path(root)
        self.stopping = False
        self.reader = MessageReader()
        self.stderr = ''
        self.process.setWorkingDirectory(str(root))
        self.process.start(sys.executable, ['-m', 'pyGHDL.cli.lsp'])
        self.timeout.start(15000)

    def initialize(self):
        self.request('initialize', {'processId': os.getpid(), 'rootPath': str(self.root),
                     'rootUri': self.root.as_uri(), 'capabilities': {}}, self.initialized)

    def initialized(self, result):
        if result is None:
            return
        self.timeout.stop()
        self.notify('initialized', {})
        self.running = True
        self.ready.emit()

    def send(self, message):
        self.process.write(frame({'jsonrpc': '2.0', **message}))

    def notify(self, method, params):
        self.send({'method': method, 'params': params})

    def request(self, method, params, callback):
        self.serial += 1
        self.pending[self.serial] = callback
        self.send({'id': self.serial, 'method': method, 'params': params})

    def read(self):
        try:
            messages = self.reader.feed(bytes(self.process.readAllStandardOutput()))
        except (ValueError, StopIteration, KeyError) as error:
            self.failed.emit(f'Invalid language server response: {error}')
            return
        for message in messages:
            if 'method' in message:
                if 'id' in message:
                    self.send({'id': message['id'], 'error': {'code': -32601, 'message': 'Unsupported client request'}})
                else:
                    self.notification.emit(message['method'], message.get('params', {}))
            else:
                callback = self.pending.pop(message.get('id'), None)
                if callback:
                    callback(message.get('result'))

    def read_errors(self):
        self.stderr = (self.stderr + bytes(self.process.readAllStandardError()).decode('utf-8', 'replace'))[-8000:]

    def finished(self, code, status):
        self.running = False
        self.timeout.stop()
        if not self.stopping:
            self.failed.emit(self.stderr.strip() or f'Language server exited ({code}).')

    def stop(self):
        self.stopping = True
        self.timeout.stop()
        self.running = False
        self.pending.clear()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            # Bound cleanup even when libghdl is stuck analyzing incomplete code.
            self.process.terminate()
            if not self.process.waitForFinished(500):
                self.process.kill()
                self.process.waitForFinished(500)


def cursor_at(editor, position):
    block = editor.document().findBlockByNumber(position['line'])
    cursor = QTextCursor(editor.document())
    if block.isValid():
        prefix = block.text()[:position['character']]
        cursor.setPosition(block.position() + len(prefix.encode('utf-16-le')) // 2)
    return cursor


def server_position(cursor):
    text = cursor.block().text().encode('utf-16-le')[:cursor.positionInBlock() * 2]
    return {'line': cursor.blockNumber(), 'character': len(text.decode('utf-16-le', 'ignore'))}


class EditorAssistance(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.page = window, window.code_page
        self.temp = tempfile.TemporaryDirectory(prefix='eitri-lsp-')
        self.root = Path(self.temp.name).resolve()
        self.server = LanguageServer(self)
        self.server.ready.connect(self.sync)
        self.server.notification.connect(self.notification)
        self.server.failed.connect(self.failed)
        self.documents, self.aliases, self.diagnostics = {}, {}, {}
        self.identity = None
        self.unavailable = self.closed = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.sync)
        self.page.assistance.toggled.connect(self.toggle)
        self.page.problems.itemActivated.connect(self.open_problem)
        window.sidebar.standard.currentTextChanged.connect(self.restart)
        self.page.editor_added.connect(self.connect_editor)
        for editor in self.page.editors:
            self.connect_editor(editor)

    def connect_editor(self, editor):
        editor.textChanged.connect(self.changed)
        editor.hover_requested.connect(lambda position, point, e=editor: self.query(e, position, 'hover', point))
        editor.definition_requested.connect(lambda e=editor: self.query(e, server_position(e.textCursor()), 'definition'))
        self.schedule()

    def changed(self):
        editor = self.sender()
        if editor in self.page.editors:
            editor.set_diagnostics([])
            self.diagnostics.pop(self.uri_for(editor), None)
        self.rebuild_problems()
        self.schedule()

    def schedule(self):
        if not self.closed and self.page.assistance.isChecked() and not self.unavailable:
            self.timer.start()

    def toggle(self, enabled):
        self.restart()
        self.page.lsp_status.setText('VHDL assistance starting…' if enabled else 'VHDL assistance off')

    def restart(self, *_):
        self.server.stop()
        self.documents.clear()
        self.diagnostics.clear()
        self.identity = None
        self.unavailable = False
        for editor in self.page.editors:
            editor.set_diagnostics([])
        self.rebuild_problems()
        self.schedule()

    def failed(self, message):
        self.unavailable = True
        self.server.stop()
        self.page.lsp_status.setText('VHDL assistance unavailable — toggle to retry')
        self.page.lsp_status.setToolTip(message)

    def sources(self):
        project = self.window.project
        if project:
            project.refresh(self.window.documents.overlays())
            try:
                sources = project.ordered_sources()
            except ValueError:
                sources = [{'path': p, 'source': s, 'library': project.library_for(p)} for p, s in project.sources.items()]
        else:
            sources = []
        for index, record in enumerate(self.window.documents.records):
            if not record.path and record.editor.toPlainText().strip():
                sources.append({'path': str(self.root / f'untitled_{index}.vhd'), 'source': record.editor.toPlainText(), 'library': 'work'})
        return sources

    def sync(self):
        if self.closed or self.unavailable or not self.page.assistance.isChecked():
            return
        sources = self.sources()
        if not sources:
            return
        identity = (tuple((s['path'], s['library']) for s in sources), self.window.sidebar.standard.currentText())
        if self.identity != identity:
            self.server.stop()
            self.documents.clear()
            self.diagnostics.clear()
            self.identity = identity
            files = []
            self.aliases.clear()
            for index, source in enumerate(sources):
                original = Path(source['path']).resolve().as_uri()
                mirror = self.root / f'source_{index:04d}.vhd'
                mirror.write_bytes(source['source'].encode('iso-8859-1', 'replace'))
                self.aliases[original] = mirror.as_uri()
                files.append({'file': str(mirror), 'library': source['library']})
            (self.root / 'hdl-prj.json').write_text(json.dumps({'options': {'ghdl_analysis': ['--std=' + STANDARDS[identity[1]]]}, 'files': files}))
            self.page.lsp_status.setText('Indexing project with GHDL…')
            self.server.start(self.root)
            return
        if not self.server.running:
            return
        for source in sources:
            uri, text = Path(source['path']).resolve().as_uri(), source['source']
            server_uri = self.aliases[uri]
            previous, version = self.documents.get(uri, (None, 0))
            if text == previous:
                continue
            self.documents[uri] = (text, version + 1)
            if previous is None:
                self.server.notify('textDocument/didOpen', {'textDocument': {'uri': server_uri, 'languageId': 'vhdl', 'version': 1, 'text': text}})
            else:
                lines = previous.split('\n')
                self.server.notify('textDocument/didChange', {'textDocument': {'uri': server_uri, 'version': version + 1},
                    'contentChanges': [{'range': {'start': {'line': 0, 'character': 0}, 'end': {'line': len(lines) - 1, 'character': len(lines[-1])}}, 'text': text}]})
        self.page.lsp_status.setText(f'GHDL · {len(sources)} sources · hover · F12 definition')

    def uri_for(self, editor):
        index = self.page.editors.index(editor)
        path = self.window.documents.records[index].path
        return (path or self.root / f'untitled_{index}.vhd').as_uri()

    def original_uri(self, uri):
        return next((original for original, mirror in self.aliases.items() if mirror == uri), uri)

    def notification(self, method, params):
        if method != 'textDocument/publishDiagnostics':
            return
        uri = self.original_uri(params['uri'])
        self.diagnostics[uri] = params.get('diagnostics', [])
        for editor in self.page.editors:
            if self.uri_for(editor) == uri:
                if self.documents.get(uri, (None,))[0] == editor.toPlainText():
                    editor.set_diagnostics(self.diagnostics[uri])
        self.rebuild_problems()

    def rebuild_problems(self):
        self.page.problems.clear()
        for uri, diagnostics in self.diagnostics.items():
            path = Path(QUrl(uri).toLocalFile())
            name = self.window.project.relative(path) if self.window.project else path.name
            for diagnostic in diagnostics:
                position = diagnostic['range']['start']
                severity = 'Error' if diagnostic.get('severity', 1) == 1 else 'Warning'
                item = QListWidgetItem(f'{name}:{position["line"] + 1} — {severity}: {diagnostic["message"]}')
                item.setData(Qt.ItemDataRole.UserRole, (uri, position))
                self.page.problems.addItem(item)
        self.page.problems.setVisible(self.page.problems.count() > 0)

    def open_problem(self, item):
        uri, position = item.data(Qt.ItemDataRole.UserRole)
        self.show_definition({'uri': uri, 'range': {'start': position}})

    def query(self, editor, position, kind, point=None):
        self.timer.stop()
        self.sync()
        uri = self.uri_for(editor)
        if not self.server.running or uri not in self.documents:
            return
        text = editor.toPlainText()
        def result(value):
            if not value or editor not in self.page.editors or text != editor.toPlainText() or uri != self.uri_for(editor):
                return
            if kind == 'hover':
                contents = value.get('contents', '')
                if not isinstance(contents, list):
                    contents = [contents]
                text_value = '\n'.join(item.get('value', '') if isinstance(item, dict) else item for item in contents)
                import html
                QToolTip.showText(point, '<pre>' + html.escape(text_value) + '</pre>', editor)
            else:
                self.show_definition(value[0] if isinstance(value, list) else value)
        self.server.request('textDocument/' + kind, {'textDocument': {'uri': self.aliases[uri]}, 'position': position}, result)

    def show_definition(self, location):
        uri, position = self.original_uri(location['uri']), location['range']['start']
        for editor in self.page.editors:
            if self.uri_for(editor) == uri:
                self.page.code_tabs.setCurrentWidget(editor)
                editor.setTextCursor(cursor_at(editor, position))
                editor.ensureCursorVisible()
                editor.setFocus()
                return
        path = Path(QUrl(uri).toLocalFile())
        if path.is_file() and self.window.documents.load(path, position['line']):
            self.window.editor.setTextCursor(cursor_at(self.window.editor, position))

    def close(self):
        self.closed = True
        self.timer.stop()
        self.server.stop()
        self.temp.cleanup()
