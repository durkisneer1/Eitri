"""Behavioral invariants independent of source/entity names and lab fixtures."""
from copy import deepcopy
from itertools import product
import json
import random

import pytest
from eitri.backend.schematic import display_netlist
from test_mux_schematic import evaluate


def cell(kind, **ports):
    return dict(type=kind, attributes={}, parameters={}, connections=ports,
                port_directions={p: 'output' if p == 'Y' else 'input' for p in ports})


def decoded_mux(select_width, width):
    # Deliberately shuffled IDs and branches: numbering is not bit significance.
    rng = random.Random(select_width * 100 + width)
    selector = list(range(2, 2 + select_width))
    rng.shuffle(selector)
    branches = list(range(2 ** select_width))
    rng.shuffle(branches)
    data = list(range(20, 20 + width * len(branches)))
    outputs = list(range(200, 200 + width))
    selects = list(range(300, 300 + len(branches)))
    cells = {}
    for n, branch in enumerate(branches):
        cells[f'compare_{n}'] = cell('$eq', A=selector,
            B=[str((branch >> i) & 1) for i in range(select_width)], Y=[selects[n]])
    cells['choose'] = cell('$pmux', A=['x'] * width,
        B=[bit for branch in branches for bit in data[branch * width:(branch + 1) * width]],
        S=selects, Y=outputs)
    return {'ports': {'S': dict(direction='input', bits=selector),
                      'D': dict(direction='input', bits=data),
                      'Y': dict(direction='output', bits=outputs)}, 'cells': cells, 'netnames': {}}


@pytest.mark.parametrize('select_width,width', list(product(range(1, 5), (1, 3, 7))))
@pytest.mark.parametrize('detail', ('Simple', 'Detailed'))
def test_binary_decoder_truth_tables(select_width, width, detail):
    original = {'modules': {'arbitrary_name': decoded_mux(select_width, width)}}
    saved = deepcopy(original)
    drawing = display_netlist(original, detail=detail)['modules']['arbitrary_name']
    assert original == saved
    # All selector values, walking data bits and all-ones: no swapped inputs,
    # reversed bus bits or cross-bit coupling can satisfy these checks.
    count = (1 << select_width) * width
    for selector, data in product(range(1 << select_width), [0, (1 << count) - 1, *(1 << b for b in range(count))]):
        assert evaluate(drawing, {'S': selector, 'D': data}) == (data >> (selector * width)) & ((1 << width) - 1)


def test_ambiguous_decoder_is_preserved():
    module = decoded_mux(2, 1)
    module['cells']['other_driver'] = deepcopy(module['cells']['compare_0'])
    drawing = display_netlist({'modules': {'m': module}})['modules']['m']
    assert drawing['cells']['choose']['type'] == '$pmux'
    assert 'other_driver' in drawing['cells']


def test_unknown_aliases_are_not_hardware_but_unknown_outputs_are():
    module = dict(ports={'Y': dict(direction='output', bits=[2])}, cells={},
                  netnames={'unused': dict(bits=['x'] * 9), 'unused_z': dict(bits=['z'])})
    drawing = display_netlist({'modules': {'m': module}})['modules']['m']
    assert drawing['cells'] == {}
    module['netnames']['unused_binary_wire'] = dict(bits=[2, 3])
    module['ports']['Y']['bits'] = ['x', 'z']
    drawing = display_netlist({'modules': {'m': module}})['modules']['m']
    assert {c['type'] for c in drawing['cells'].values()} == {'Unknown (X)', 'High impedance (Z)'}
    assert all(bit > 3 for bit in drawing['ports']['Y']['bits'])


def test_component_instance_name_cannot_trigger_mux_expansion():
    child = dict(ports={}, cells={}, netnames={})
    parent = dict(ports={}, netnames={}, cells={'eitri_mux_2_1': cell('child')})
    drawing = display_netlist({'modules': {'top': parent, 'child': child}}, top='top', detail='Detailed')
    assert drawing['modules']['top']['cells']['eitri_mux_2_1']['type'] == 'eitri_mux_2_1'


def executable_display(module):
    """Test oracle: translate display symbols back into standard Yosys cells."""
    module = deepcopy(module)
    cells = module['cells']
    vectors = [p['bits'] for p in module['ports'].values()]
    vectors += [v for c in cells.values() for v in c['connections'].values()]
    next_bit = max(b for v in vectors for b in v if isinstance(b, int)) + 1
    for name, c in list(cells.items()):
        attrs, ports = c.get('attributes', {}), c['connections']
        if 'operation_type' in attrs:
            c['type'] = attrs['operation_type']
        elif 'mux_inputs' in attrs:
            level = [ports[f'D{i}'] for i in range(attrs['mux_inputs'])]
            del cells[name]
            for s in ports['S']:
                new = []
                for i in range(0, len(level), 2):
                    width = len(level[i])
                    y = ports['Y'] if len(level) == 2 else list(range(next_bit, next_bit + width))
                    next_bit += width
                    mux = cell('$mux', A=level[i], B=level[i+1], S=[s], Y=y)
                    mux['parameters'] = {'WIDTH': width}
                    cells[f'{name}_{next_bit}'] = mux
                    new.append(y)
                level = new
        elif 'repeat_count' in attrs or c['type'] in ('Unknown (X)', 'High impedance (Z)'):
            width = len(ports['Y'])
            a = ports['A'] * width if 'A' in ports else ['x' if c['type'].startswith('Unknown') else 'z'] * width
            c.update(type='$pos', connections={'A': a, 'Y': ports['Y']},
                     port_directions={'A': 'input', 'Y': 'output'},
                     parameters={'A_SIGNED': 0, 'A_WIDTH': width, 'Y_WIDTH': width})
        elif 'gate_type' in attrs:
            width = len(ports['Y'])
            c['type'] = attrs['gate_type']
            c['parameters'] = {'A_SIGNED': 0, 'A_WIDTH': len(ports['A']), 'Y_WIDTH': width}
            if 'B' in ports:
                if len(ports['B']) == 1:
                    ports['B'] *= width
                c['parameters'].update(B_SIGNED=0, B_WIDTH=len(ports['B']))
    # Presentation labels are not HDL attributes (Yosys JSON only accepts
    # a restricted subset of escaped Unicode strings).
    for c in cells.values():
        c.get('attributes', {}).pop('component_type', None)
    return module


