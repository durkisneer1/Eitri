"""Source generation inside a folder project, without replacing other buffers."""
from pathlib import Path
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox
from eitri.backend.vhdl import parse_entity, entity_names
from .design_dialog import NewDesignDialog
from .templates import design_template, testbench_template, testbench_path

VHDL_FILTER = 'VHDL files (*.vhd *.vhdl)'


class DesignFlow:
    def __init__(self, window):
        self.window = window

    def new_design(self):
        if not self.window.project and not self.window.choose_folder():
            return False
        dialog = NewDesignDialog(self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        filename, _ = QFileDialog.getSaveFileName(self.window, 'Save new design', str(self.window.project.root / (dialog.entity.name + '.vhd')), VHDL_FILTER)
        if not filename:
            return False
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix('.vhd')
        if not self.write_generated(path, design_template(dialog.entity)):
            return False
        return self.window.load(path)

    def choose_entity(self, source):
        names = entity_names(source)
        if not names:
            raise ValueError('No entity declaration found in this file.')
        name = names[0]
        if len(names) > 1:
            name, accepted = QInputDialog.getItem(self.window, 'Choose entity', 'Entity', names, 0, False)
            if not accepted:
                return None
        return parse_entity(source, name, allow_custom_types=True)

    def write_generated(self, path, text):
        path = Path(path).resolve()
        opened = next((d for d in self.window.documents.records if d.path == path), None)
        if opened and opened.editor.document().isModified():
            QMessageBox.warning(self.window, 'Unsaved destination', 'Save or close the destination buffer before replacing it.')
            return False
        if path.exists() and QMessageBox.question(self.window, 'Replace generated file?', f'Replace {path.name}?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return False
        if not self.window.documents.write_text(path, text):
            return False
        if opened:
            opened.editor.setPlainText(text)
            opened.editor.document().setModified(False)
            opened.disk_text = text
        self.window.refresh_project()
        return True

    def create_testbench(self):
        if not self.window.editor:
            return False
        try:
            entity = self.choose_entity(self.window.editor.toPlainText())
            if entity is None:
                return False
            import re
            from eitri.backend.project import masked
            source = masked(self.window.editor.toPlainText())
            context = '\n'.join(dict.fromkeys(re.findall(r'\b(?:library|use|context)\s+[^;]+;', source, re.I)))
            text = testbench_template(entity, context=(context + '\n') if context else None, allow_custom_types=True)
        except ValueError as error:
            QMessageBox.warning(self.window, 'Cannot create testbench', str(error))
            return False
        if self.window.path is None and not self.window.save_as():
            return False
        proposed = testbench_path(self.window.path)
        filename, _ = QFileDialog.getSaveFileName(self.window, 'Save testbench', str(proposed), VHDL_FILTER)
        if not filename:
            return False
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix('.vhd')
        if path.resolve() == self.window.path:
            QMessageBox.warning(self.window, 'Choose another file', 'A testbench cannot replace its design source.')
            return False
        if not self.write_generated(path, text):
            return False
        self.window.load(path)
        self.window.select_file_target('simulation', path, run=False)
        return True

    def insert_instance(self, path=None):
        window = self.window
        if not window.project or not window.editor or window.editor.isReadOnly():
            return
        window.refresh_project()
        choices = [u for u in window.project.entities if path is None or Path(u.path) == Path(path)]
        if not choices:
            return
        labels = [f'{u.library}.{u.name} — {window.project.relative(u.path)}' for u in choices]
        label, accepted = QInputDialog.getItem(window, 'Insert component instance', 'Design to instantiate', labels, 0, False)
        if not accepted:
            return
        unit = choices[labels.index(label)]
        try:
            entity = parse_entity(window.project.sources[unit.path], unit.name, allow_custom_types=True)
        except ValueError as error:
            QMessageBox.warning(window, 'Cannot generate port map', str(error))
            return
        import re
        label = 'u_' + entity.name
        source = window.editor.toPlainText()
        while re.search(r'\b' + re.escape(label) + r'\s*:', source, re.I):
            label += '_inst'
        text = f'\n    -- Replace <...> with your connections.\n    {label} : entity {unit.library}.{entity.name}'
        if entity.generics:
            text += '\n        generic map (\n' + ',\n'.join(f'            {g.name} => {g.default}' for g in entity.generics) + '\n        )'
        if entity.ports:
            text += '\n        port map (\n' + ',\n'.join(f'            {p.name} => <{p.name}>' for p in entity.ports) + '\n        )'
        window.editor.insertPlainText(text + ';\n')
        window.statusBar().showMessage('Instance inserted. Replace each <...> placeholder with a signal.', 7000)
