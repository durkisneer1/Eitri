import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest
import yosys
import netlistsvg

pytestmark = pytest.mark.integration


def test_dearpygui_import_without_creating_a_window():
    import dearpygui.dearpygui as dpg
    assert callable(dpg.add_button)


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
