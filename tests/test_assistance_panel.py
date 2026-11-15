"""Diagnostics remain stable through edits, theme changes, docking and hiding."""
import pytest
from PySide6.QtCore import QSettings, Qt
from eitri.ui.window import Workspace
from eitri.ui.theme import apply_theme


@pytest.fixture
def workspace(tmp_path, monkeypatch, qt_application_lifetime):
    import eitri.ui.window as module
    settings = QSettings(str(tmp_path / 'workspace.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(module, 'QSettings', lambda *args: settings)
    window = Workspace(run_root=tmp_path / 'runs')
    window.resize(1250, 850)
    window.show()
    window.assistance.timer.stop()
    monkeypatch.setattr(window.assistance, 'schedule', lambda: None)
    qt_application_lifetime.processEvents()
    yield window, qt_application_lifetime, settings
    for editor in window.code_page.editors:
        editor.document().setModified(False)
    window.close()
    window.deleteLater()
    apply_theme('Dark')


def publish(window, diagnostics, version=1):
    controller = window.assistance
    uri = controller.uri_for(window.editor)
    controller.documents[uri] = (window.editor.toPlainText(), version)
    controller.notification('textDocument/publishDiagnostics', dict(uri=uri, version=version, diagnostics=diagnostics))


ERROR = dict(range={'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}},
             severity=1, message='Expected a semicolon.')


def test_theme_does_not_clear_diagnostics_or_move_editor(workspace):
    window, app, settings = workspace
    editor, page = window.editor, window.code_page
    editor.setPlainText('\n'.join('signal a;' for _ in range(150)))
    editor.document().setModified(False)
    publish(window, [ERROR])
    editor.verticalScrollBar().setValue(50)
    app.processEvents()
    sizes = page.editor_split.sizes()
    scroll = editor.verticalScrollBar().value()
    from PySide6.QtTest import QSignalSpy
    edits = QSignalSpy(editor.source_changed)
    window.theme_toggle.click()
    app.processEvents()
    assert edits.count() == 0
    assert page.problems.count() == 1
    assert editor.diagnostics == [ERROR]
    assert not window.assistance.pending
    assert not page.assistance_panel.isHidden()
    assert page.editor_split.sizes() == sizes
    assert editor.verticalScrollBar().value() == scroll
    assert not editor.document().isModified()
    assert window.theme_toggle.text() == ''
    assert window.theme_toggle.objectName() == 'iconButton'


def test_typing_does_not_claim_success_until_diagnostics_clear(workspace):
    window, app, settings = workspace
    page = window.code_page
    window.editor.setPlainText('entity example is end')
    publish(window, [ERROR])
    app.processEvents()
    geometry = window.editor.geometry()
    size = page.editor_split.sizes()
    message = page.assistance_panel.forge_message
    window.editor.insertPlainText(';')
    assert page.assistance_panel.empty_title.text() == 'Checking your changes…'
    assert page.assistance_panel.forge_message == message
    # An older diagnostic response cannot celebrate or restore stale problems.
    uri = window.assistance.uri_for(window.editor)
    window.assistance.notification('textDocument/publishDiagnostics', dict(uri=uri, version=1, diagnostics=[]))
    assert page.assistance_panel.empty_title.text() == 'Checking your changes…'
    publish(window, [], version=2)
    app.processEvents()
    assert page.assistance_panel.empty_title.text() == 'No diagnostics'
    assert page.assistance_panel.forge_message != message
    assert window.editor.geometry() == geometry
    assert page.editor_split.sizes() == size
    message = page.assistance_panel.forge_message
    publish(window, [], version=2)
    assert page.assistance_panel.forge_message == message
    publish(window, [ERROR], version=3)
    publish(window, [], version=4)
    assert page.assistance_panel.forge_message != message


def test_panel_size_and_dock_survive_diagnostics_hiding_and_restart(workspace, tmp_path):
    window, app, settings = workspace
    page = window.code_page
    split, panel = page.editor_split, page.assistance_panel
    split.moveSplitter(split.height() - 155 - split.handleWidth(), 1)
    app.processEvents()
    bottom_size = split.sizes()[1]
    assert settings.value('assistance/bottomSize', type=int) == bottom_size
    publish(window, [ERROR])
    publish(window, [])
    assert split.sizes()[1] == bottom_size
    panel.dock_button.click()
    app.processEvents()
    assert split.orientation() == Qt.Orientation.Horizontal
    split.moveSplitter(split.width() - 330 - split.handleWidth(), 1)
    app.processEvents()
    right_size = split.sizes()[1]
    assert settings.value('assistance/rightSize', type=int) == right_size
    panel.dock_button.click()
    app.processEvents()
    assert split.sizes()[1] == bottom_size
    panel.dock_button.click()
    app.processEvents()
    assert split.sizes()[1] == right_size
    panel.hide_button.click()
    publish(window, [ERROR])
    assert panel.isHidden()
    assert not page.show_problems.isChecked()
    page.show_problems.click()
    app.processEvents()
    assert not panel.isHidden()
    assert split.sizes()[1] == right_size
    second = Workspace(run_root=tmp_path / 'second')
    second.resize(1250, 850)
    second.show()
    app.processEvents()
    assert second.code_page.editor_split.dock == 'right'
    assert second.code_page.editor_split.sizes()[1] == right_size
    second.close()
    second.deleteLater()


def test_disabled_assistance_does_not_offer_false_clean_result(workspace):
    window, app, settings = workspace
    publish(window, [ERROR])
    window.code_page.assistance.setChecked(False)
    assert window.code_page.assistance_panel.empty_title.text() == 'Assistance is off'
    assert not window.code_page.assistance_panel.isHidden()
    window.code_page.assistance.setChecked(True)
    window.assistance.failed('Cannot start GHDL')
    assert window.code_page.assistance_panel.empty_title.text() == 'The forge needs attention'


def test_sync_does_not_resend_while_validation_is_pending(workspace, monkeypatch):
    window, app, settings = workspace
    controller = window.assistance
    window.editor.setPlainText('entity example is end;')
    uri = controller.uri_for(window.editor)
    from PySide6.QtCore import QUrl
    path = QUrl(uri).toLocalFile()
    source = dict(path=path, source=window.editor.toPlainText(), library='work')
    monkeypatch.setattr(controller, 'sources', lambda: [source])
    controller.identity = (((path, 'work'),), window.sidebar.standard.currentText())
    controller.aliases[uri] = uri
    controller.documents[uri] = (source['source'], 1)
    controller.pending.add(uri)
    controller.unsent_edits.clear()
    controller.server.running = True
    sent = []
    monkeypatch.setattr(controller.server, 'notify', lambda *args: sent.append(args))
    controller.sync()
    controller.sync()
    assert sent == []
    assert controller.documents[uri][1] == 1
    # An edit then undo before the debounce fires still requests validation,
    # since the previous diagnostics were cleared by the edit.
    window.editor.insertPlainText(' ')
    window.editor.undo()
    controller.sync()
    assert len(sent) == 1
    assert controller.documents[uri][1] == 2
