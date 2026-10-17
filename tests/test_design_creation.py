"""Creation forms, generated VHDL, and protection of existing documents."""
import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox
from eitri.backend.vhdl import Entity, Port, parse_entity, validate_entity
from eitri.ui.design_dialog import NewDesignDialog, WelcomeDialog
from eitri.ui.templates import design_template, testbench_template as make_testbench, testbench_path as bench_path
from eitri.ui.window import Workspace


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    window = Workspace(run_root=tmp_path / 'runs')
    yield window
    for editor in window.code_page.editors:
        editor.document().setModified(False)
    window.close()
    window.deleteLater()
    app.processEvents()


def sample():
    return Entity('adder', [Port('enable', 'in'), Port('a', 'in', 'STD_LOGIC_VECTOR(7 downto 0)'),
                            Port('result', 'out', 'STD_LOGIC_VECTOR(7 downto 0)')])


def test_form_scalars_vectors_and_duplicate_validation(app):
    dialog = NewDesignDialog()
    dialog.entity_name.setText('adder')
    dialog.add_port()
    dialog.ports.item(0, 0).setText('data')
    assert dialog.ports.cellWidget(0, 3).currentIndex() == 0
    dialog.ports.cellWidget(0, 2).setCurrentText('STD_LOGIC_VECTOR')
    dialog.ports.cellWidget(0, 3).widget(1).setValue(32)
    assert dialog.ports.cellWidget(0, 3).currentIndex() == 1
    assert dialog.read_entity().ports[0].data_type == 'STD_LOGIC_VECTOR(31 downto 0)'
    dialog.add_port()
    dialog.ports.item(1, 0).setText('DATA')
    dialog.accept()
    assert 'Duplicate' in dialog.error.text()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.remove_port()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted


@pytest.mark.parametrize('name, reason', [
    ('signal', 'reserved VHDL word'), ('1BitFullAdder', 'must start with a letter'),
    ('bad__name', 'consecutive underscores'), ('name_', 'end with an underscore'),
    ('', 'required'), ('my name', 'no spaces'), ('my-name', 'no spaces'),
])
def test_invalid_names(name, reason):
    with pytest.raises(ValueError, match=reason):
        validate_entity(Entity(name))


def test_parser_preserves_grouped_ports_ranges_and_default_generics():
    source = '''entity Example is
    generic (WIDTH : positive := 8);
    port (a, b : in std_logic_vector(WIDTH - 1 downto 0) := (others => '0');
          y : out std_logic_vector(0 to WIDTH - 1); enable : std_logic);
    end entity Example;
    -- entity fake is end fake;
    '''
    entity = parse_entity(source)
    assert [port.name for port in entity.ports] == ['a', 'b', 'y', 'enable']
    bench = make_testbench(entity)
    assert 'constant WIDTH : positive := 8;' in bench
    assert 'WIDTH => WIDTH' in bench
    assert 'a => a_sig' in bench and 'b => b_sig' in bench
    assert 'STD_LOGIC_VECTOR(0 to WIDTH - 1)'.lower() in bench.lower()
    assert 'entity fake' not in bench


def test_unsupported_interface_is_explicit():
    with pytest.raises(ValueError, match='STD_LOGIC'):
        parse_entity('entity foo is port (x : in integer); end foo;')


