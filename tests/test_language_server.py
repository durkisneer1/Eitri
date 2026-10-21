"""Protocol framing and real bundled GHDL editor assistance."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
from eitri.ui.language_server import MessageReader, frame, cursor_at, server_position
from eitri.ui.window import Workspace


def wait(app, condition):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(.01)
    assert condition(), 'Timed out waiting for GHDL LS'


@pytest.fixture
def workspace(tmp_path):
    app = QApplication.instance() or QApplication([])
    w = Workspace(run_root=tmp_path / 'runs')
    w.open_folder(tmp_path)
    yield app, w
    for e in w.code_page.editors:
        e.document().setModified(False)
    w.close()
    assert w.assistance.server.process.state() == QProcess.ProcessState.NotRunning


def test_fragmented_utf8_frames():
    messages = [{'id': 1, 'result': 'éλ'}, {'method': 'hello', 'params': {}}]
    raw = b''.join(frame(m) for m in messages)
    reader = MessageReader()
    result = []
    for byte in raw:
        result += reader.feed(bytes([byte]))
    assert result == messages
    assert reader.buffer == b''


def test_editor_column_conversion(workspace):
    _, w = workspace
    e = w.editor
    e.setPlainText('-- 🎉 comment\nentity demo is end;')
    position = {'line': 0, 'character': 5}
    cursor = cursor_at(e, position)
    assert cursor.positionInBlock() == 6
    assert server_position(cursor) == position


@pytest.mark.integration
def test_live_diagnostics_edits_hover_definition_and_restart(workspace, tmp_path):
    pytest.importorskip('pyGHDL')
    app, w = workspace
    e = w.editor
    broken = 'entity demo is end;\narchitecture rtl of demo is\n signal a : bit;\nbegin\n a <= missing;\nend;\n'
    e.setPlainText(broken)
    wait(app, lambda: bool(e.diagnostics) or w.assistance.unavailable)
    assert not w.assistance.unavailable, w.code_page.lsp_status.toolTip()
    assert any('missing' in d['message'] for d in e.diagnostics)
    assert w.code_page.problems.count() > 0
    fixed = broken.replace('missing', "'0'")
    e.setPlainText(fixed)
    uri = w.assistance.uri_for(e)
    wait(app, lambda: w.assistance.documents.get(uri, (None,))[0] == fixed)
    results = {}
    for kind in ('hover', 'definition'):
        w.assistance.server.request('textDocument/' + kind,
            {'textDocument': {'uri': w.assistance.aliases[uri]}, 'position': {'line': 4, 'character': 1}},
            lambda value, key=kind: results.update({key: value}))
    wait(app, lambda: len(results) == 2)
    assert not e.diagnostics
    assert results['hover']['contents']
    assert results['definition'][0]['range']['start']['line'] == 2
    w.assistance.show_definition(results['definition'][0])
    assert e.textCursor().blockNumber() == 2
    # Save As changes the URI and restarts GHDL's library state safely.
    assert w.write(tmp_path / 'saved.vhd')
    w.refresh_project()
    wait(app, lambda: w.assistance.server.running and w.paths[0].as_uri() in w.assistance.documents)
    assert not w.assistance.unavailable
    w.code_page.assistance.setChecked(False)
    assert w.assistance.server.process.state() == QProcess.ProcessState.NotRunning
    w.code_page.assistance.setChecked(True)
    wait(app, lambda: w.assistance.server.running)
    assert not w.assistance.unavailable


@pytest.mark.integration
def test_lsp_loads_component_sources(workspace, tmp_path):
    pytest.importorskip('pyGHDL')
    app, w = workspace
    child = tmp_path / 'child.vhd'
    child.write_text('entity child is end; architecture rtl of child is begin end;')
    assert w.write(tmp_path / 'top.vhd')
    w.editor.setPlainText('entity top is end; architecture rtl of top is begin u: entity work.child; end;')
    # Explicit reference also covers no-port entity instantiation.
    w.editor.setPlainText('-- eitri-source: "child.vhd"\n' + w.editor.toPlainText())
    wait(app, lambda: w.assistance.server.running and len(w.assistance.documents) == 2)
    done = []
    w.assistance.server.request('textDocument/documentSymbol',
        {'textDocument': {'uri': w.assistance.aliases[w.assistance.uri_for(w.editor)]}}, done.append)
    wait(app, lambda: bool(done))
    assert not w.editor.diagnostics
    assert child.as_uri() in w.assistance.documents
