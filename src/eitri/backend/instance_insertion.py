"""Find architecture-level insertion sites without trusting the editor cursor.

This is a conservative source navigation helper, not a VHDL elaborator. Insert
at the architecture's closing statement, never inside a process or declaration.
"""
from dataclasses import dataclass
import re
from .project import UNIT, masked


@dataclass(frozen=True)
class InstanceSite:
    architecture: str
    entity: str
    start: int
    end: int
    offset: int


def instance_sites(source):
    text = masked(source)
    units = list(UNIT.finditer(text))
    sites = []
    for index, unit in enumerate(units):
        if unit[1].lower() != 'architecture':
            continue
        stop = units[index + 1].start() if index + 1 < len(units) else len(text)
        name = re.escape(unit[2])
        endings = list(re.finditer(r'\bend\s*(?:(?:architecture\b\s*)?(?:' + name + r'\b)?\s*);',
                                  text[unit.end():stop], re.I))
        if not endings:
            continue
        ending = endings[-1]
        offset = unit.end() + ending.start()
        if not re.search(r'\bbegin\b', text[unit.end():offset], re.I):
            continue
        # Keep any indentation on the closing statement attached to it.
        line_start = text.rfind('\n', 0, offset) + 1
        if not text[line_start:offset].strip():
            offset = line_start
        sites.append(InstanceSite(unit[2], unit[3], unit.start(),
                                  unit.end() + ending.end(), offset))
    return sites
