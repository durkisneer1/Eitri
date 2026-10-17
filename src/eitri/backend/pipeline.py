"""Run immutable editor snapshots through the packaged HDL tools.

Executed in a separate process by jobs.py, never on Qt's GUI thread. All build
files use fixed local names in a unique run directory; user text is not a shell
command or interpolated into a Yosys script.
"""
import json
from pathlib import Path
import re
import subprocess

STANDARDS = {'VHDL 2008': '08', 'VHDL 2002': '02', 'VHDL 1993': '93'}
IDENTIFIER = re.compile(r'[A-Za-z](?:[A-Za-z0-9]|_(?=[A-Za-z0-9]))*\Z')
DURATION = re.compile(r'[1-9][0-9]*(?:fs|ps|ns|us|ms|sec)\Z', re.I)


def validate(request):
    """Validate settings before starting tools, with messages suitable for the UI."""
    if request['kind'] not in ('simulation', 'circuit'):
        raise ValueError('Unknown job type.')
    if request.get('circuit_detail', 'Detailed') not in ('Simple', 'Detailed'):
        raise ValueError('Choose Simple or Detailed circuit generation.')
    if request['standard'] not in STANDARDS:
        raise ValueError('Choose a supported VHDL standard.')
    name = request['testbench'] if request['kind'] == 'simulation' else request['entity']
    if not IDENTIFIER.fullmatch(name):
        raise ValueError('Enter a basic VHDL entity name (letters, digits and single underscores).')
    if not request['design'].strip():
        raise ValueError('The Design tab is empty.')
    if request['kind'] == 'simulation':
        if not request['bench'].strip():
            raise ValueError('The Testbench tab is empty.')
        if not DURATION.fullmatch(request['stop_time']):
            raise ValueError('Stop time must be a positive integer and unit, for example 200ns or 1us.')
        if request['wave_format'] not in ('VCD', 'GHW'):
            raise ValueError('Choose VCD or GHW output.')


def run_pipeline(request, directory, log=print):
    """Return artifact metadata; raise on failed analysis, simulation or synthesis."""
    import ghdl
    import yosys
    import netlistsvg
    from .vcd import parse_vcd
    from .schematic import display_netlist, inline_svg_styles
    from .schematic_theme import write_skin, color_schematic

    validate(request)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'design.vhd').write_text(request['design'], encoding='utf-8')
    # Fixed snapshot filenames avoid path quoting issues in every native tool.
    dependencies = []
    for index, dependency in enumerate(request.get('dependencies', [])):
        filename = f'dependency_{index:03d}.vhd'
        (directory / filename).write_text(dependency['source'], encoding='utf-8')
        dependencies.append(filename)
        log(f'{filename} = {dependency["path"]}')
    standard = '--std=' + STANDARDS[request['standard']]

    def invoke(title, function, *args, **kwargs):
        log('\n=== ' + title + ' ===')
        result = function(*args, **kwargs)
        if hasattr(result, 'stdout') and result.stdout:
            log(result.stdout)
        if hasattr(result, 'stderr') and result.stderr:
            log(result.stderr)
        return result

    if request['kind'] == 'simulation':
        (directory / 'testbench.vhd').write_text(request['bench'], encoding='utf-8')
        invoke('Analyze Design + Testbench', ghdl.run,
               ['-a', standard, *dependencies, 'design.vhd', 'testbench.vhd'],
               cwd=directory, capture_output=True, timeout=60)
        # Explicit elaboration works with executable-producing GHDL backends too.
        invoke('Elaborate ' + request['testbench'], ghdl.run,
               ['-e', standard, request['testbench']],
               cwd=directory, capture_output=True, timeout=60)
        args = ['-r', standard, request['testbench'], '--assert-level=error',
                '--stop-time=' + request['stop_time'].lower(), '--vcd=wave.vcd']
        # VCD powers the built-in viewer; optionally write GHW at the same time.
        if request['wave_format'] == 'GHW':
            args.append('--wave=wave.ghw')
        invoke('Simulate to ' + request['stop_time'], ghdl.run, args,
               cwd=directory, capture_output=True, timeout=120)
        log('\n=== Read waveforms ===')
        waveform = parse_vcd(directory / 'wave.vcd')
        (directory / 'waveform.json').write_text(json.dumps(waveform), encoding='utf-8')
        return {'kind': 'simulation', 'waveform': 'waveform.json',
                'wave_file': 'wave.ghw' if request['wave_format'] == 'GHW' else 'wave.vcd',
                'signals': len(waveform['signals']), 'end_time': waveform['end_time'],
                'timescale': waveform['timescale']}

    # GHDL lowers VHDL to Verilog before the portable YoWASP Yosys backend runs.
    log('\n=== Synthesize VHDL → Verilog ===')
    lowered = ghdl.run(['--synth', standard, '--out=verilog', *dependencies, 'design.vhd', '-e', request['entity']],
                       cwd=directory, capture_output=True, timeout=120)
    if lowered.stderr:
        log(lowered.stderr)
    (directory / 'design.v').write_text(lowered.stdout, encoding='utf-8')
    # -auto-top avoids case differences between VHDL names and emitted Verilog.
    # memory_map makes ROM logic explicit for netlistsvg's generic cell renderer.
    detail = request.get('circuit_detail', 'Detailed')
    passes = ('proc; memory_map; clean; ' if detail == 'Simple'
              else 'proc; flatten -noscopeinfo; opt; memory_map; opt; clean; ')
    script = ('read_verilog design.v; hierarchy -check -auto-top; '
              + passes + 'stat; write_json netlist.json')
    invoke('Build Yosys netlist', yosys.run_script, script, cwd=directory, timeout=180)
    log('\n=== Render schematic ===')
    netlist = json.loads((directory / 'netlist.json').read_text())
    modules = netlist['modules']
    top = next((name for name, module in modules.items()
                if str(module.get('attributes', {}).get('top', '')).endswith('1')), next(iter(modules)))
    display = display_netlist(netlist, top=top)
    (directory / 'schematic.json').write_text(json.dumps(display), encoding='utf-8')
    write_skin(directory / 'skin.svg', display)
    netlistsvg.render(directory / 'schematic.json', directory / 'schematic.svg', skin=directory / 'skin.svg', timeout=90)
    inline_svg_styles(directory / 'schematic.svg')
    color_schematic(directory / 'schematic.svg')
    module = modules[top]
    return {'kind': 'circuit', 'svg': 'schematic.svg', 'top': top,
            'detail': detail, 'cells': len(display['modules'][top].get('cells', {})), 'ports': len(module.get('ports', {}))}


def main():
    import sys
    # JobRunner reads run.log as UTF-8. Redirected Windows streams otherwise
    # use the system code page, which cannot encode our Unicode progress text.
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    directory = Path(sys.argv[1]).resolve()
    request = json.loads((directory / 'request.json').read_text(encoding='utf-8'))
    try:
        result = run_pipeline(request, directory, lambda text: print(text, flush=True))
        (directory / 'result.json').write_text(json.dumps(result), encoding='utf-8')
        print('\nCompleted successfully.', flush=True)
    except Exception as error:
        if isinstance(error, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
            for output in (error.stdout, error.stderr):
                if output:
                    print(output.decode(errors='replace') if isinstance(output, bytes) else output, flush=True)
        print(f'\nERROR: {error}', flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
