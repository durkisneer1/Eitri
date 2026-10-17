"""The worker log protocol must not depend on Windows' active code page."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('fail', [False, True])
def test_worker_logs_utf8_with_legacy_stdio(tmp_path, fail):
    (tmp_path / 'request.json').write_text('{}', encoding='utf-8')
    script = '''
import sys
from eitri.backend import pipeline

def run(request, directory, log):
    log('Synthesize VHDL \\u2192 Verilog')
    print('Diagnostic: \\u03bb', file=sys.stderr)
    if sys.argv[2] == 'fail':
        raise RuntimeError('Cannot process \\u03bb')
    return {'kind': 'circuit'}

pipeline.run_pipeline = run
pipeline.main()
'''
    env = dict(os.environ, PYTHONIOENCODING='cp1252', PYTHONUTF8='0')
    env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
    result = subprocess.run(
        [sys.executable, '-c', script, str(tmp_path), 'fail' if fail else 'success'],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=30,
    )
    output = result.stdout.decode('utf-8')
    assert result.returncode == int(fail), output
    assert 'Synthesize VHDL \u2192 Verilog' in output
    assert 'Diagnostic: \u03bb' in output
    if fail:
        assert 'ERROR: Cannot process \u03bb' in output
    else:
        assert json.loads((tmp_path / 'result.json').read_text()) == {'kind': 'circuit'}
