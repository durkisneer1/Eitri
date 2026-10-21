"""CPU-scale folder discovery, snapshots, caching and selective circuit expansion."""
from dataclasses import replace
from pathlib import Path
import json
import shutil
import pytest
from eitri.backend.project import Project, Target
from eitri.backend.pipeline import run_pipeline

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'learning_cpu'


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'cpu'
    shutil.copytree(EXAMPLE, root)
    return Project(root)


def test_recursive_index_and_cpu_dependency_order(project):
    target = next(t for t in project.targets('simulation') if t.entity == 'cpu_tb')
    sources = project.ordered_sources(target)
    names = [Path(s['path']).name for s in sources]
    assert names.index('cpu_types.vhd') < names.index('alu.vhd') < names.index('cpu.vhd')
    assert names.index('adder.vhd') < names.index('alu.vhd')
    assert names[-1] == 'cpu_tb.vhd'
    assert 'alu_tb.vhd' not in names
    _, cpu = project.resolve('cpu')
    assert [i.name for i in cpu.instances] == ['u_program', 'u_datapath']
    _, alu = project.resolve('alu')
    assert alu.instances[0].architecture == 'rtl'
    assert 'result => sum' in alu.instances[0].associations


def test_unsaved_component_overlay_and_snapshot_are_independent(project):
    leaf = str(project.root / 'rtl/alu/adder.vhd')
    original = project.sources[leaf]
    project.refresh({leaf: original.replace('unsigned(a) + unsigned(b)', 'unsigned(a) - unsigned(b)')})
    target = next(t for t in project.targets('simulation') if t.entity == 'cpu_tb')
    snapshot = project.snapshot(target)
    assert '- unsigned(b)' in snapshot['sources'][0]['source']
    assert Path(leaf).read_text() == original
    project.refresh({leaf: original})
    assert '- unsigned(b)' in snapshot['sources'][0]['source']


def test_saved_targets_and_excluded_artifacts(project):
    target = replace(project.targets('simulation')[0], name='Adder smoke', stop_time='10ns', generics={})
    project.save_target(target)
    generated = project.root / 'runs/run1'
    generated.mkdir(parents=True)
    (generated / 'duplicate.vhd').write_text('entity adder is end;')
    reopened = Project(project.root)
    assert reopened.targets('simulation')[0].name == 'Adder smoke'
    assert reopened.targets('simulation')[0].stop_time == '10ns'
    assert not reopened.issues


def test_ambiguity_cycle_and_missing_package_are_explicit(tmp_path):
    (tmp_path / 'a.vhd').write_text('entity a is end; architecture x of a is begin end; architecture y of a is begin end;')
    p = Project(tmp_path)
    with pytest.raises(ValueError, match='select an architecture'):
        p.resolve('a')
    assert p.resolve('a', architecture='y')[1].name == 'y'
    (tmp_path / 'a.vhd').write_text('entity a is end; architecture x of a is begin u: entity work.b; end;')
    (tmp_path / 'b.vhd').write_text('entity b is end; architecture x of b is begin u: entity work.a; end;')
    p.refresh()
    with pytest.raises(ValueError, match='Circular'):
        p.ordered_sources(p.targets('simulation')[0])
    (tmp_path / 'b.vhd').write_text('use work.missing.all; entity b is end; architecture x of b is begin end;')
    p.refresh()
    with pytest.raises(ValueError, match='missing package'):
        p.ordered_sources(p.targets('simulation')[0])


def test_unrelated_incomplete_file_does_not_block_target(project):
    (project.root / 'unfinished.vhd').write_text('use work.todo.all; entity unfinished is end;')
    project.refresh()
    target = next(t for t in project.targets('simulation') if t.entity == 'adder_tb')
    assert len(project.ordered_sources(target)) == 2


@pytest.mark.integration
def test_cpu_simulation_incremental_cache_and_unsaved_failure(project, tmp_path):
    pytest.importorskip('ghdl')
    target = next(t for t in project.targets('simulation') if t.entity == 'cpu_tb')
    request = project.snapshot(target, cache_root=str(tmp_path / 'cache'))
    first = run_pipeline(request, tmp_path / 'first', log=lambda _: None)
    assert first['signals'] > 20
    logs = []
    run_pipeline(request, tmp_path / 'second', log=logs.append)
    assert any('analyzed 0.' in log for log in logs)
    assert json.loads((tmp_path / 'second/sources.json').read_text())['source_0000.vhd'].endswith('adder.vhd')
    leaf = str(project.root / 'rtl/alu/adder.vhd')
    project.refresh({leaf: project.sources[leaf].replace('unsigned(a) + unsigned(b)', 'unsigned(a) - unsigned(b)')})
    logs = []
    with pytest.raises(RuntimeError, match='Simulate'):
        run_pipeline(project.snapshot(target, cache_root=str(tmp_path / 'cache')), tmp_path / 'broken', log=logs.append)
    assert any(str(project.root / 'tb/cpu_tb.vhd') + ':' in log and 'CPU program should compute' in log for log in logs)


@pytest.mark.integration
def test_selective_circuit_expansion_preserves_sibling(project, tmp_path):
    pytest.importorskip('ghdl')
    target = next(t for t in project.targets('circuit') if t.entity == 'cpu')
    simple = run_pipeline(project.snapshot(target), tmp_path / 'simple', log=lambda _: None)
    assert set(simple['components']) == {'u_datapath', 'u_program'}
    expanded = run_pipeline(project.snapshot(target, expand_instances=['u_datapath']), tmp_path / 'expanded', log=lambda _: None)
    assert expanded['components'] == ['u_program']
    assert expanded['cells'] > simple['cells']
    assert (tmp_path / 'expanded/schematic.svg').is_file()


@pytest.mark.integration
def test_package_bodies_and_named_libraries(tmp_path):
    pytest.importorskip('ghdl')
    (tmp_path / '.eitri.json').write_text(json.dumps({'libraries': {'common': ['math*.vhd']}}))
    (tmp_path / 'math.vhd').write_text('package math is function answer return integer; end;')
    (tmp_path / 'math_body.vhd').write_text('package body math is function answer return integer is begin return 42; end; end;')
    (tmp_path / 'top.vhd').write_text('library common; use common.math.all; entity top is end; architecture test of top is begin process begin assert answer = 42 severity failure; wait; end process; end;')
    p = Project(tmp_path)
    target = p.targets('simulation')[0]
    sources = p.ordered_sources(target)
    assert [Path(s['path']).name for s in sources][:2] == ['math.vhd', 'math_body.vhd']
    assert run_pipeline(p.snapshot(target), tmp_path / 'runs/test', log=lambda _: None)['kind'] == 'simulation'
