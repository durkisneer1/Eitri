"""Adapt four-state constants for netlistsvg without changing the real netlist."""
from copy import deepcopy


def display_netlist(netlist, top=None):
    """Represent X/Z as labeled source boxes in a renderer-only copy.

    netlistsvg 1.0.2 rejects Z and does not render X as a proper constant node.
    Separate synthetic nets preserve the distinction instead of treating Z as 0.
    The original netlist.json remains the authoritative synthesis artifact.
    """
    display = deepcopy(netlist)
    if top is not None:
        # Child implementations stay in the exported netlist. The renderer sees
        # only the top module, so child instances become labeled port boxes.
        display['modules'] = {top: display['modules'][top]}
        for name, cell in display['modules'][top].get('cells', {}).items():
            if cell.get('type') in netlist['modules']:
                # Generic boxes otherwise show only their type, hiding which
                # instance they represent. Change only the renderer's label.
                import re
                original_type = cell['type']
                cell.setdefault('attributes', {})['component_type'] = re.sub(r'_B[^_]+$', '', original_type)
                cell['type'] = name
    for module in display['modules'].values():
        # Scope markers retain source attributes after flattening, not hardware.
        module['cells'] = {name: cell for name, cell in module.get('cells', {}).items()
                           if cell.get('type') != '$scopeinfo'}
        vectors = [port['bits'] for port in module.get('ports', {}).values()]
        vectors += [net['bits'] for net in module.get('netnames', {}).values()]
        vectors += [bits for cell in module.get('cells', {}).values() for bits in cell.get('connections', {}).values()]
        next_bit = max((bit for bits in vectors for bit in bits if isinstance(bit, int)), default=1) + 1
        sources = {}
        for bits in vectors:
            for value, title in (('z', 'High impedance (Z)'), ('x', 'Unknown (X)')):
                count = bits.count(value)
                if not count:
                    continue
                key = (value, count)
                if key not in sources:
                    sources[key] = list(range(next_bit, next_bit + count))
                    next_bit += count
                replacements = iter(sources[key])
                for index, bit in enumerate(bits):
                    if bit == value:
                        bits[index] = next(replacements)
        for (value, count), bits in sources.items():
            name = f'Eitri_{value.upper()}_{count}'
            while name in module.setdefault('cells', {}):
                name += '_'
            module['cells'][name] = {
                'type': 'High impedance (Z)' if value == 'z' else 'Unknown (X)',
                'parameters': {}, 'attributes': {}, 'port_directions': {'Y': 'output'},
                'connections': {'Y': bits}, 'hide_name': 0}
    return display


def inline_svg_styles(path):
    """Inline the shipped netlistsvg skin's simple CSS for Qt's SVG renderer.

    Browser SVG engines apply the root `svg` rule to all descendants. Qt's SVG
    subset can drop that inherited stroke, making wires disappear. Resolve the
    skin's tag/class rules into presentation attributes before displaying/exporting.
    """
    import re
    import xml.etree.ElementTree as ET
    namespace = '{http://www.w3.org/2000/svg}'
    ET.register_namespace('', namespace[1:-1])
    tree = ET.parse(path)
    root = tree.getroot()
    rules = []
    for style in root.findall(namespace + 'style'):
        for selector, declarations in re.findall(r'([^{}]+)\{([^{}]+)\}', style.text or ''):
            properties = dict(part.strip().split(':', 1) for part in declarations.split(';') if ':' in part)
            rules.append((selector.strip(), {key.strip(): value.strip() for key, value in properties.items()}))
        root.remove(style)
    inherited_keys = {'stroke', 'stroke-width', 'fill', 'font-size', 'font-family', 'font-weight', 'text-anchor'}

    def visit(element, inherited):
        properties = dict(inherited)
        properties.update({key: value for key, value in element.attrib.items() if key in inherited_keys})
        tag = element.tag.split('}')[-1]
        classes = element.get('class', '').split()
        for selector, declarations in rules:
            if selector == tag or (selector.startswith('.') and selector[1:] in classes):
                properties.update(declarations)
        for declaration in element.get('style', '').split(';'):
            if ':' in declaration:
                key, value = declaration.split(':', 1)
                properties[key.strip()] = value.strip()
        for key, value in properties.items():
            element.set(key, value)
        for child in element:
            visit(child, {key: value for key, value in properties.items() if key in inherited_keys})
    visit(root, {})
    tree.write(path, encoding='utf-8', xml_declaration=True)
