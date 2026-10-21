"""End-to-end folder editing, hierarchy navigation and named run workflows."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import shutil
import time
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox
import pytest
from eitri.ui.window import Workspace
from eitri.ui.hierarchy import ComponentCard


@pytest.fixture
def workspace(tmp_path):
    app = QApplication.instance() or QApplication([])
    root = tmp_path / 'cpu'
    shutil.copytree(Path(__file__).parents[1] / 'examples/learning_cpu', root)
    w = Workspace(run_root=tmp_path / 'runs')
    assert w.open_folder(root)
    yield app, w, root
    w.tools.stop_all()
    wait(app, lambda: not w.tools.running)
    for d in w.documents.records:
        d.editor.document().setModified(False)
    w.close()


def wait(app, condition):
    end = time.monotonic() + 25
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return
        time.sleep(.01)
    assert condition()


def test_file_switch_retains_unsaved_undo_and_target(workspace):
    app, w, root = workspace
    w.select_file_target('simulation', root / 'tb/cpu_tb.vhd', run=False)
    target = w.selected_target('simulation')
    w.load(root / 'rtl/alu/adder.vhd')
    leaf = w.editor
    leaf.moveCursor(QTextCursor.MoveOperation.End)
    leaf.insertPlainText('\n-- keep this unsaved')
    position = leaf.textCursor().position()
    w.load(root / 'rtl/cpu.vhd')
    assert w.selected_target('simulation') == target
    w.load(root / 'rtl/alu/adder.vhd')
    assert w.editor is leaf and w.editor.textCursor().position() == position
    assert w.editor.document().isModified()
    w.editor.undo()
    assert w.editor.toPlainText() == (root / 'rtl/alu/adder.vhd').read_text()


def test_external_reload_and_conflict_protect_edits(workspace, monkeypatch):
    _, w, root = workspace
    path = root / 'rtl/alu/adder.vhd'
    w.load(path)
    disk = path.read_text()
    path.write_text(disk + '\n-- external')
    w.documents.check_external()
    assert w.editor.toPlainText().endswith('-- external')
    w.editor.insertPlainText('-- local\n')
    local = w.editor.toPlainText()
    path.write_text(disk + '\n-- changed again')
    w.documents.check_external()
    assert w.documents.active.conflict
    assert w.editor.toPlainText() == local
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    assert not w.save()
    assert path.read_text().endswith('-- changed again')
    w.documents.keep_active()
    assert w.editor.document().isModified()
    assert w.save()
    assert path.read_text() == local


def test_hierarchy_expansion_and_source_navigation(workspace):
    _, w, root = workspace
    page = w.hierarchy_page
    page.top.setCurrentIndex(next(i for i in range(page.top.count()) if page.top.itemData(i)[0] == 'cpu'))
    cards = [i for i in page.view.scene().items() if isinstance(i, ComponentCard)]
    assert len(cards) == 6
    assert all(len(card.childItems()) == 2 for card in cards)
    assert any(card.text_items[0].toPlainText() == 'u_datapath' for card in cards)
    adder = next(c.node for c in cards if c.node['entity'] == 'work.adder')
    page.inspect(adder)
    assert 'result => sum' in page.details.toPlainText()
    page.open_instance()
    assert w.path == root / 'rtl/alu/alu.vhd'
    page.open_definition()
    assert w.path == root / 'rtl/alu/adder.vhd'
    page.collapsed.add('cpu/u_datapath')
    page.draw()
    assert len([i for i in page.view.scene().items() if isinstance(i, ComponentCard)]) == 3


@pytest.mark.integration
def test_batch_runs_and_result_navigation(workspace):
    pytest.importorskip('ghdl')
    app, w, root = workspace
    w.load(root / 'rtl/alu/adder.vhd')
    w.select_file_target('simulation', root / 'tb/alu_tb.vhd', run=False)
    w.tools.run_all()
    wait(app, lambda: len(w.tools.results) == 3 and not w.tools.running and not w.tools.queue)
    assert all(entry['success'] for entry in w.tools.results)
    assert w.selected_target('simulation').entity == 'alu_tb'
    assert w.project.config['selected_simulation'] == 'alu_tb'
    assert [w.sidebar.tests.topLevelItem(i).text(1) for i in range(3)] == ['Passed'] * 3
    assert w.path == root / 'rtl/alu/adder.vhd'
    w.tools.open_result(next(entry for entry in w.tools.results if entry['request']['target']['entity'] == 'adder_tb'))
    assert 'adder_tb' in w.simulation_page.status.text()
    assert w.simulation_page.export_button.isEnabled()


@pytest.mark.integration
def test_project_lsp_uses_unsaved_leaf_and_navigates(workspace):
    pytest.importorskip('pyGHDL')
    app, w, root = workspace
    w.load(root / 'rtl/alu/adder.vhd')
    wait(app, lambda: w.assistance.server.running and len(w.assistance.documents) == 10)
    answers = []
    uri = (root / 'rtl/alu/alu.vhd').as_uri()
    w.assistance.server.request('textDocument/definition', {'textDocument': {'uri': w.assistance.aliases[uri]}, 'position': {'line': 9, 'character': 30}}, answers.append)
    wait(app, lambda: bool(answers))
    assert not w.code_page.problems.count()
    leaf = w.editor
    leaf.setPlainText(leaf.toPlainText().replace('unsigned(a)', 'unsigned(missing)'))
    wait(app, lambda: any('missing' in d['message'] for d in leaf.diagnostics))
    assert 'missing' not in (root / 'rtl/alu/adder.vhd').read_text()


def test_hierarchy_svg_export_preserves_labels(workspace, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    _, w, _ = workspace
    target = tmp_path / 'hierarchy.svg'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    w.hierarchy_page.export_svg()
    text = target.read_text()
    assert 'u_datapath' in text
    assert 'u_add' in text
