"""The CLI detaches once, preserving its interpreter and diagnostic output."""
import subprocess
import sys
from unittest.mock import Mock

import pytest
from eitri import launcher


@pytest.mark.parametrize('platform', ['darwin', 'linux', 'win32'])
def test_background_launch(tmp_path, monkeypatch, platform):
    monkeypatch.setattr(launcher.sys, 'platform', platform)
    monkeypatch.setattr(launcher, 'log_path', lambda: tmp_path / 'logs' / 'eitri.log')
    monkeypatch.setattr(subprocess, 'DETACHED_PROCESS', 8, raising=False)
    monkeypatch.setattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 512, raising=False)
    spawn = Mock()
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    launcher.main([])
    args, kwargs = spawn.call_args
    assert args[0] == [sys.executable, '-m', 'eitri', '--foreground']
    assert kwargs['stdin'] == subprocess.DEVNULL
    assert kwargs['stdout'] is kwargs['stderr']
    assert kwargs['stdout'].closed
    assert kwargs['close_fds']
    assert (tmp_path / 'logs' / 'eitri.log').exists()
    if platform == 'win32':
        assert kwargs['creationflags'] == 520
        assert 'start_new_session' not in kwargs
    else:
        assert kwargs['start_new_session']


def test_foreground_does_not_respawn(monkeypatch):
    from eitri.ui import window
    run = Mock()
    monkeypatch.setattr(window, 'main', run)
    spawn = Mock()
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    launcher.main(['--foreground'])
    run.assert_called_once_with()
    spawn.assert_not_called()


def test_launch_failure_is_actionable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launcher, 'log_path', lambda: tmp_path / 'eitri.log')
    monkeypatch.setattr(subprocess, 'Popen', Mock(side_effect=OSError('cannot spawn')))
    with pytest.raises(SystemExit) as error:
        launcher.main([])
    assert error.value.code == 1
    assert 'eitri --foreground' in capsys.readouterr().err
