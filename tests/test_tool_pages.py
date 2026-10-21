"""Tool failures, real pipelines, cancellation and waveform interpretation."""
import json
import os
from pathlib import Path
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog
from eitri.backend.pipeline import validate
from eitri.backend.schematic import display_netlist, inline_svg_styles
from eitri.backend.vcd import parse_vcd, value_at, format_value, time_label
from eitri.ui.window import Workspace


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def wait_until(app, condition, seconds=60):
    end = time.monotonic() + seconds
    while not condition() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    assert condition(), 'Timed out waiting for background tool'
    app.processEvents()


@pytest.fixture
def workspace(app, tmp_path):
    window = Workspace(run_root=tmp_path / 'runs')
    fixtures = Path(__file__).parent / 'fixtures'
    window.code_page.editors[0].setPlainText((fixtures / 'ROM_16x32.vhd').read_text())
    window.code_page.editors[1].setPlainText((fixtures / 'ROM_16x32_TB.vhd').read_text())
    window.sidebar.entity.setText('ROM_16x32')
    window.sidebar.testbench.setText('ROM_16x32_TB')
    yield window
    for runner in window.tools.runners.values():
        runner.stop()
    wait_until(app, lambda: not window.tools.running)
    for editor in window.code_page.editors:
        editor.document().setModified(False)
    window.close()
    window.deleteLater()
    app.processEvents()


def test_vcd_aliases_unknowns_and_timescale(tmp_path):
    path = tmp_path / 'test.vcd'
    path.write_text('''$timescale
10 ps
$end
$scope module top $end
$var wire 4 ! data [3:0] $end
$scope module uut $end
$var wire 4 ! alias [3:0] $end
$upscope $end
$upscope $end
$enddefinitions $end
$dumpvars
bxxxx !
$end
#2
b1010 !
#4
bzzzz !
#8
''')
    data = parse_vcd(path)
    assert data['timescale'] == '10 ps'
    first, alias = data['signals']
    assert first['name'] == 'top.data[3:0]'
    assert alias['events'] == first['events']
    assert value_at(first, 0) == 'XXXX'
    assert format_value(value_at(first, 3), 4) == 'A'
    assert format_value(value_at(first, 5), 4) == 'Z'
    assert time_label(8, data['timescale']) == '80 ps'
    assert data['end_time'] == 8


def test_renderer_adaptation_preserves_original_and_styles(tmp_path):
    original = {'modules': {'test': {'ports': {'y': {'bits': ['z', 'x', 2]}}, 'cells': {}, 'netnames': {}}}}
    display = display_netlist(original)
    assert original['modules']['test']['ports']['y']['bits'] == ['z', 'x', 2]
    assert all(isinstance(bit, int) for bit in display['modules']['test']['ports']['y']['bits'])
    assert {cell['type'] for cell in display['modules']['test']['cells'].values()} == {'High impedance (Z)', 'Unknown (X)'}
    svg = tmp_path / 'test.svg'
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><style>svg {stroke:#000;fill:none;} text {fill:#000;stroke:none;}</style><g><path d="M0 0L10 10"/><text>Label</text></g></svg>')
    inline_svg_styles(svg)
    import xml.etree.ElementTree as ET
    root = ET.parse(svg).getroot()
    assert root.find('.//{*}path').get('stroke') == '#000'
    assert root.find('.//{*}text').get('fill') == '#000'


def test_invalid_settings_dont_spawn_process(workspace):
    workspace.sidebar.testbench.setText('bad; injected')
    workspace.tools.start('simulation')
    assert not workspace.tools.running
    assert 'entity name' in workspace.simulation_page.status.text()
    workspace.sidebar.entity.setText('ROM_16x32')
    request = workspace.tools.snapshot('circuit')
    request['entity'] = 'bad__name'
    with pytest.raises(ValueError):
        validate(request)


@pytest.mark.integration
def test_real_simulation_export_and_failure_preserve_previous_view(workspace, app, tmp_path, monkeypatch):
    pytest.importorskip('ghdl')
    workspace.sidebar.wave_format.setCurrentText('GHW')
    workspace.tools.start('simulation')
    wait_until(app, lambda: not workspace.tools.running)
    page = workspace.simulation_page
    assert page.has_result, page.log.toPlainText()
    assert page.wave_file.suffix == '.ghw'
    assert page.wave_file.stat().st_size > 0
    signal = next(signal for signal in page.data['signals'] if signal['name'] == 'rom_16x32_tb.data_out[31:0]')
    assert format_value(value_at(signal, 20_000_000), 32) == 'DEADBEEF'
    assert format_value(value_at(signal, 40_000_000), 32) == 'Z'
    page.wave.cursor = 20_000_000
    page.update_values(page.wave.cursor)
    page.wave.zoom_by(2)
    assert page.wave.zoom == 2
    target = tmp_path / 'export.zip'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(target), ''))
    page.export_run()
    import zipfile
    with zipfile.ZipFile(target) as archive:
        assert {'design.vhd', 'testbench.vhd', 'wave.vcd', 'wave.ghw', 'run.log'} <= set(archive.namelist())
    old_wave = page.wave_file
    workspace.code_page.editors[0].insertPlainText('invalid VHDL\n')
    assert 'Inputs changed' in page.status.text()
    workspace.tools.start('simulation')
    wait_until(app, lambda: not workspace.tools.running)
    assert 'Failed' in page.status.text()
    assert 'design.vhd' in page.log.toPlainText()
    assert page.wave_file == old_wave
    assert page.run_button.isEnabled() and not page.stop_button.isEnabled()


