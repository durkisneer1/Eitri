"""Read digital VCD signals without a GUI or third-party parser.

Preserve hierarchical aliases and VHDL logic states. Bounded previews keep very large
simulations from exhausting the UI; the complete VCD remains exportable.
"""
from bisect import bisect_right
import re

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_EVENTS = 150_000
MAX_SIGNALS = 512


def parse_vcd(path, stop_time=None):
    if path.stat().st_size > MAX_FILE_BYTES:
        return {'signals': [], 'end_time': 0, 'timescale': '1 fs',
                'warning': 'VCD exceeds the 64 MB preview limit. Export it or open it in GTKWave.'}
    scope, signals, ids = [], [], {}
    timescale, timestamp, end_time, count = '1 fs', 0, 0, 0
    warning = ''
    directive = ''
    with path.open(encoding='utf-8', errors='replace') as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            # Header directives may span multiple lines; dumpvars starts data.
            if directive or (line.startswith('$') and not line.startswith(('$dump', '$end'))):
                directive += ' ' + line
                if '$end' not in directive:
                    continue
                tokens = directive.split()
                if tokens[0] == '$scope':
                    scope.append(tokens[2])
                elif tokens[0] == '$upscope' and scope:
                    scope.pop()
                elif tokens[0] == '$timescale':
                    timescale = ' '.join(tokens[1:-1])
                elif tokens[0] == '$var':
                    if len(signals) >= MAX_SIGNALS:
                        warning = 'Preview limited to 512 signals; full data is available in the waveform file.'
                    elif tokens[1] in ('real', 'realtime', 'string'):
                        warning = 'Real/string signals are omitted from the digital preview; use GTKWave for those signals.'
                    else:
                        code = tokens[3]
                        events = ids.setdefault(code, [])
                        signals.append({'name': '.'.join(scope + [''.join(tokens[4:-1])]),
                                        'width': int(tokens[2]), 'events': events})
                directive = ''
                continue
            if line.startswith('#'):
                timestamp = int(line[1:])
                end_time = timestamp
            elif line.startswith('$'):
                continue
            else:
                if line[0] in 'bB':
                    parts = line[1:].split()
                    if len(parts) != 2:
                        continue
                    value, code = parts
                elif line[0] in '01uUxXzZwWlLhH-':
                    value, code = line[0], line[1:]
                else:
                    continue
                if code not in ids:
                    continue
                if count >= MAX_EVENTS:
                    warning = 'Preview truncated after 150,000 changes; full data is available in the waveform file.'
                    break
                value = value.upper()
                events = ids[code]
                if events and events[-1][0] == timestamp:
                    events[-1] = [timestamp, value]
                elif not events or events[-1][1] != value:
                    events.append([timestamp, value])
                    count += 1
    data = {'signals': signals, 'end_time': end_time, 'timescale': timescale, 'warning': warning}
    # A quiet final wait need not produce a VCD timestamp. Extend the preview,
    # not the event data or exported VCD, to the user's requested boundary.
    # Never carry values across changes omitted by the event limit.
    if stop_time is not None and not warning.startswith('Preview truncated'):
        units = {'fs': 1, 'ps': 10**3, 'ns': 10**6, 'us': 10**9,
                 'ms': 10**12, 's': 10**15, 'sec': 10**15}
        def duration(value):
            match = re.fullmatch(r'\s*(\d+)\s*(fs|ps|ns|us|ms|s|sec)\s*', value, re.I)
            if not match:
                raise ValueError(f'Invalid waveform duration: {value}')
            return int(match[1]) * units[match[2].lower()]
        ticks, remainder = divmod(duration(stop_time), duration(timescale))
        requested_end = ticks + remainder / duration(timescale) if remainder else ticks
        data['recorded_end_time'] = end_time
        data['end_time'] = max(end_time, requested_end)
    return data


def value_at(signal, timestamp):
    events = signal['events']
    index = bisect_right(events, timestamp, key=lambda event: event[0]) - 1
    return events[index][1] if index >= 0 else 'X'


def format_value(value, width, radix='Hex'):
    # Only binary digits have a numeric representation. Keep std_logic
    # states (including U, W, L, H and -) visible in every radix.
    value = value.upper()
    if not value or any(bit not in '01' for bit in value):
        return value if width == 1 else (value[0] if len(set(value)) == 1 else value)
    number = int(value, 2)
    if radix == 'Binary' or width == 1:
        return value.zfill(width)
    if radix == 'Unsigned':
        return str(number)
    return f'{number:0{(width + 3) // 4}X}'


def time_label(ticks, timescale):
    match = re.fullmatch(r'\s*(\d+)\s*(fs|ps|ns|us|ms|s|sec)\s*', timescale)
    if not match:
        return f'{ticks:g} ticks'
    units = {'fs': 1e-15, 'ps': 1e-12, 'ns': 1e-9, 'us': 1e-6, 'ms': 1e-3, 's': 1, 'sec': 1}
    seconds = ticks * int(match[1]) * units[match[2]]
    for unit in ('s', 'ms', 'us', 'ns', 'ps', 'fs'):
        if seconds >= units[unit] * 0.999 or unit == 'fs':
            return f'{seconds / units[unit]:.4g} {unit}'
