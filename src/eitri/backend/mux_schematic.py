"""Recognize decoded muxes and draw their equivalent binary-selector circuit.

These transformations apply only to the schematic copy. The compiler netlist
is preserved. Recognition proves the decoder truth table for every binary
selector value, rather than relying on VHDL names or compiler-generated names.
"""


def _decoded_mux(cell, drivers):
    if cell['type'] != '$pmux':
        return None
    cone, leaves, visiting = set(), set(), set()

    def collect(bit):
        if isinstance(bit, str):
            if bit not in ('0', '1'):
                raise ValueError
            return
        if bit in drivers and drivers[bit] is None:
            raise ValueError  # Multiple drivers: never infer a decoder truth table.
        driver = drivers.get(bit)
        if driver is None or driver[1]['type'] not in ('$eq', '$logic_not', '$not'):
            leaves.add(bit)
            if len(leaves) > 4:
                raise ValueError
            return
        name, gate = driver
        if name in cone:
            return
        if name in visiting or len(cone) > 64:
            raise ValueError
        visiting.add(name)
        for port in ('A', 'B'):
            for wire in gate['connections'].get(port, []):
                collect(wire)
        visiting.remove(name)
        cone.add(name)

    try:
        for bit in cell['connections']['S']:
            collect(bit)
        selector = sorted(leaves)
        if not selector:
            return None

        def evaluate(bit, values):
            if isinstance(bit, str):
                return int(bit)
            if bit in values:
                return values[bit]
            _, gate = drivers[bit]
            inputs = gate['connections']
            a = [evaluate(b, values) for b in inputs['A']]
            if gate['type'] == '$logic_not':
                result = int(not any(a))
            elif gate['type'] == '$not':
                if len(a) != 1:
                    raise ValueError
                result = 1 - a[0]
            else:
                b = [evaluate(b, values) for b in inputs['B']]
                # Conservatively reject unequal widths/sign extension.
                if len(a) != len(b):
                    raise ValueError
                result = int(a == b)
            values[bit] = result
            return result

        data = []
        ports = cell['connections']
        width = len(ports['Y'])
        for number in range(1 << len(selector)):
            values = {bit: (number >> i) & 1 for i, bit in enumerate(selector)}
            active = [i for i, bit in enumerate(ports['S']) if evaluate(bit, values)]
            # No guesses for incomplete or overlapping decoders.
            if len(active) != 1:
                return None
            start = active[0] * width
            branch = ports['B'][start:start + width]
            if len(branch) != width:
                return None
            data.append(branch)
        return selector, data, cone
    except (ValueError, KeyError, RecursionError):
        return None


def mux_schematic(module, detailed=False):
    cells = module.setdefault('cells', {})
    drivers = {}
    for name, cell in cells.items():
        for port, direction in cell.get('port_directions', {}).items():
            if direction not in ('output', 'inout'):
                continue
            bits = cell['connections'][port]
            for bit in bits:
                if isinstance(bit, int):
                    driver = (name, cell) if direction == 'output' and len(bits) == 1 else None
                    drivers[bit] = None if bit in drivers else driver
    candidates = set()
    for name, cell in list(cells.items()):
        decoded = _decoded_mux(cell, drivers)
        if decoded is None:
            if cell['type'] != '$mux':
                continue
            ports = cell['connections']
            if len(ports['S']) != 1:
                continue
            decoded = ports['S'], [ports['A'], ports['B']], set()
        selector, data, cone = decoded
        candidates.update(cone)
        width = len(cell['connections']['Y'])
        connections = {f'D{i}': bits for i, bits in enumerate(data)}
        connections.update(S=selector, Y=cell['connections']['Y'])
        cells[name] = dict(type=f'eitri_mux_{len(data)}_{width}', hide_name=1,
                           attributes={'mux_inputs': len(data), 'mux_width': width},
                           parameters={}, connections=connections,
                           port_directions={p: 'output' if p == 'Y' else 'input' for p in connections})

    # Keep shared decoder gates when another cell or output still needs them.
    used = {b for port in module.get('ports', {}).values() for b in port['bits']}
    used.update(b for name, cell in cells.items() if name not in candidates
                for port, direction in cell.get('port_directions', {}).items() if direction == 'input'
                for b in cell['connections'][port])
    retained = set()
    while True:
        needed = {name for name in candidates - retained
                  if any(b in used for b in cells[name]['connections']['Y'])}
        if not needed:
            break
        retained.update(needed)
        used.update(b for name in needed for p in ('A', 'B')
                    for b in cells[name]['connections'].get(p, []))
    removed = set()
    for name in candidates - retained:
        removed.update(cells.pop(name)['connections']['Y'])
    module['netnames'] = {name: net for name, net in module.get('netnames', {}).items()
                          if not any(b in removed for b in net['bits'])}
    if detailed:
        _expand(module)