@pytest.mark.integration
def test_real_circuit_generation_and_svg_preview(workspace, app):
    pytest.importorskip('ghdl')
    workspace.tools.start('circuit')
    wait_until(app, lambda: not workspace.tools.running, seconds=240)
    page = workspace.circuit_page
    assert page.has_result, page.log.toPlainText()
    assert page.svg_file.is_file()
    assert page.view.scene().items()[0].renderer().isValid()
    netlist = json.loads((page.result_dir / 'netlist.json').read_text())
    assert '"z"' in json.dumps(netlist)  # Original four-state data stays intact.
    assert 'High impedance (Z)' in page.svg_file.read_text()
    assert 'cells' in page.status.text()


@pytest.mark.integration
def test_stop_terminates_running_simulator(workspace, app):
    pytest.importorskip('ghdl')
    workspace.code_page.editors[1].setPlainText('''entity spin is end;
architecture test of spin is begin
process begin loop null; end loop; wait; end process;
end;
''')
    workspace.sidebar.testbench.setText('spin')
    workspace.tools.start('simulation')
    page = workspace.simulation_page
    wait_until(app, lambda: '=== Simulate' in page.log.toPlainText())
    assert workspace.tools.running
    page.stop_requested.emit()
    wait_until(app, lambda: not workspace.tools.running)
    assert page.status.text() == 'Stopped.'
    assert not (page.result_dir / 'result.json').exists()
    assert page.run_button.isEnabled()


def test_scope_metadata_is_not_drawn():
    original = {'modules': {'top': {'ports': {}, 'netnames': {}, 'cells': {
        'scope': {'type': '$scopeinfo', 'connections': {}},
        'fa0': {'type': 'adder', 'connections': {}}
    }}, 'adder': {'ports': {}, 'netnames': {}, 'cells': {}}}}
    drawing = display_netlist(original, top='top')
    assert list(drawing['modules']) == ['top']
    assert list(drawing['modules']['top']['cells']) == ['fa0']
    assert drawing['modules']['top']['cells']['fa0']['type'] == 'fa0'
    assert drawing['modules']['top']['cells']['fa0']['attributes']['component_type'] == 'adder'
    assert original['modules']['top']['cells']['scope']['type'] == '$scopeinfo'


@pytest.mark.integration
def test_simple_and_detailed_hierarchy(tmp_path):
    from eitri.backend.pipeline import run_pipeline
    pytest.importorskip('ghdl')
    # VHDL source keeps four real instances, with a carry chain between them.
    source = """library ieee; use ieee.std_logic_1164.all;
entity bitadder is port(a,b,ci: in std_logic; s,co: out std_logic); end;
architecture rtl of bitadder is begin s<=a xor b xor ci;
co<=(a and b) or (ci and (a xor b)); end;
library ieee; use ieee.std_logic_1164.all;
entity top is port(a,b: in std_logic_vector(3 downto 0);
ci: in std_logic; s: out std_logic_vector(3 downto 0); co: out std_logic); end;
architecture rtl of top is
component bitadder is port(a,b,ci: in std_logic; s,co: out std_logic); end component;
signal c: std_logic_vector(4 downto 0);
begin c(0)<=ci; co<=c(4);
fa0: bitadder port map(a(0),b(0),c(0),s(0),c(1));
fa1: bitadder port map(a(1),b(1),c(1),s(1),c(2));
fa2: bitadder port map(a(2),b(2),c(2),s(2),c(3));
fa3: bitadder port map(a(3),b(3),c(3),s(3),c(4));
end;"""
    request = dict(kind='circuit', standard='VHDL 2008', entity='top', design=source)
    for detail in ('Simple', 'Detailed'):
        directory = tmp_path / detail
        result = run_pipeline(dict(request, circuit_detail=detail), directory, log=lambda _: None)
        svg = (directory / 'schematic.svg').read_text()
        assert '$scopeinfo' not in svg
        netlist = json.loads((directory / 'netlist.json').read_text())
        cells = netlist['modules'][result['top']]['cells']
        if detail == 'Simple':
            assert set(cells) == {'fa0', 'fa1', 'fa2', 'fa3'}
            assert all(cell['type'] in netlist['modules'] for cell in cells.values())
            assert all(f'>fa{i}<' in svg for i in range(4))
            assert result['cells'] == 4
        else:
            assert all(cell['type'] not in netlist['modules'] for cell in cells.values())
            assert result['cells'] > 4


@pytest.mark.integration
def test_ram_simple_preserves_memory_detailed_expands_it(tmp_path):
    from eitri.backend.pipeline import run_pipeline
    pytest.importorskip('ghdl')
    source = (Path(__file__).parent / 'fixtures' / 'RAM_16x32Bits.vhd').read_text()
    counts = {}
    for detail in ('Simple', 'Detailed'):
        directory = tmp_path / detail
        result = run_pipeline(dict(kind='circuit', standard='VHDL 2008',
                                   entity='RAM_16x32Bits', design=source,
                                   circuit_detail=detail), directory, log=lambda _: None)
        netlist = json.loads((directory / 'netlist.json').read_text())
        cells = netlist['modules'][result['top']]['cells'].values()
        types = {cell['type'] for cell in cells}
        counts[detail] = result['cells']
        if detail == 'Simple':
            memory = next(cell for cell in cells if cell['type'] == '$mem_v2')
            assert int(memory['parameters']['WIDTH'], 2) == 32
            assert int(memory['parameters']['SIZE'], 2) == 16
        else:
            assert not any(kind.startswith('$mem') for kind in types)
            assert '$dff' in types
            assert '$dffe' not in types
        assert (directory / 'schematic.svg').stat().st_size > 0
    assert counts['Simple'] < counts['Detailed']
