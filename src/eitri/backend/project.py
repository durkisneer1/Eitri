"""Folder index shared by navigation, editor assistance and run snapshots.

This tolerant source index is for navigation and ordering, not elaboration:
GHDL remains authoritative for bindings, generate conditions and type checking.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
import fnmatch
import hashlib
import json
import re
from .vhdl import valid_name

NAME = r'[a-zA-Z][a-zA-Z0-9_]*'
UNIT = re.compile(r'\b(entity|architecture|package\s+body|package)\s+(' + NAME + r')(?:\s+of\s+(' + NAME + r'))?\s+is\b', re.I)
INSTANCE = re.compile(r'\b(' + NAME + r')\s*:\s*(?:(entity)\s+(?:(' + NAME + r')\s*\.)?|(component)\s+)?(' + NAME + r')(?:\s*\(\s*(' + NAME + r')\s*\))?\s*(?=generic\s+map|port\s+map|;)', re.I)
IGNORE = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'build', 'dist', '.eitri', 'runs', 'analysis-cache'}


def masked(source):
    # Keep source offsets, including lines, for navigation and diagnostics.
    pattern = r'--[^\n]*|/\*.*?\*/|"(?:[^"]|"")*"'
    return re.sub(pattern, lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), source, flags=re.S)


@dataclass
class Instance:
    name: str
    entity: str
    library: str
    architecture: str
    line: int
    associations: str = ''


@dataclass
class Unit:
    name: str
    kind: str
    path: str
    library: str
    line: int
    entity: str = ''
    instances: list = field(default_factory=list)
    has_ports: bool = False

    @property
    def key(self):
        return f'{self.library}.{self.name}'.lower()


@dataclass
class Target:
    name: str
    kind: str
    entity: str
    path: str
    library: str = 'work'
    architecture: str = ''
    generics: dict = field(default_factory=dict)
    stop_time: str = '200ns'
    wave_format: str = 'VCD'
    circuit_detail: str = 'Simple'
    signals: list | None = None


class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = {'version': 1, 'standard': 'VHDL 2008', 'exclude': [], 'libraries': {}, 'targets': []}
        self.config_path = self.root / '.eitri.json'
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version', 1) != 1:
                raise ValueError('Unsupported .eitri.json project format.')
            self.config.update(data)
        if not isinstance(self.config['exclude'], list) or not isinstance(self.config['libraries'], dict):
            raise ValueError('Project excludes must be a list and libraries a mapping of names to file patterns.')
        from .pipeline import STANDARDS
        if self.config['standard'] not in STANDARDS:
            raise ValueError('Choose a supported VHDL standard in .eitri.json.')
        if not all(isinstance(p, str) for p in self.config['exclude']):
            raise ValueError('Project exclude patterns must be strings.')
        for library, patterns in self.config['libraries'].items():
            if not isinstance(library, str) or not valid_name(library) or not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
                raise ValueError('Each library needs a VHDL name and a list of file patterns.')
        if not isinstance(self.config['targets'], list):
            raise ValueError('Project targets must be a list.')
        try:
            for data in self.config['targets']:
                target = Target(**data)
                if target.kind not in ('simulation', 'circuit') or not all(isinstance(v, str) for v in (target.name, target.entity, target.path, target.library, target.architecture)) or not isinstance(target.generics, dict):
                    raise ValueError('Invalid saved run target.')
        except (TypeError, KeyError) as error:
            raise ValueError(f'Invalid saved run target: {error}') from error
        self.sources = {}
        self.units = []
        self.issues = []
        self.cache = {}
        self.revision = 0
        self.refresh()

    def relative(self, path):
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def library_for(self, path):
        relative = self.relative(path)
        libraries = [name for name, patterns in self.config['libraries'].items()
                     if any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)]
        if len(libraries) > 1:
            raise ValueError(f'{relative} matches multiple libraries: {", ".join(libraries)}')
        return libraries[0].lower() if libraries else 'work'

    def refresh(self, overlays=None):
        overlays = {str(Path(p).resolve()): text for p, text in (overlays or {}).items()}
        sources = {}
        issues = []
        import os
        for folder, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in IGNORE and not d.startswith('.') and
                             not any(fnmatch.fnmatch(self.relative(Path(folder) / d), p) for p in self.config['exclude']))
            for filename in sorted(files):
                path = Path(folder) / filename
                if path.suffix.lower() not in ('.vhd', '.vhdl') or path.is_symlink():
                    continue
                if any(fnmatch.fnmatch(self.relative(path), p) for p in self.config['exclude']):
                    continue
                key = str(path.resolve())
                try:
                    stat = path.stat()
                    stamp = (stat.st_mtime_ns, stat.st_size)
                    if key in overlays:
                        text = overlays[key]
                    elif key in self.cache and self.cache[key][0] == stamp:
                        text = self.cache[key][1]
                    else:
                        text = path.read_text(encoding='utf-8')
                        self.cache[key] = (stamp, text)
                    sources[key] = text
                except (OSError, UnicodeError) as error:
                    issues.append(f'{self.relative(path)}: {error}')
        # Keep unsaved buffers even if their backing file was externally deleted.
        sources.update({p: t for p, t in overlays.items() if Path(p).is_relative_to(self.root)})
        if sources == self.sources and self.units:
            self.issues = list(dict.fromkeys(self.issues + issues))
            return False
        self.sources = sources
        self.revision += 1
        self.units = []
        self.issues = issues
        for path, source in sources.items():
            text = masked(source)
            matches = list(UNIT.finditer(text))
            for index, match in enumerate(matches):
                kind = re.sub(r'\s+', ' ', match[1].lower())
                if kind == 'entity' and match[3]:
                    continue
                body = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
                unit = Unit(match[2], kind, path, self.library_for(path), text.count('\n', 0, match.start()), match[3] or '')
                if kind == 'entity':
                    unit.has_ports = bool(re.search(r'\bport\s*\(', body, re.I))
                if kind == 'architecture':
                    for inst in INSTANCE.finditer(body):
                        if (not inst[2] and not inst[4] and not re.match(r'\s*(generic|port)\s+map', body[inst.end():], re.I)) or inst[5].lower() in ('process', 'block', 'for', 'if', 'assert'):
                            continue
                        offset = match.end() + inst.start()
                        tail = source[match.end() + inst.end():]
                        association = tail.split(';', 1)[0].strip()[:1500]
                        unit.instances.append(Instance(inst[1], inst[5], inst[3] or unit.library,
                                                       inst[6] or '', text.count('\n', 0, offset), association))
                self.units.append(unit)
        seen = {}
        for unit in self.units:
            key = (unit.library, unit.kind, unit.entity.lower(), unit.name.lower())
            if key in seen:
                self.issues.append(f'Duplicate {unit.kind} {unit.key}: {self.relative(seen[key])} and {self.relative(unit.path)}')
            seen[key] = unit.path
        return True

    @property
    def entities(self):
        return [u for u in self.units if u.kind == 'entity']

    def resolve(self, entity, library='work', architecture=''):
        matches = [u for u in self.entities if u.name.lower() == entity.lower() and u.library.lower() == library.lower()]
        if len(matches) != 1:
            raise ValueError(f'{"Missing" if not matches else "Ambiguous"} entity {library}.{entity}.')
        unit = matches[0]
        architectures = [u for u in self.units if u.kind == 'architecture' and u.library == unit.library and u.entity.lower() == unit.name.lower()]
        if architecture:
            architectures = [u for u in architectures if u.name.lower() == architecture.lower()]
        if len(architectures) != 1:
            raise ValueError(f'{unit.key}: ' + ('select an architecture; multiple implementations exist.' if len(architectures) > 1 else 'no matching architecture found.'))
        return unit, architectures[0]

    def targets(self, kind):
        saved = [Target(**data) for data in self.config['targets'] if data.get('kind') == kind]
        occupied = {(t.library, t.entity.lower(), t.architecture.lower()) for t in saved}
        for unit in self.entities:
            if kind == 'simulation' and unit.has_ports:
                continue
            architectures = [a for a in self.units if a.kind == 'architecture' and a.library == unit.library and a.entity.lower() == unit.name.lower()]
            for arch in architectures:
                if (unit.library, unit.name.lower(), arch.name.lower()) in occupied:
                    continue
                suffix = f' ({arch.name})' if len(architectures) > 1 else ''
                saved.append(Target(unit.name + suffix, kind, unit.name, self.relative(unit.path), unit.library, arch.name))
        return saved

    def save_target(self, target):
        data = asdict(target)
        self.config['targets'] = [t for t in self.config['targets'] if not (t['name'] == target.name and t['kind'] == target.kind)] + [data]
        self.save_config()

    def save_config(self):
        # Atomic metadata write; source files are never modified by indexing.
        temporary = self.config_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(self.config, indent=2) + '\n', encoding='utf-8')
        temporary.replace(self.config_path)

    def ordered_sources(self, target=None):
        """Dependency order for analysis. Compiler checks semantic correctness."""
        files = set(self.sources)
        dependencies = {p: set() for p in files}
        missing_packages = {}
        packages = {(u.library, u.name.lower()): u.path for u in self.units if u.kind == 'package'}
        entities = {(u.library, u.name.lower()): u.path for u in self.entities}
        for path, source in self.sources.items():
            library = self.library_for(path)
            for lib, name in re.findall(r'\buse\s+(' + NAME + r')\.(' + NAME + r')\.', masked(source), re.I):
                key = (library if lib.lower() == 'work' else lib.lower(), name.lower())
                if key in packages:
                    dependencies[path].add(packages[key])
                elif key[0] not in ('std', 'ieee'):
                    missing_packages.setdefault(path, []).append(f'{self.relative(path)}: missing package {key[0]}.{key[1]}.')
        for unit in self.units:
            if unit.kind in ('architecture', 'package body'):
                key = (unit.library, (unit.entity or unit.name).lower())
                declaration = (entities if unit.kind == 'architecture' else packages).get(key)
                if declaration:
                    dependencies[unit.path].add(declaration)
            for instance in unit.instances:
                lib = unit.library if instance.library.lower() == 'work' else instance.library.lower()
                try:
                    child, arch = self.resolve(instance.entity, lib, instance.architecture)
                except ValueError:
                    # Unrelated, unfinished components do not block another target.
                    continue
                dependencies[unit.path].update((child.path, arch.path))
        required = set(files)
        if target:
            root, architecture = self.resolve(target.entity, target.library, target.architecture)
            required = {root.path, architecture.path}
            # Package bodies must accompany packages when used.
            for unit in self.units:
                if unit.kind == 'package body':
                    declaration = packages.get((unit.library, unit.name.lower()))
                    if declaration:
                        dependencies[declaration].add(unit.path)
            pending = list(required)
            while pending:
                p = pending.pop()
                for dep in dependencies[p] - required:
                    required.add(dep)
                    pending.append(dep)
            # Explicitly diagnose unresolved/ambiguous instances in this target.
            for unit in self.units:
                if unit.path in required:
                    for instance in unit.instances:
                        self.resolve(instance.entity, unit.library if instance.library.lower() == 'work' else instance.library.lower(), instance.architecture)
        errors = [message for path in required for message in missing_packages.get(path, [])]
        if errors:
            raise ValueError('\n'.join(errors))
        # Package/body pairs have a mutual reachability edge but only the body
        # depends on the declaration for compilation.
        for unit in self.units:
            if unit.kind == 'package body':
                declaration = packages.get((unit.library, unit.name.lower()))
                if declaration:
                    dependencies[declaration].discard(unit.path)
        ordered, visited, active = [], set(), set()
        def visit(path):
            if path in visited:
                return
            if path in active:
                raise ValueError(f'Circular file dependency involving {self.relative(path)}. Separate mutually dependent design units into files.')
            active.add(path)
            for dep in sorted(dependencies[path] - {path}):
                if dep in required:
                    visit(dep)
            active.remove(path)
            visited.add(path)
            ordered.append({'path': path, 'source': self.sources[path], 'library': self.library_for(path)})
        for path in sorted(required):
            visit(path)
        return ordered

    def snapshot(self, target, **settings):
        sources = self.ordered_sources(target)
        if self.issues:
            raise ValueError('\n'.join(self.issues))
        return {'kind': target.kind, 'project_root': str(self.root), 'sources': sources,
                'target': asdict(target), 'standard': self.config['standard'],
                'entity': target.entity, 'testbench': target.entity,
                'stop_time': target.stop_time, 'wave_format': target.wave_format,
                'circuit_detail': target.circuit_detail, **settings}
