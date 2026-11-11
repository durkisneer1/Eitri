"""Mux presentation must preserve selection, bit order, and shared logic."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import json

import pytest
from eitri.backend.pipeline import run_pipeline
from eitri.backend.schematic import display_netlist


def evaluate(module, inputs, output_name='Y'):
    values = {'0': 0, '1': 1}
    for name, number in inputs.items():
        values.update({bit: (number >> i) & 1 for i, bit in enumerate(module['ports'][name]['bits'])})
    pending = list(module['cells'].values())
    while pending:
        ready = False
        for cell in pending[:]:
            ports = cell['connections']
            needed = [bit for p, bits in ports.items() if p != 'Y' for bit in bits]
            if not all(bit in values for bit in needed):
                continue
            data = {p: [values[b] for b in bits] for p, bits in ports.items() if p != 'Y'}
            kind = cell['attributes'].get('gate_type', cell['type'])
            if kind.startswith('eitri_repeat_'):
                output = data['A'] * cell['attributes']['repeat_count']
            elif kind.startswith('eitri_mux_'):
                selected = sum(b << i for i, b in enumerate(data['S']))
                output = data[f'D{selected}']
            elif kind == '$not':
                output = [1 - bit for bit in data['A']]
            else:
                a, b = data['A'], data['B']
                if len(b) == 1:
                    b = b * len(a)
                assert len(a) == len(b)
                assert kind in ('$and', '$or')
                output = [x & y if kind == '$and' else x | y for x, y in zip(a, b)]
            assert len(output) == len(ports['Y'])
            values.update(zip(ports['Y'], output))
            pending.remove(cell)
            ready = True
        assert ready, 'Unconnected or unsupported gate'
    return sum(values[b] << i for i, b in enumerate(module['ports'][output_name]['bits']))


@pytest.fixture(scope='module')
def mux_runs(tmp_path_factory):
    pytest.importorskip('ghdl')
    root = tmp_path_factory.mktemp('mux')
    source = (Path(__file__).parent / 'fixtures/MUX4to1_32Bits.vhd').read_text()
    runs = {}
    for mode in ('Simple', 'Detailed'):
        directory = root / mode
        result = run_pipeline(dict(kind='circuit', standard='VHDL 2008',
                                   entity='MUX4to1_32Bits', design=source, circuit_detail=mode),
                              directory, lambda _: None)
        raw = json.loads((directory / 'netlist.json').read_text())
        display = json.loads((directory / 'schematic.json').read_text())
        runs[mode] = raw, display['modules'][result['top']], directory
    return runs


@pytest.mark.integration
def test_lab_mux_both_views_preserve_every_selector_and_data_bit(mux_runs):
    for mode, (raw, module, directory) in mux_runs.items():
        cells = list(module['cells'].values())
        if mode == 'Simple':
            assert len(cells) == 1
            assert cells[0]['attributes']['mux_inputs'] == 4
            assert cells[0]['attributes']['mux_width'] == 32
        else:
            assert {c['attributes']['gate_type'] for c in cells} == {'$and', '$or', '$not'}
        assert any(c['type'] == '$pmux' for m in raw['modules'].values() for c in m['cells'].values())
        # All scalar truth-table combinations at each bit position catch input
        # permutations, bus reversal, and accidental cross-bit connections.
        for selected, bit, pattern in product(range(4), range(32), product((0, 1), repeat=4)):
            inputs = {name: value << bit for name, value in zip('ABCD', pattern)}
            assert evaluate(module, dict(inputs, S=selected)) == inputs['ABCD'[selected]]
        assert (directory / 'schematic.svg').stat().st_size > 0


@pytest.mark.integration
def test_decoder_sharing_and_incomplete_selection_are_not_hidden(mux_runs):
    raw = deepcopy(mux_runs['Simple'][0])
    top = next(iter(raw['modules']))
    module = raw['modules'][top]
    mux = next(c for c in module['cells'].values() if c['type'] == '$pmux')
    # Exposing a decoder output must keep its drivers in the schematic.
    module['ports']['decoded'] = dict(direction='output', bits=[mux['connections']['S'][0]])
    before = deepcopy(raw)
    drawing = display_netlist(raw, top=top)
    assert raw == before
    assert any(c['type'] == '$eq' for c in drawing['modules'][top]['cells'].values())
    # Remove a branch: binary selector value 3 now has no valid selection.
    mux['connections']['S'].pop()
    mux['connections']['B'] = mux['connections']['B'][:-32]
    drawing = display_netlist(raw, top=top)
    assert any(c['type'] == '$pmux' for c in drawing['modules'][top]['cells'].values())


def test_one_hot_inputs_are_not_mistaken_for_binary_decoder():
    raw = {'modules': {'m': {'ports': {}, 'netnames': {}, 'cells': {'mux': {
        'type': '$pmux', 'attributes': {}, 'parameters': {},
        'port_directions': {'A': 'input', 'B': 'input', 'S': 'input', 'Y': 'output'},
        'connections': {'A': ['x'], 'B': [4, 5], 'S': [2, 3], 'Y': [6]}
    }}}}}
    drawing = display_netlist(raw)
    assert drawing['modules']['m']['cells']['mux']['type'] == '$pmux'


@pytest.mark.integration
def test_extension_modes_and_both_schematic_views(tmp_path):
    ghdl = pytest.importorskip('ghdl')
    source = (Path(__file__).parent / 'fixtures/ExtensionUnit_32Bits.vhd').read_text()
    (tmp_path / 'extension.vhd').write_text(source)
    (tmp_path / 'check_extension.vhd').write_text('''
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity check_extension is end;
architecture test of check_extension is
  signal control : std_logic := '0';
  signal data_in : std_logic_vector(15 downto 0) := (others => '0');
  signal data_out : std_logic_vector(31 downto 0);
begin
  uut: entity work.ExtensionUnit_32Bits port map(control, data_in, data_out);
  process begin
    for value in 0 to 65535 loop
      data_in <= std_logic_vector(to_unsigned(value, 16));
      control <= '0'; wait for 1 ns;
      assert data_out = std_logic_vector(resize(unsigned(data_in), 32)) severity failure;
      control <= '1'; wait for 1 ns;
      assert data_out = std_logic_vector(resize(signed(data_in), 32)) severity failure;
    end loop;
    control <= 'X'; wait for 1 ns;
    assert data_out = (data_out'range => 'X') severity failure;
    report "EXTENSION_CHECK_PASSED";
    std.env.stop;
    wait;
  end process;
end;
''')
    ghdl.run(['-a', '--std=08', 'extension.vhd', 'check_extension.vhd'], cwd=tmp_path, timeout=30)
    result = ghdl.run(['-r', '--std=08', 'check_extension', '--assert-level=error'], cwd=tmp_path, timeout=30, capture_output=True)
    assert 'EXTENSION_CHECK_PASSED' in result.stdout + result.stderr
    for mode in ('Simple', 'Detailed'):
        directory = tmp_path / mode
        result = run_pipeline(dict(kind='circuit', standard='VHDL 2008',
                                   entity='ExtensionUnit_32Bits', design=source, circuit_detail=mode),
                              directory, lambda _: None)
        module = json.loads((directory / 'schematic.json').read_text())['modules'][result['top']]
        cells = list(module['cells'].values())
        assert not any(c['type'] in ('$pmux', '$eq', 'Unknown (X)') for c in cells)
        assert any(c['attributes'].get('repeat_count') == 16 for c in cells)
        if mode == 'Detailed':
            assert [c['type'] for c in cells if 'repeat_count' not in c['attributes']] == ['$and']
        for control, data in product((0, 1), (0, 1, 0x7fff, 0x8000, 0x9de2, 0xffff, *(1 << i for i in range(16)))):
            expected = data | (0xffff0000 if control and data & 0x8000 else 0)
            assert evaluate(module, dict(Sign_Ctrl=control, Data_In=data), 'Data_Out') == expected