def test_new_design_and_create_testbench_write_sibling_files(window, tmp_path, monkeypatch):
    target = tmp_path / 'custom filename.vhdl'
    def accept_form(dialog):
        dialog.entity = sample()
        return QDialog.DialogCode.Accepted
    from eitri.ui.components_dialog import ComponentsDialog
    monkeypatch.setattr(ComponentsDialog, 'exec', lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(NewDesignDialog, 'exec', accept_form)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    assert window.new_file()
    assert target.read_text() == design_template(sample())
    assert window.paths == [target, None]
    assert window.sidebar.entity.text() == 'adder'
    assert window.code_page.editors[1].toPlainText() == ''
    assert window.design_flow.create_testbench()
    bench = tmp_path / 'custom filename_TB.vhdl'
    assert window.paths[1] == bench
    assert bench.read_text() == make_testbench(sample())
    assert window.sidebar.testbench.text() == 'adder_TB'
    assert 'component adder is' in bench.read_text()
    assert window.code_page.code_tabs.currentIndex() == 1


def test_existing_tb_is_not_overwritten_without_confirmation(window, tmp_path, monkeypatch):
    target = tmp_path / 'adder.vhd'
    target.write_text(design_template(sample()))
    window.design_flow.install_design(target, target.read_text())
    bench = bench_path(target)
    bench.write_text('-- hand-written testbench')
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    assert not window.design_flow.create_testbench()
    assert bench.read_text() == '-- hand-written testbench'
    assert window.paths[1] is None


def test_cancel_keeps_both_documents(window, tmp_path, monkeypatch):
    for editor in window.code_page.editors:
        editor.insertPlainText('-- unsaved')
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.new_file()
    assert not window.design_flow.open_design()
    assert all(editor.toPlainText() == '-- unsaved' for editor in window.code_page.editors)


def test_failed_generated_file_write_keeps_existing_tb(window, tmp_path, monkeypatch):
    target = tmp_path / 'adder.vhd'
    window.design_flow.install_design(target, design_template(sample()))
    window.code_page.editors[1].setPlainText('-- keep this')
    monkeypatch.setattr(window.documents, 'write_text', lambda *args: False)
    assert not window.design_flow.create_testbench()
    assert window.code_page.editors[1].toPlainText() == '-- keep this'
    assert window.paths[1] is None


def test_startup_open_updates_entity_and_clears_old_bench(window, tmp_path, monkeypatch):
    target = tmp_path / 'existing.vhd'
    target.write_text(design_template(sample()))
    def choose_open(dialog):
        dialog.choice = 'open'
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(WelcomeDialog, 'exec', choose_open)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(target), ''))
    window.design_flow.startup()
    assert window.paths[0] == target
    assert window.sidebar.entity.text() == 'adder'
    assert window.code_page.editors[0].toPlainText() == target.read_text()


@pytest.mark.integration
@pytest.mark.parametrize('entity', [sample(), Entity('empty'), Entity('uut', [Port('uut', 'in')]),
                                    Entity('stimulus', [Port('stimulus', 'out')])])
def test_generated_pair_compiles_and_elaborates(tmp_path, entity):
    ghdl = pytest.importorskip('ghdl')
    (tmp_path / 'design.vhd').write_text(design_template(entity))
    (tmp_path / 'bench.vhd').write_text(make_testbench(entity))
    ghdl.run(['-a', '--std=08', 'design.vhd', 'bench.vhd'], cwd=tmp_path, capture_output=True, timeout=30)
    ghdl.run(['-e', '--std=08', entity.name + '_TB'], cwd=tmp_path, capture_output=True, timeout=30)


@pytest.mark.integration
def test_generate_tb_from_lab_design(tmp_path):
    ghdl = pytest.importorskip('ghdl')
    source = (Path(__file__).parent / 'fixtures/ROM_16x32.vhd').read_text()
    (tmp_path / 'design.vhd').write_text(source)
    (tmp_path / 'bench.vhd').write_text(make_testbench(parse_entity(source)))
    ghdl.run(['-a', '--std=08', 'design.vhd', 'bench.vhd'], cwd=tmp_path, capture_output=True, timeout=30)
    result = ghdl.run(['-r', '--std=08', 'ROM_16x32_TB', '--stop-time=200ns'], cwd=tmp_path, capture_output=True, timeout=30)
    assert result.returncode == 0


def test_components_step_import_count_and_remove(app, tmp_path, monkeypatch):
    from eitri.ui.components_dialog import ComponentsDialog
    path = tmp_path / 'adder.vhd'
    path.write_text(design_template(sample()))
    dialog = ComponentsDialog(Entity('parent'))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    dialog.add_component()
    dialog.count.setValue(4)
    assert dialog.components[0].entity.name == 'adder'
    assert dialog.components[0].count == 4
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[2]))
    dialog.add_component()
    assert len(dialog.components) == 1
    assert 'already included' in errors[0]
    dialog.remove_component()
    assert not dialog.components
    assert not dialog.count.isEnabled()


