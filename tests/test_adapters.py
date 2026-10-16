import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
import yosys
import gtkwave
import netlistsvg


def test_yosys_keeps_arguments_out_of_shell():
    with patch('yosys.subprocess.run') as run:
        yosys.run(['-s', 'file with spaces;literal.ys'], cwd='/somewhere', timeout=12)
        args, kwargs = run.call_args
        assert args[0][-2:] == ['-s', 'file with spaces;literal.ys']
        assert not kwargs.get('shell', False)
        assert kwargs['cwd'] == '/somewhere'
        assert kwargs['timeout'] == 12
        assert kwargs['capture_output']


def test_yosys_rejects_shell_string():
    with pytest.raises(TypeError):
        yosys.run('read_verilog gate.v')


def test_missing_gtkwave_reports_configured_path(tmp_path, monkeypatch):
    monkeypatch.setenv('GTKWAVE_EXECUTABLE', str(tmp_path / 'missing-viewer'))
    assert not gtkwave.is_available()
    with pytest.raises(FileNotFoundError, match='does not exist'):
        gtkwave.executable()


def test_gtkwave_launch_returns_process_without_waiting(tmp_path):
    binary = tmp_path / 'viewer executable'
    wave = tmp_path / 'wave with spaces.vcd'
    binary.touch()
    wave.write_text('$enddefinitions $end\n')
    with patch('gtkwave.subprocess.Popen') as popen:
        process = gtkwave.launch(wave, executable_path=binary)
        assert process is popen.return_value
        assert popen.call_args.args[0] == [str(binary), str(wave)]
        popen.return_value.wait.assert_not_called()


def test_renderer_missing_payload_is_actionable(monkeypatch):
    monkeypatch.setattr(netlistsvg, 'is_available', lambda: False)
    with pytest.raises(RuntimeError, match='payload missing'):
        netlistsvg.render('netlist.json', 'out.svg')


def test_renderer_propagates_engine_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(netlistsvg, 'is_available', lambda: True)
    source = tmp_path / 'netlist.json'
    source.write_text('{}')
    with patch('netlistsvg.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'node')):
        with pytest.raises(subprocess.CalledProcessError):
            netlistsvg.render(source, tmp_path / 'output.svg')