@pytest.mark.integration
@pytest.mark.parametrize('body', [
    'y <= a when s = "00" else b when s = "01" else c when s = "10" else d;',
    'with s select y <= a when "00", b when "01", c when "10", d when others;',
    'y <= std_logic_vector(unsigned(a) + unsigned(b)) xor c;',
    'y <= std_logic_vector(shift_left(unsigned(a), to_integer(unsigned(s))));',
    'y <= a when signed(a) < signed(b) else b;',
    'y <= (others => xor a);',
    "y <= (others => a(0)) when s(0) = '1' else (others => '0');",
    'y <= std_logic_vector(resize(signed(a(1 downto 0)), 4));',
    "process(clk) begin if rising_edge(clk) then if s(0) = '1' then y <= a; end if; end if; end process;",
    "process(clk, rst) begin if rst = '1' then y <= (others => '0'); elsif rising_edge(clk) then y <= a; end if; end process;",
])
def test_synthesis_to_display_equivalence(tmp_path, body):
    from eitri.backend.pipeline import run_pipeline
    yosys = pytest.importorskip('yosys')
    source = '''library ieee; use ieee.std_logic_1164.all; use ieee.numeric_std.all;
entity top is port(a,b,c,d: in std_logic_vector(3 downto 0);
s: in std_logic_vector(1 downto 0); clk,rst: in std_logic;
y: out std_logic_vector(3 downto 0)); end;
architecture rtl of top is begin ''' + body + ' end;'
    for mode in ('Simple', 'Detailed'):
        directory = tmp_path / mode
        result = run_pipeline(dict(kind='circuit', standard='VHDL 2008', entity='top',
                                   design=source, circuit_detail=mode), directory, lambda _: None)
        raw = json.loads((directory / 'netlist.json').read_text())
        display = json.loads((directory / 'schematic.json').read_text())
        top = result['top']
        import xml.etree.ElementTree as ET
        labels = {e.text for e in ET.parse(directory / 'schematic.svg').iter() if e.tag.endswith('text')}
        for c in display['modules'][top]['cells'].values():
            if 'component_type' in c.get('attributes', {}):
                assert c['attributes']['component_type'] in labels
        (directory / 'executable.json').write_text(json.dumps({'modules': {top: executable_display(display['modules'][top])}}))
        # Prove every output bit, including state correspondence for retained
        # registers. Async FFs use the same async2sync model on both sides.
        # No sampled stimulus or expected symbol counts.
        proof = yosys.run_script(
            f'read_json netlist.json; rename {top} gold; read_json executable.json; rename {top} gate; '
            'async2sync; equiv_make gold gate equiv; hierarchy -top equiv; equiv_struct; equiv_simple; equiv_induct; equiv_status -assert',
            cwd=directory, timeout=60)
        assert 'Equivalence successfully proven' in proof.stdout
        assert raw == json.loads((directory / 'netlist.json').read_text())


def test_reductions_have_distinct_symbols_and_preserve_parameters():
    operations = {
        'zero': cell('$logic_not', A=[2, 3, 4], Y=[5]),
        'parity': cell('$reduce_xor', A=[2, 3, 4], Y=[6]),
        'parallel': cell('$xor', A=[2, 3, 4], B=[7, 8, 9], Y=[10, 11, 12]),
    }
    raw = {'modules': {'m': dict(ports={}, netnames={}, cells=operations)}}
    drawing = display_netlist(raw)['modules']['m']['cells']
    assert drawing['zero']['type'] == 'Zero test'
    assert drawing['parity']['type'] == 'Reduce XOR'
    assert drawing['parallel']['attributes']['gate_width'] == 3
    for name in operations:
        assert drawing[name]['connections'] == operations[name]['connections']
        assert drawing[name]['parameters'] == operations[name]['parameters']


def test_overlapping_and_large_decoders_stay_explicit():
    module = decoded_mux(2, 1)
    module['cells']['compare_0']['connections']['B'] = module['cells']['compare_1']['connections']['B'][:]
    assert display_netlist({'modules': {'m': module}})['modules']['m']['cells']['choose']['type'] == '$pmux'
    module = decoded_mux(5, 1)
    assert display_netlist({'modules': {'m': module}})['modules']['m']['cells']['choose']['type'] == '$pmux'
