import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest
import yosys
import netlistsvg

pytestmark = pytest.mark.integration


def test_qt_import_without_creating_a_window():
    from PySide6.QtWidgets import QMainWindow
    assert callable(QMainWindow)


def test_yosys_to_svg(tmp_path):
    (tmp_path / 'gate.v').write_text('module gate(input a, b, output y); assign y = a & b; endmodule\n')
    result = yosys.run_script('read_verilog gate.v; prep -top gate; write_json gate.json',
                              cwd=tmp_path, timeout=180)
    assert result.returncode == 0
    data = json.loads((tmp_path / 'gate.json').read_text())
    assert 'gate' in data['modules']
    # Exercise the packaged Node runtime, not node/npm on the host PATH.
    old = os.environ.get('PATH', '')
    try:
        os.environ['PATH'] = str(Path(sys.executable).parent)
        output = netlistsvg.render(tmp_path / 'gate.json', tmp_path / 'result with spaces.svg')
    finally:
        os.environ['PATH'] = old
    assert ET.parse(output).getroot().tag.endswith('svg')
    assert output.stat().st_size > 100


def test_native_yosys_database():
    pytest.importorskip('pyosys')
    api = yosys.libyosys()
    design = api.Design()
    assert design is not None


def test_ghdl_native_backend_if_installed(tmp_path):
    ghdl = pytest.importorskip('ghdl')
    (tmp_path / 'hello.vhd').write_text('''
entity hello is end;
architecture test of hello is begin
  process begin report "GHDL_ADAPTER_OK"; wait; end process;
end;
''')
    ghdl.run(['-a', '--std=08', 'hello.vhd'], cwd=tmp_path, capture_output=True, timeout=30)
    result = ghdl.run(['-r', '--std=08', 'hello'], cwd=tmp_path, capture_output=True, timeout=30)
    assert 'GHDL_ADAPTER_OK' in result.stdout + result.stderr


def test_rom_templates_simulate(tmp_path):
    ghdl = pytest.importorskip('ghdl')
    fixtures = Path(__file__).parent / 'fixtures'
    DESIGN_STARTER = (fixtures / 'ROM_16x32.vhd').read_text()
    TESTBENCH_STARTER = (fixtures / 'ROM_16x32_TB.vhd').read_text()
    (tmp_path / 'ROM_16x32.vhd').write_text(DESIGN_STARTER)
    (tmp_path / 'ROM_16x32_TB.vhd').write_text(TESTBENCH_STARTER)
    ghdl.run(['-a', '--std=08', 'ROM_16x32.vhd', 'ROM_16x32_TB.vhd'],
             cwd=tmp_path, capture_output=True, timeout=30)
    ghdl.run(['-r', '--std=08', 'ROM_16x32_TB', '--assert-level=error',
              '--stop-time=200ns', '--vcd=rom.vcd'],
             cwd=tmp_path, capture_output=True, timeout=30)
    lines = (tmp_path / 'rom.vcd').read_text().splitlines()
    output_id = next(line.split()[3] for line in lines
                     if line.startswith('$var') and 'data_out[31:0]' in line)
    actual = [line.split()[0][1:].upper() for line in lines
              if line.startswith('b') and line.split()[1] == output_id]
    expected = ['Z', 'DEADBEEF', 'Z', 'CAFEBABE', 'DEADFEED', 'BEEFCAFE',
                'Z', 'B16B00B5', 'DEADD00D', 'Z']
    assert actual == ['Z' * 32 if word == 'Z' else f'{int(word, 16):032b}'
                      for word in expected]