def _expand(module):
    cells = module['cells']
    aliases = {}
    vectors = [p['bits'] for p in module.get('ports', {}).values()]
    vectors += [p['bits'] for p in module.get('netnames', {}).values()]
    vectors += [bits for c in cells.values() for bits in c['connections'].values()]
    next_bit = max((b for bits in vectors for b in bits if isinstance(b, int)), default=1) + 1

    def gate(kind, a, b=None, output=None):
        nonlocal next_bit
        if output is None:
            output = list(range(next_bit, next_bit + len(a)))
            next_bit += len(a)
        connections = dict(A=a, Y=output)
        if b is not None:
            connections['B'] = b
        name = f'Eitri_gate_{next_bit}_{len(cells)}'
        while name in cells:
            name += '_'
        width = len(output)
        attributes = {'gate_type': kind, 'gate_width': width}
        cell_type = f'eitri_{kind[1:]}_{width}' if width > 1 else kind
        cells[name] = dict(type=cell_type, hide_name=1, attributes=attributes, parameters={},
                           port_directions={p: 'output' if p == 'Y' else 'input' for p in connections},
                           connections=connections)
        return output

    for name, cell in list(cells.items()):
        if 'mux_inputs' not in cell.get('attributes', {}) or 'component_type' in cell.get('attributes', {}):
            continue
        ports = cell['connections']
        selector = ports['S']
        count = cell['attributes']['mux_inputs']
        # Identical branches are wires; repeated bit functions need only one
        # gate. In a sign extender the low word bypasses the mux entirely.
        columns = {}
        for index, output in enumerate(ports['Y']):
            column = tuple(ports[f'D{i}'][index] for i in range(count))
            if len(set(column)) == 1:
                if output != column[0]:
                    aliases[output] = column[0]
            elif column in columns:
                aliases[output] = columns[column]
            else:
                columns[column] = output
        if not columns:
            del cells[name]
            continue
        ports = {f'D{i}': [column[i] for column in columns] for i in range(count)} | {'Y': list(columns.values())}
        if len(selector) == 1 and all(bit == '0' for bit in ports['D0']):
            gate('$and', ports['D1'], selector, ports['Y'])
            del cells[name]
            continue
        if len(selector) == 1 and all(bit == '0' for bit in ports['D1']):
            gate('$and', ports['D0'], gate('$not', selector), ports['Y'])
            del cells[name]
            continue
        inverted = [gate('$not', [bit]) for bit in selector]
        terms = []
        for i in range(cell['attributes']['mux_inputs']):
            literals = [[bit] if i & (1 << j) else inverted[j] for j, bit in enumerate(selector)]
            enable = literals[0]
            for literal in literals[1:]:
                enable = gate('$and', enable, literal)
            data = ports[f'D{i}']
            # A scalar enable controls every bit of this bus-wide AND symbol.
            terms.append(gate('$and', data, enable))
        result = terms[0]
        for i, term in enumerate(terms[1:], 1):
            result = gate('$or', result, term, ports['Y'] if i == len(terms) - 1 else None)
        del cells[name]

    def resolve(bit):
        seen = set()
        while bit in aliases and bit not in seen:
            seen.add(bit)
            bit = aliases[bit]
        return bit

    for vector in [p['bits'] for p in module.get('ports', {}).values()] + [
            n['bits'] for n in module.get('netnames', {}).values()] + [
            bits for c in cells.values() for bits in c['connections'].values()]:
        vector[:] = [resolve(bit) for bit in vector]


def repeat_schematic(module):
    """Draw replicated scalar wires as labeled fan-out, not tall bit joins."""
    cells = module['cells']
    vectors = [p['bits'] for p in module.get('ports', {}).values()]
    vectors += [n['bits'] for n in module.get('netnames', {}).values()]
    vectors += [bits for c in cells.values() for bits in c['connections'].values()]
    next_bit = max((b for bits in vectors for b in bits if isinstance(b, int)), default=1) + 1
    targets = [p['bits'] for p in module.get('ports', {}).values() if p.get('direction') == 'output']
    targets += [c['connections'][p] for c in list(cells.values())
                for p, direction in c.get('port_directions', {}).items() if direction == 'input']
    repeats = {}
    for bits in targets:
        start = 0
        while start < len(bits):
            bit = bits[start]
            end = start + 1
            while end < len(bits) and bits[end] == bit:
                end += 1
            # Preserve the sign bit in an adjacent, contiguous low-word slice.
            if isinstance(bit, int) and start and bits[start - 1] == bit - 1:
                start += 1
            count = end - start
            if isinstance(bit, int) and count > 1:
                key = bit, count
                if key not in repeats:
                    output = list(range(next_bit, next_bit + count))
                    next_bit += count
                    name = f'Eitri_repeat_{next_bit}'
                    while name in cells:
                        name += '_'
                    cells[name] = dict(type=f'eitri_repeat_{count}', hide_name=1,
                        attributes={'repeat_count': count}, parameters={},
                        connections={'A': [bit], 'Y': output}, port_directions={'A': 'input', 'Y': 'output'})
                    repeats[key] = output
                bits[start:end] = repeats[key]
            start = end
