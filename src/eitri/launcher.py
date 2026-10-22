"""Launch the desktop workspace without occupying the invoking terminal."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def log_path():
    if sys.platform == 'darwin':
        root = Path.home() / 'Library' / 'Logs'
    elif sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        root = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local' / 'state'))
    return root / 'Eitri' / 'eitri.log'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Open the Eitri VHDL workspace.')
    parser.add_argument('--foreground', action='store_true',
                        help='keep the app attached to this terminal for debugging')
    args = parser.parse_args(argv)
    if args.foreground:
        from .ui.window import main as run_workspace
        run_workspace()
        return

    path = log_path()
    options = {'start_new_session': True}
    if sys.platform == 'win32':
        options = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('ab') as log:
            subprocess.Popen(
                [sys.executable, '-m', 'eitri', '--foreground'],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                close_fds=True, **options,
            )
    except OSError as error:
        parser.exit(1, f'Could not launch Eitri: {error}\nTry eitri --foreground.\n')
