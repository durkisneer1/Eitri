"""Small, explicit entity-interface reader for testbench generation.

This is not a VHDL compiler. It supports basic names, STD_LOGIC ports, constrained
STD_LOGIC_VECTOR ports, and scalar generic defaults. Unsupported interfaces fail
with a useful message instead of producing a partly connected testbench.
"""
from dataclasses import dataclass, field
import re
from .pipeline import IDENTIFIER

RESERVED = set('''abs access after alias all and architecture array assert assume
assume_guarantee attribute begin block body buffer bus case component configuration
constant context cover default disconnect downto else elsif end entity exit fairness
file for force function generate generic group guarded if impure in inertial inout is
label library linkage literal loop map mod nand new next nor not null of on open or
others out package parameter port postponed procedure process property protected pure
range record register reject release rem report restrict restrict_guarantee return rol
ror select sequence severity shared signal sla sll sra srl strong subtype then to
transport type unaffected units until use variable vmode vprop vunit wait when while
with xnor xor'''.split())


def valid_name(name):
    return bool(IDENTIFIER.fullmatch(name)) and name.lower() not in RESERVED



def validate_name(name, kind):
    """Explain the first broken basic-identifier rule in the creation form."""
    if not name:
        raise ValueError(f'{kind} name is required.')
    if name.startswith('\\'):
        raise ValueError(f'{kind} name: extended identifiers are not supported by Eitri. Use a name starting with a letter.')
    if not re.match(r'[A-Za-z]', name):
        raise ValueError(f'{kind} name "{name}" must start with a letter (A–Z), not a digit or symbol.')
    if re.search(r'[^A-Za-z0-9_]', name):
        raise ValueError(f'{kind} name "{name}" may contain only letters, digits and underscores; no spaces or other symbols.')
    if '__' in name:
        raise ValueError(f'{kind} name "{name}" cannot contain consecutive underscores.')
    if name.endswith('_'):
        raise ValueError(f'{kind} name "{name}" cannot end with an underscore.')
    if name.lower() in RESERVED:
        raise ValueError(f'{kind} name "{name}" is a reserved VHDL word. Choose a different name.')


@dataclass(frozen=True)
class Port:
    name: str
    direction: str
    data_type: str = 'STD_LOGIC'


@dataclass(frozen=True)
class Generic:
    name: str
    data_type: str
    default: str


@dataclass(frozen=True)
class Entity:
    name: str
    ports: list[Port] = field(default_factory=list)
    generics: list[Generic] = field(default_factory=list)


def validate_entity(entity):
    validate_name(entity.name, 'Entity')
    names = set()
    for item in [*entity.generics, *entity.ports]:
        validate_name(item.name, 'Generic' if isinstance(item, Generic) else 'Port')
        if item.name.lower() in names:
            raise ValueError(f'Duplicate name: {item.name} (VHDL names are case-insensitive).')
        names.add(item.name.lower())
    for port in entity.ports:
        if port.direction not in ('in', 'out', 'inout', 'buffer'):
            raise ValueError(f'Unsupported port direction for {port.name}.')
        if not re.fullmatch(r'STD_LOGIC(?:_VECTOR\s*\(.+\))?', port.data_type, re.I):
            raise ValueError(f'{port.name}: only STD_LOGIC and constrained STD_LOGIC_VECTOR are supported.')


# Preserve quoted literals while removing comments; comment markers in strings
# must not corrupt the entity text being inspected.
COMMENT = re.compile(r'"(?:[^"]|"")*"|\'[^\']\'|--[^\n]*|/\*.*?\*/', re.S)


def without_comments(source):
    return COMMENT.sub(lambda match: ' ' if match[0].startswith(('--', '/*')) else match[0], source)


def split_declarations(text):
    """Split semicolons only outside parentheses and quoted literals."""
    return _split_top_level(text, ';')


def _split_top_level(text, delimiter):
    parts, start, depth = [], 0, 0
    quoted = False
    for index, character in enumerate(text):
        if character == '"':
            quoted = not quoted
        elif not quoted:
            if character == '(':
                depth += 1
            elif character == ')':
                depth -= 1
            elif character == delimiter and depth == 0:
                parts.append(text[start:index].strip())
                start = index + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def clause(body, keyword):
    match = re.search(r'\b' + keyword + r'\s*\(', body, re.I)
    if not match:
        return ''
    start, depth = match.end(), 1
    quoted = False
    for index in range(start, len(body)):
        character = body[index]
        if character == '"':
            quoted = not quoted
        elif not quoted:
            if character == '(':
                depth += 1
            elif character == ')':
                depth -= 1
                if depth == 0:
                    return body[start:index]
    raise ValueError(f'Unclosed {keyword} clause in the entity.')


def entity_names(source):
    return re.findall(r'\bentity\s+([A-Za-z][A-Za-z0-9_]*)\s+is\b', without_comments(source), re.I)


def parse_entity(source, name=None):
    text = without_comments(source)
    names = entity_names(text)
    if not names:
        raise ValueError('No entity declaration was found in the Design tab.')
    chosen = next((item for item in names if name and item.lower() == name.lower()), names[0])
    if name and chosen.lower() != name.lower():
        raise ValueError(f'Entity {name} was not found in the Design tab.')
    start = re.search(r'\bentity\s+' + re.escape(chosen) + r'\s+is\b', text, re.I).end()
    ending = re.search(r'\bend\s*(?:entity\s*)?(?:' + re.escape(chosen) + r'\s*)?;', text[start:], re.I)
    if not ending:
        raise ValueError(f'Could not find the end of entity {chosen}.')
    body = text[start:start + ending.start()]
    ports, generics = [], []
    for declaration in split_declarations(clause(body, 'generic')):
        match = re.fullmatch(r'\s*(?:constant\s+)?([\w,\s]+)\s*:\s*(?:in\s+)?(integer|positive|natural|boolean)\s*:=\s*(.+)', declaration, re.I | re.S)
        if not match:
            raise ValueError('Testbench generation supports integer/positive/natural/boolean generics with defaults. Edit other interfaces manually.')
        for generic_name in match[1].split(','):
            generics.append(Generic(generic_name.strip(), match[2], match[3].strip()))
    for declaration in split_declarations(clause(body, 'port')):
        declaration = declaration.split(':=', 1)[0].strip()
        match = re.fullmatch(r'\s*(?:signal\s+)?([\w,\s]+)\s*:\s*(?:(inout|buffer|in|out)\s+)?(STD_LOGIC(?:_VECTOR\s*\(.+\))?)(?:\s*:=\s*.+)?', declaration, re.I | re.S)
        if not match:
            raise ValueError('Testbench generation supports STD_LOGIC and constrained STD_LOGIC_VECTOR ports. Check the entity declaration.')
        data_type = re.sub(r'\s+', ' ', match[3]).strip()
        if 'vector' in data_type.lower() and not re.search(r'\b(to|downto)\b', data_type, re.I):
            raise ValueError('Vector ports must have an explicit range, for example (7 downto 0).')
        for port_name in match[1].split(','):
            ports.append(Port(port_name.strip(), (match[2] or 'in').lower(), data_type))
    entity = Entity(chosen, ports, generics)
    validate_entity(entity)
    return entity