@pytest.mark.integration
def test_four_bit_adder_reuses_four_one_bit_components(tmp_path):
    from eitri.ui.components_dialog import ComponentSource
    ghdl = pytest.importorskip('ghdl')
    child = """library IEEE; use IEEE.STD_LOGIC_1164.ALL;
entity FullAdder is port(a,b,cin: in STD_LOGIC; sum,cout: out STD_LOGIC); end;
architecture rtl of FullAdder is begin
sum <= a xor b xor cin;
cout <= (a and b) or (a and cin) or (b and cin);
end;
"""
    parent = Entity('FourBitAdder', [
        Port('a', 'in', 'STD_LOGIC_VECTOR(3 downto 0)'),
        Port('b', 'in', 'STD_LOGIC_VECTOR(3 downto 0)'), Port('cin', 'in'),
        Port('sum', 'out', 'STD_LOGIC_VECTOR(3 downto 0)'), Port('cout', 'out')])
    generated = design_template(parent, [ComponentSource(Path('FullAdder.vhd'), child, parse_entity(child), 4)])
    assert 'entity FullAdder is' not in generated
    (tmp_path / 'child.vhd').write_text(child)
    assert generated.count(' : FullAdder') == 4
    assert 'signal u_' not in generated
    assert generated.count('a => <a>') == 4
    # Manual wiring uses parent port slices directly and only three carry signals.
    generated = generated.replace('-- Declare internal signals here.',
                                  'signal c1, c2, c3 : STD_LOGIC;', 1)
    for i in range(4):
        mapping = {'a': f'a({i})', 'b': f'b({i})', 'sum': f'sum({i})',
                   'cin': 'cin' if i == 0 else f'c{i}',
                   'cout': 'cout' if i == 3 else f'c{i + 1}'}
        for port, connection in mapping.items():
            generated = generated.replace(f'<{port}>', connection, 1)
    (tmp_path / 'design.vhd').write_text(generated)
    bench = make_testbench(parent).replace('        wait;', """
        a_sig <= "1111"; b_sig <= "0000"; cin_sig <= '1';
        wait for 10 ns;
        assert sum_sig = "0000" and cout_sig = '1' severity failure;
        a_sig <= "0101"; b_sig <= "0011"; cin_sig <= '0';
        wait for 10 ns;
        assert sum_sig = "1000" and cout_sig = '0' severity failure;
        wait;
""")
    (tmp_path / 'bench.vhd').write_text(bench)
    ghdl.run(['-a', '--std=08', 'child.vhd', 'design.vhd', 'bench.vhd'], cwd=tmp_path, capture_output=True, timeout=30)
    ghdl.run(['-r', '--std=08', 'FourBitAdder_TB', '--assert-level=error', '--stop-time=30ns'],
             cwd=tmp_path, capture_output=True, timeout=30)
    result = ghdl.run(['--synth', '--std=08', '--out=verilog', 'child.vhd', 'design.vhd', '-e', 'FourBitAdder'],
                      cwd=tmp_path, capture_output=True, timeout=30)
    assert 'module fourbitadder' in result.stdout.lower()


def test_new_design_tracks_component_files_and_save_as_rebases(window, tmp_path, monkeypatch):
    from eitri.ui.components_dialog import ComponentsDialog, ComponentSource
    from eitri.backend.dependencies import references
    child_path = tmp_path / 'child.vhd'
    child = Entity('child', [Port('a', 'in'), Port('y', 'out')])
    child_source = design_template(child)
    child_path.write_text(child_source)
    target = tmp_path / 'parent.vhd'
    def ports_form(dialog):
        dialog.entity = Entity('parent')
        return QDialog.DialogCode.Accepted
    def components_form(dialog):
        dialog.components = [ComponentSource(child_path, child_source, child)]
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(NewDesignDialog, 'exec', ports_form)
    monkeypatch.setattr(ComponentsDialog, 'exec', components_form)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    assert window.new_file()
    assert references(target.read_text(), target) == [child_path]
    assert 'entity child is' not in target.read_text()
    assert window.tools.snapshot('circuit')['dependencies'][0]['source'] == child_source
    destination = tmp_path / 'moved'
    destination.mkdir()
    assert window.write(destination / 'renamed.vhd')
    assert references(window.editor.toPlainText(), window.path) == [child_path]
    window.design_flow.install_design(window.path, window.path.read_text())
    assert window.tools.snapshot('circuit')['dependencies'][0]['path'] == str(child_path)
