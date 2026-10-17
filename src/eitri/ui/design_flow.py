"""Onboarding and source creation; commit editor changes only after safe writes."""
from pathlib import Path
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox
from eitri.backend.dependencies import add_references
from eitri.backend.vhdl import entity_names, parse_entity
from .design_dialog import NewDesignDialog, WelcomeDialog
from .components_dialog import ComponentsDialog
from .templates import design_template, testbench_template, testbench_path

VHDL_FILTER = 'VHDL files (*.vhd *.vhdl);;All files (*)'


class DesignFlow:
    def __init__(self, window):
        self.window = window

    def startup(self):
        # Cancellation of a child file dialog returns to the initial choice.
        # Cancel on the welcome dialog leaves an empty, usable workspace.
        while True:
            dialog = WelcomeDialog(self.window)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            if (self.new_design() if dialog.choice == 'new' else self.open_design()):
                return

    def confirm_all(self):
        tabs = self.window.code_page.code_tabs
        original = tabs.currentIndex()
        for index in range(2):
            tabs.setCurrentIndex(index)
            if not self.window.confirm_discard():
                return False
        tabs.setCurrentIndex(original)
        return True

    def install_design(self, path, text):
        """Replace the design and detach the prior testbench as one UI operation."""
        window = self.window
        window.paths = [path, None]
        window.code_page.code_tabs.setCurrentIndex(0)
        window.code_page.editors[0].setPlainText(text)
        window.code_page.editors[1].clear()
        for editor in window.code_page.editors:
            editor.document().setModified(False)
        names = entity_names(text)
        window.sidebar.entity.setText(names[0] if names else '')
        window.sidebar.testbench.setText(names[0] + '_TB' if names else '')
        window.update_title()
        window.switch_mode(0)
        window.editor.setFocus()
        window.statusBar().showMessage(f'Opened {path.name}. Create a testbench from the Design tab.', 6000)

    def new_design(self):
        if not self.confirm_all():
            return False
        dialog = NewDesignDialog(self.window)
        while True:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            entity = dialog.entity
            components_dialog = ComponentsDialog(entity, self.window)
            if components_dialog.exec() == QDialog.DialogCode.Accepted:
                break
        filename, _ = QFileDialog.getSaveFileName(self.window, 'Save new design', entity.name + '.vhd', VHDL_FILTER)
        if not filename:
            return False
        path = self.with_extension(Path(filename))
        if path is None:
            return False
        if any(item.path.resolve() == path.resolve() for item in components_dialog.components):
            QMessageBox.warning(self.window, 'Component source conflict', 'Save the parent design to a different file from its component sources.')
            return False
        text = design_template(entity, components_dialog.components)
        text = add_references(text, [item.path for item in components_dialog.components], path)
        if not self.window.documents.write_text(path, text):
            return False
        self.install_design(path, text)
        return True

    def open_design(self):
        if not self.confirm_all():
            return False
        filename, _ = QFileDialog.getOpenFileName(self.window, 'Open VHDL design', '', VHDL_FILTER)
        if not filename:
            return False
        path = Path(filename)
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            QMessageBox.critical(self.window, 'Could not open design', str(error))
            return False
        self.install_design(path, text)
        return True

    def with_extension(self, path):
        if not path.suffix:
            path = path.with_suffix('.vhd')
            # The native dialog checked the entered name, not this amended one.
            if path.exists() and QMessageBox.question(self.window, 'Replace file?', f'Replace {path.name}?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return None
        return path

    def create_testbench(self):
        window = self.window
        source = window.code_page.editors[0].toPlainText()
        names = entity_names(source)
        selected = window.sidebar.entity.text().strip()
        try:
            if len(names) > 1:
                initial = next((index for index, name in enumerate(names) if name.lower() == selected.lower()), 0)
                selected, accepted = QInputDialog.getItem(window, 'Choose entity', 'Entity to instantiate', names, initial, False)
                if not accepted:
                    return False
            else:
                selected = names[0] if names else None
            entity = parse_entity(source, selected)
            text = testbench_template(entity)
        except ValueError as error:
            QMessageBox.warning(window, 'Cannot create testbench', str(error))
            return False

        # A design must have a filename before its sibling _TB filename is known.
        window.code_page.code_tabs.setCurrentIndex(0)
        if window.paths[0] is None and not window.save_as():
            return False
        target = testbench_path(window.paths[0])
        if target.resolve() == window.paths[0].resolve():
            QMessageBox.warning(window, 'Cannot create testbench', 'The testbench path resolves to the design file. Choose a different design filename.')
            return False
        window.code_page.code_tabs.setCurrentIndex(1)
        if not window.confirm_discard():
            return False
        if target.exists():
            choice = QMessageBox.question(window, 'Replace existing testbench?',
                f'{target.name} already exists. Replace it with a new generated template?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if choice != QMessageBox.StandardButton.Yes:
                return False
        if not window.documents.write_text(target, text):
            return False
        window.paths[1] = target
        window.code_page.editors[1].setPlainText(text)
        window.code_page.editors[1].document().setModified(False)
        window.sidebar.entity.setText(entity.name)
        window.sidebar.testbench.setText(entity.name + '_TB')
        window.update_title()
        window.switch_mode(0)
        window.statusBar().showMessage(f'Created {target.name}. Add stimulus in the testbench process.', 7000)
        return True
