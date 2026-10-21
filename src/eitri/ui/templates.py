"""Minimal VHDL source generators. No Qt dependencies and no demo logic."""
from eitri.backend.vhdl import Entity, validate_entity

HEADER = 'library IEEE;\nuse IEEE.STD_LOGIC_1164.ALL;\n'


def interface_lines(entity, indent='    '):
    lines = []
    if entity.generics:
        lines.append(indent + 'generic (')
        declarations = [f'{item.name} : {item.data_type} := {item.default}' for item in entity.generics]
        lines.append(';\n'.join(indent + '    ' + item for item in declarations))
        lines.append(indent + ');')
    if entity.ports:
        lines.append(indent + 'port (')
        declarations = [f'{port.name} : {port.direction} {port.data_type}' for port in entity.ports]
        lines.append(';\n'.join(indent + '    ' + item for item in declarations))
        lines.append(indent + ');')
    return lines


def design_template(entity: Entity, components=()):
    validate_entity(entity)
    declarations, instances = [], []
    used = {entity.name.lower(), *(port.name.lower() for port in entity.ports)}
    used.update(component.entity.name.lower() for component in components)

    def unique(name):
        while name.lower() in used:
            name += '_inst'
        used.add(name.lower())
        return name

    for component in components:
        child = component.entity
        declarations += [f'    component {child.name} is',
                         *interface_lines(child, '        '), '    end component;', '']
        for number in range(1, component.count + 1):
            instance = unique(f'u_{child.name}_{number}')
            # Explicit placeholders avoid inventing wiring or unnecessary signals.
            # Generic defaults remain in the component declaration.
            instances += ['    -- Replace <...> with connections before compiling.',
                          f'    {instance} : {child.name}']
            if child.ports:
                instances += ['        port map (', ',\n'.join(
                    f'            {port.name} => <{port.name}>' for port in child.ports), '        );']
            else:
                instances[-1] += ';'
            instances.append('')
    lines = [HEADER, f'entity {entity.name} is', *interface_lines(entity),
             f'end {entity.name};', '', f'architecture Behavioral of {entity.name} is',
             *declarations, '    -- Declare internal signals here.', 'begin',
             *instances, '    -- Add your design logic here.', 'end Behavioral;', '']
    return '\n'.join(lines)


def testbench_template(entity: Entity, context=None, allow_custom_types=False):
    validate_entity(entity, allow_custom_types=allow_custom_types)
    tb_name = entity.name + '_TB'
    # Generated signal names avoid clashes with the component and generic names.
    used = {entity.name.lower(), tb_name.lower(), *(item.name.lower() for item in entity.generics)}
    uut_label = 'uut'
    while uut_label.lower() in used:
        uut_label += '_inst'
    used.add(uut_label.lower())
    stimulus_label = 'stimulus'
    while stimulus_label.lower() in used:
        stimulus_label += '_proc'
    used.add(stimulus_label.lower())
    signals = {}
    for port in entity.ports:
        name = port.name + '_sig'
        while name.lower() in used:
            name += '_sig'
        used.add(name.lower())
        signals[port.name] = name
    lines = [context or HEADER, f'entity {tb_name} is', f'end {tb_name};', '',
             f'architecture Behavioral of {tb_name} is', f'    component {entity.name} is',
             *interface_lines(entity, '        '), '    end component;', '']
    for generic in entity.generics:
        lines.append(f'    constant {generic.name} : {generic.data_type} := {generic.default};')
    for port in entity.ports:
        initial = ''
        if port.direction == 'in' and port.data_type.upper().startswith('STD_LOGIC'):
            initial = " := (others => '0')" if 'vector' in port.data_type.lower() else " := '0'"
        lines.append(f'    signal {signals[port.name]} : {port.data_type}{initial};')
    lines += ['begin', f'    {uut_label} : {entity.name}']
    if entity.generics:
        lines += ['        generic map (', ',\n'.join(f'            {item.name} => {item.name}' for item in entity.generics), '        )']
    if entity.ports:
        lines += ['        port map (', ',\n'.join(f'            {port.name} => {signals[port.name]}' for port in entity.ports), '        );']
    else:
        lines[-1] += ';'
    lines += ['', f'    {stimulus_label} : process', '    begin', '        -- Add input changes and checks here.',
              '        wait;', f'    end process {stimulus_label};', 'end Behavioral;', '']
    return '\n'.join(lines)


def testbench_path(design_path):
    """Keep the folder and extension: adder.vhdl becomes adder_TB.vhdl."""
    return design_path.with_name(design_path.stem + '_TB' + design_path.suffix)
