"""Track source references in portable VHDL comments and snapshot dependency trees."""
import json
import os
from pathlib import Path
import re
from .vhdl import entity_names, without_comments

REFERENCE = re.compile(r'^\s*-- eitri-source: (.+)$', re.M)


def references(source, path):
    paths = []
    for value in REFERENCE.findall(source):
        try:
            name = json.loads(value)
            if not isinstance(name, str):
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError('Invalid eitri-source reference; expected a quoted filename.')
        target = Path(name)
        if not target.is_absolute():
            if path is None:
                raise ValueError('Save the design before resolving relative component sources.')
            target = Path(path).parent / target
        paths.append(target.resolve())
    return paths


def relative_reference(path, destination):
    try:
        return os.path.relpath(path, Path(destination).resolve().parent)
    except ValueError:  # Different Windows drives cannot have a relative path.
        return str(path)


def add_references(source, paths, destination):
    lines = ['-- eitri-source: ' + json.dumps(relative_reference(path, destination))
             for path in dict.fromkeys(Path(path).resolve() for path in paths)]
    return ('\n'.join(lines) + '\n\n' if lines else '') + source


def rebase_references(source, previous, destination):
    if previous is None or Path(previous).resolve() == Path(destination).resolve():
        return source
    targets = iter(references(source, previous))
    return REFERENCE.sub(lambda _: '-- eitri-source: ' + json.dumps(
        relative_reference(next(targets), destination)), source)


def required_entities(source):
    text = without_comments(source)
    names = re.findall(r'\bcomponent\s+([A-Za-z][\w]*)\s*(?:is\b|port\b|generic\b|end\b)', text, re.I)
    names += re.findall(r'\bentity\s+work\.([A-Za-z][\w]*)', text, re.I)
    names += re.findall(r':\s*([A-Za-z][\w]*)\s+(?:generic|port)\s+map\b', text, re.I)
    return set(name.lower() for name in names)


def snapshot_dependencies(roots):
    """Resolve explicit references plus component entities in sibling VHDL files.

    Roots are (path-or-None, editor-text) pairs. Dependencies are ordered before
    their users, read fresh on every run, and never overwrite editor snapshots.
    """
    root_paths = {Path(path).resolve() for path, _ in roots if path}
    root_names = {name.lower() for _, source in roots for name in entity_names(source)}
    visiting, visited, owners, result = set(), set(), {}, []
    cache = {}

    def read(path):
        if path not in cache:
            try:
                cache[path] = path.read_text(encoding='utf-8')
            except (OSError, UnicodeError) as error:
                raise ValueError(f'Cannot read component source {path}: {error}') from error
        return cache[path]

    def discover(path, source):
        explicit = references(source, path)
        local = {name.lower() for name in entity_names(source)}
        required = required_entities(source) - local
        if path and Path(path).resolve() not in root_paths and required & root_names:
            raise ValueError(f'Circular component dependency from {path} to the active design.')
        needed = required - root_names
        provided = {}
        for target in explicit:
            for name in entity_names(read(target)):
                provided.setdefault(name.lower(), []).append(target)
        directory = Path(path).resolve().parent if path else None
        for name in sorted(needed):
            candidates = provided.get(name, [])
            if not candidates and directory:
                for candidate in sorted(directory.iterdir()):
                    if candidate.suffix.lower() not in ('.vhd', '.vhdl') or not candidate.is_file():
                        continue
                    candidate = candidate.resolve()
                    if candidate in root_paths:
                        continue
                    if name in {item.lower() for item in entity_names(read(candidate))}:
                        candidates.append(candidate)
            candidates = list(dict.fromkeys(candidates))
            if not candidates:
                raise ValueError(f'Cannot find component entity "{name}". Place its source beside {path or "the saved design"} or add an eitri-source reference.')
            if len(candidates) > 1:
                raise ValueError(f'Multiple sources define "{name}". Add an explicit eitri-source reference to select one.')
            if candidates[0] not in explicit:
                explicit.append(candidates[0])
        for target in explicit:
            visit(target)

    def visit(path):
        if path in root_paths:
            return
        if path in visiting:
            raise ValueError(f'Circular component dependency involving {path.name}.')
        if path in visited:
            return
        source = read(path)
        for name in entity_names(source):
            key = name.lower()
            if key in root_names or (key in owners and owners[key] != path):
                raise ValueError(f'Duplicate entity "{name}" in component source {path}.')
            owners[key] = path
        visiting.add(path)
        discover(path, source)
        visiting.remove(path)
        visited.add(path)
        result.append({'path': str(path), 'source': source})

    for path, source in roots:
        discover(path, source)
    return result
