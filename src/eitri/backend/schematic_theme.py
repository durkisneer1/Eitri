"""Layout skin and SVG palette for both previews and exported schematics."""
from importlib.resources import files
import xml.etree.ElementTree as ET

SVG = '{http://www.w3.org/2000/svg}'
SKIN = '{https://github.com/nturley/netlistsvg}'
CANVAS = '#242423'
WIRE = '#bfa779'
BOX = '#3c4a50'
BOX_EDGE = '#a4b2b7'
PORT = '#91ad98'
TEXT = '#eee7da'


def write_skin(path, netlist):
    """Give labels physical space before the router places nodes and wires."""
    root = ET.fromstring(files('netlistsvg').joinpath(
        '_vendor/node_modules/netlistsvg/lib/default.svg').read_text())
    ET.register_namespace('', SVG[1:-1])
    ET.register_namespace('s', SKIN[1:-1])
    layout = root.find('.//' + SKIN + 'layoutEngine')
    layout.set('org.eclipse.elk.layered.spacing.nodeNodeBetweenLayers', '60')
    layout.set('org.eclipse.elk.spacing.nodeNode', '45')
    layout.set('org.eclipse.elk.spacing.edgeNode', '25')
    layout.set('org.eclipse.elk.layered.spacing.edgeNodeBetweenLayers', '30')
    # Port labels live inside wide boxes, away from routed wires.
    width = 160
    for module in netlist['modules'].values():
        for cell in module.get('cells', {}).values():
            directions = cell.get('port_directions', {})
            left = max((len(name) for name, direction in directions.items() if direction == 'input'), default=0)
            right = max((len(name) for name, direction in directions.items() if direction != 'input'), default=0)
            title = cell.get('attributes', {}).get('component_type', '')
            width = max(width, (left + right) * 7 + 48, len(title) * 7 + 24)
    generic = next(node for node in root.findall(SVG + 'g') if node.get(SKIN + 'type') == 'generic')
    generic.set(SKIN + 'width', str(width))
    generic.set(SKIN + 'height', '100')
    heading = generic.find(SVG + 'text')
    heading.set('x', str(width / 2))
    heading.set('y', '18')
    subtitle = ET.Element(SVG + 'text', {'x': str(width / 2), 'y': '34',
        'class': 'nodelabel', SKIN + 'attribute': 'component_type'})
    generic.insert(1, subtitle)
    body = generic.find(SVG + 'rect')
    body.set('width', str(width))
    body.set('rx', '4')
    for port in generic.findall(SVG + 'g'):
        output = port.get(SKIN + 'pid', '').startswith('out')
        y = 58 if port.get(SKIN + 'pid', '').endswith('0') else 86
        x = width if output else 0
        port.set(SKIN + 'x', str(x))
        port.set(SKIN + 'y', str(y))
        port.set('transform', f'translate({x},{y})')
        text = port.find(SVG + 'text')
        text.set('x', '-9' if output else '9')
        text.set('y', '4')
        text.set('class', 'boxOutputLabel' if output else 'boxInputLabel')
        text.attrib.pop('style', None)
    style = root.find(SVG + 'style')
    style.text += '\n.boxOutputLabel { text-anchor:end; }\n.boxInputLabel { text-anchor:start; }'
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def color_schematic(path):
    """Use explicit presentation attributes so Qt and SVG exports agree."""
    tree = ET.parse(path)
    root = tree.getroot()

    def visit(node, kind=None):
        kind = node.get(SKIN + 'type', kind)
        tag = node.tag.split('}')[-1]
        node.attrib.pop('style', None)
        net = any(part.startswith('net_') for part in node.get('class', '').split())
        if tag == 'text':
            node.set('fill', PORT if kind in ('inputExt', 'outputExt') else TEXT)
            node.set('stroke', 'none')
            node.set('font-weight', 'normal')
            node.set('font-size', '12px')
            if node.get(SKIN + 'attribute') == 'component_type':
                node.set('fill', '#bec9cd')
                node.set('font-size', '11px')
        elif tag in ('path', 'rect', 'circle', 'line', 'polygon', 'polyline'):
            if net or kind in ('split', 'join'):
                node.set('stroke', WIRE)
                node.set('fill', WIRE if tag in ('circle', 'rect') else 'none')
            else:
                external = kind in ('inputExt', 'outputExt')
                node.set('stroke', PORT if external else BOX_EDGE)
                node.set('fill', ('#35453b' if external else BOX) if tag != 'line' else 'none')
            node.set('stroke-width', '1.4')
        for child in node:
            visit(child, kind)

    visit(root)
    # The stock generic skin draws its header before the body. Filled boxes
    # need the opposite paint order so titles remain visible inside the box.
    for group in root.iter(SVG + 'g'):
        if group.get(SKIN + 'type') == 'generic':
            body = group.find(SVG + 'rect')
            if body is not None:
                group.remove(body)
                group.insert(0, body)
    root.set('stroke', WIRE)
    root.set('fill', 'none')
    # A real background rectangle also travels with exported SVGs.
    root.insert(0, ET.Element(SVG + 'rect', {'width': '100%', 'height': '100%',
                                           'fill': CANVAS, 'stroke': 'none'}))
    tree.write(path, encoding='utf-8', xml_declaration=True)
