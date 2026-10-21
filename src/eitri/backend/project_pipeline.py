"""Immutable project snapshots with a private, incrementally analyzed cache."""
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import tempfile

from .pipeline import STANDARDS, IDENTIFIER, DURATION, render_circuit
from .vcd import parse_vcd


def validate_project_request(request):
    if not request['sources']:
        raise ValueError('This target has no source files.')
    target = request['target']
    for name in [target['entity'], target.get('library', 'work'), *([target['architecture']] if target.get('architecture') else [])]:
        if not IDENTIFIER.fullmatch(name):
            raise ValueError(f'Invalid VHDL target name: {name}')
    for key, value in target.get('generics', {}).items():
        if not IDENTIFIER.fullmatch(key) or not isinstance(value, (str, int, float, bool)):
            raise ValueError('Generic overrides must map VHDL names to scalar values.')
    for source in request['sources']:
        if not IDENTIFIER.fullmatch(source.get('library', 'work')):
            raise ValueError('Invalid library name.')
    if request['kind'] == 'simulation':
        if not DURATION.fullmatch(request['stop_time']):
            raise ValueError('Stop time must be positive, e.g. 200ns or 1us.')
        if request['wave_format'] not in ('VCD', 'GHW'):
            raise ValueError('Choose VCD or GHW.')


@contextmanager
def analysis_directory(request, directory):
    try:
        version = importlib.metadata.version('ghdl-bundled')
    except importlib.metadata.PackageNotFoundError:
        version = 'bundled'
    identity = [3, version, request['project_root'], request['standard'], request['kind'], {k: request['target'].get(k) for k in ('entity', 'library', 'architecture')},
                [(s['path'], s.get('library', 'work')) for s in request['sources']]]
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    root = Path(request.get('cache_root', directory.parent / 'analysis-cache')) / key
    root.mkdir(parents=True, exist_ok=True)
    lock = root / 'busy'
    try:
        lock.mkdir()
    except FileExistsError:
        # Concurrent runs never mutate the same compiler library. A stale lock
        # after a killed worker also safely falls back to an isolated analysis.
        with tempfile.TemporaryDirectory(prefix='eitri-analysis-') as temporary:
            yield Path(temporary)
    else:
        try:
            yield root
        finally:
            lock.rmdir()


def run_project_pipeline(request, directory, log=print):
    import ghdl
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = request['target']
    mapping = {}
    fingerprints = []
    for index, source in enumerate(request['sources']):
        name = f'source_{index:04d}.vhd'
        (directory / name).write_text(source['source'], encoding='utf-8')
        mapping[name] = source['path']
        fingerprints.append(hashlib.sha256(source['source'].encode()).hexdigest())
    (directory / 'sources.json').write_text(json.dumps(mapping, indent=2))
    def invoke(title, args, cwd):
        log('\n=== ' + title + ' ===')
        result = ghdl.run(args, cwd=cwd, capture_output=True, timeout=120, check=False)
        for text in (result.stdout, result.stderr):
            if text:
                for name, path in mapping.items():
                    text = text.replace(name + ':', path + ':')
                log(text)
        if result.returncode:
            # Output has already been mapped to original editable file paths.
            raise RuntimeError(f'{title} failed. See diagnostics above.')
        return result
    with analysis_directory(request, directory) as cache:
        manifest = cache / 'analyzed.json'
        try:
            previous = json.loads(manifest.read_text())
        except (OSError, ValueError):
            previous = []
        # Only mark successful analysis reusable, including after interruption.
        if manifest.exists():
            manifest.unlink()
        standard = '--std=' + STANDARDS[request['standard']]
        dirty = False
        reused = 0
        for index, source in enumerate(request['sources']):
            name = f'source_{index:04d}.vhd'
            dirty = dirty or index >= len(previous) or previous[index] != fingerprints[index] or not (cache / name).exists()
            if dirty:
                (cache / name).write_text(source['source'], encoding='utf-8')
                invoke('Analyze ' + Path(source['path']).name,
                       ['-a', standard, '--work=' + source.get('library', 'work'), name], cache)
            else:
                reused += 1
        manifest.write_text(json.dumps(fingerprints))
        log(f'Reused {reused} unchanged analyzed source(s); analyzed {len(fingerprints) - reused}.')
        options = [standard, '--work=' + target.get('library', 'work')]
        top = [target['entity']] + ([target['architecture']] if target.get('architecture') else [])
        generics = [f'-g{name}={str(value).lower() if isinstance(value, bool) else value}' for name, value in target.get('generics', {}).items()]
        if request['kind'] == 'simulation':
            invoke('Elaborate ' + target['entity'], ['-e', *options, *top], cache)
            wave = directory / 'wave.vcd'
            args = ['-r', *options, *top, *generics, '--assert-level=error',
                    '--stop-time=' + request['stop_time'].lower(), '--vcd=' + str(wave)]
            if request['wave_format'] == 'GHW':
                args.append('--wave=' + str(directory / 'wave.ghw'))
            invoke('Simulate ' + target['name'], args, cache)
            waveform = parse_vcd(wave)
            (directory / 'waveform.json').write_text(json.dumps(waveform))
            return {'kind': 'simulation', 'waveform': 'waveform.json', 'target_name': target['name'],
                    'wave_file': 'wave.ghw' if request['wave_format'] == 'GHW' else 'wave.vcd',
                    'signals': len(waveform['signals']), 'end_time': waveform['end_time'],
                    'timescale': waveform['timescale']}
        lowered = invoke('Synthesize ' + target['entity'], ['--synth', *options, '--out=verilog', *generics, *top], cache)
        (directory / 'design.v').write_text(lowered.stdout)
    return {**render_circuit(request, directory, log), 'target_name': target['name']}
