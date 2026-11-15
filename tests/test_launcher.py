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
    run.assert_called_once_with(folder=None)
    spawn.assert_not_called()


def test_launch_failure_is_actionable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(launcher, 'log_path', lambda: tmp_path / 'eitri.log')
    monkeypatch.setattr(subprocess, 'Popen', Mock(side_effect=OSError('cannot spawn')))
    with pytest.raises(SystemExit) as error:
        launcher.main([])
    assert error.value.code == 1
    assert 'eitri --foreground' in capsys.readouterr().err


@pytest.mark.parametrize('argument', ['.', 'project with spaces', '~'])
def test_folder_is_resolved_before_detaching(tmp_path, monkeypatch, argument):
    from pathlib import Path
    folder = Path.home() if argument == '~' else tmp_path / 'project with spaces'
    if argument != '~':
        folder.mkdir()
    monkeypatch.chdir(folder if argument == '.' else tmp_path)
    monkeypatch.setattr(launcher, 'log_path', lambda: tmp_path / 'eitri.log')
    spawn = Mock()
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    launcher.main([argument])
    assert spawn.call_args.args[0] == [sys.executable, '-m', 'eitri', '--foreground', str(folder)]


@pytest.mark.parametrize('is_file', [False, True])
def test_invalid_folder_fails_before_spawning(tmp_path, monkeypatch, capsys, is_file):
    path = tmp_path / 'not-a-folder'
    if is_file:
        path.write_text('entity example is end;')
    spawn = Mock()
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    with pytest.raises(SystemExit) as error:
        launcher.main([str(path)])
    assert error.value.code == 2
    assert 'Not a directory' in capsys.readouterr().err
    spawn.assert_not_called()


def test_foreground_receives_folder(tmp_path, monkeypatch):
    from eitri.ui import window
    run = Mock()
    monkeypatch.setattr(window, 'main', run)
    launcher.main(['--foreground', str(tmp_path)])
    run.assert_called_once_with(folder=tmp_path)


@pytest.mark.parametrize('with_folder', [False, True])
def test_workspace_startup_opens_only_explicit_folder(tmp_path, monkeypatch, with_folder):
    from eitri.ui import window
    app = Mock()
    app.exec.return_value = 0
    monkeypatch.setattr(window, 'QApplication', Mock(instance=Mock(return_value=app)))
    workspace = Mock()
    monkeypatch.setattr(window, 'Workspace', Mock(return_value=workspace))
    with pytest.raises(SystemExit) as error:
        window.main(folder=tmp_path if with_folder else None)
    assert error.value.code == 0
    workspace.show.assert_called_once_with()
    if with_folder:
        workspace.open_folder.assert_called_once_with(tmp_path)
    else:
        workspace.open_folder.assert_not_called()
