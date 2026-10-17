"""Dependency persistence, graph resolution, and actual multi-file builds."""
from pathlib import Path
import pytest
from eitri.backend.dependencies import add_references, references, rebase_references, snapshot_dependencies
from eitri.backend.pipeline import run_pipeline


def wrapper(name, child):
    return f"""library ieee; use ieee.std_logic_1164.all;
entity {name} is port (a: in std_logic; y: out std_logic); end;
architecture rtl of {name} is
component {child} is port(a: in std_logic; y: out std_logic); end component;
begin u: {child} port map(a => a, y => y); end;
"""


LEAF = """library ieee; use ieee.std_logic_1164.all;
entity leaf is port(a: in std_logic; y: out std_logic); end;
architecture rtl of leaf is begin y <= not a; end;
"""


def test_nested_discovery_and_fresh_snapshots(tmp_path):
    (tmp_path / 'arbitrary-name.vhdl').write_text(LEAF)
    (tmp_path / 'middle.vhd').write_text(wrapper('middle', 'leaf'))
    top = tmp_path / 'top.vhd'
    source = wrapper('top', 'middle')
    deps = snapshot_dependencies([(top, source)])
    assert [Path(item['path']).name for item in deps] == ['arbitrary-name.vhdl', 'middle.vhd']
    (tmp_path / 'arbitrary-name.vhdl').write_text(LEAF + '\n-- changed')
    assert snapshot_dependencies([(top, source)]) != deps


def test_references_survive_save_as_and_resolve_external_files(tmp_path):
    external = tmp_path / 'components'
    external.mkdir()
    child = external / 'some file.vhd'
    child.write_text(LEAF)
    top = tmp_path / 'top.vhd'
    source = add_references(wrapper('top', 'leaf'), [child], top)
    assert references(source, top) == [child]
    destination = tmp_path / 'moved' / 'renamed.vhd'
    moved = rebase_references(source, top, destination)
    assert references(moved, destination) == [child]
    assert len(snapshot_dependencies([(destination, moved)])) == 1


def test_missing_ambiguous_and_circular_sources(tmp_path):
    top = tmp_path / 'top.vhd'
    source = wrapper('top', 'leaf')
    with pytest.raises(ValueError, match='Cannot find'):
        snapshot_dependencies([(top, source)])
    (tmp_path / 'one.vhd').write_text(LEAF)
    (tmp_path / 'two.vhd').write_text(LEAF)
    with pytest.raises(ValueError, match='Multiple sources'):
        snapshot_dependencies([(top, source)])
    explicit = add_references(source, [tmp_path / 'one.vhd'], top)
    assert len(snapshot_dependencies([(top, explicit)])) == 1
    (tmp_path / 'one.vhd').write_text(wrapper('leaf', 'top'))
    with pytest.raises(ValueError, match='Circular'):
        snapshot_dependencies([(top, explicit)])


@pytest.mark.integration
def test_multi_file_simulation_and_synthesis(tmp_path):
    pytest.importorskip('ghdl')
    (tmp_path / 'leaf.vhd').write_text(LEAF)
    (tmp_path / 'middle.vhd').write_text(wrapper('middle', 'leaf'))
    source = wrapper('top', 'middle')
    bench = """library ieee; use ieee.std_logic_1164.all;
entity top_tb is end;
architecture tb of top_tb is
signal a: std_logic := '0'; signal y: std_logic;
begin u: entity work.top port map(a,y);
process begin wait for 1 ns; assert y='1' severity failure;
a<='1'; wait for 1 ns; assert y='0' severity failure; wait; end process;
end;"""
    deps = snapshot_dependencies([(tmp_path / 'top.vhd', source), (tmp_path / 'tb.vhd', bench)])
    request = dict(kind='simulation', standard='VHDL 2008', entity='top', testbench='top_tb',
                   stop_time='3ns', wave_format='VCD', design=source, bench=bench, dependencies=deps)
    result = run_pipeline(request, tmp_path / 'sim', log=lambda _: None)
    assert result['signals'] > 0
    request['kind'] = 'circuit'
    result = run_pipeline(request, tmp_path / 'circuit', log=lambda _: None)
    assert result['cells'] > 0
    assert (tmp_path / 'circuit/dependency_000.vhd').read_text() == LEAF
