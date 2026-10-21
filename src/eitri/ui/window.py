"""Folder workspace with persistent documents and independent run targets."""
from dataclasses import replace
from pathlib import Path
import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMainWindow, QMessageBox, QSplitter, QStackedWidget, QVBoxLayout, QWidget, QDialog
from eitri.backend.project import Project
from .actions import install_actions
from .app_icon import application_icon
from .code_page import CodePage
from .documents import DocumentController
from .design_flow import DesignFlow
from .simulation import SimulationPage
from .circuit import CircuitPage
from .hierarchy import HierarchyPage
from .tool_controller import ToolController
from .sidebar import Sidebar
from .sizing import fit_window
from .theme import workspace_style
from .fonts import configure_application_font
from .toolbar import Toolbar
from .widgets import label


class Workspace(QMainWindow):
    def __init__(self, run_root=None):
        super().__init__()
        app = QApplication.instance()
        if app:
            configure_application_font(app)
            app.setWindowIcon(application_icon())
        self.setWindowIcon(application_icon())
        self.setStyleSheet(workspace_style())
        self.project = None
        self.refreshing = False
        self.rendered_revision = -1
        self.code_page = CodePage()
        self.documents = DocumentController(self)
        self.design_flow = DesignFlow(self)
        self.toolbar = Toolbar()
        self.sidebar = Sidebar()
        self.views = QStackedWidget()
        self.simulation_page = SimulationPage()
        self.circuit_page = CircuitPage()
        self.hierarchy_page = HierarchyPage()
        for page in (self.code_page, self.simulation_page, self.circuit_page, self.hierarchy_page):
            self.views.addWidget(page)
        self.views.setMinimumWidth(480)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.toolbar)
        left_layout.addWidget(self.sidebar, 1)
        self.left_column = left
        self.splitter = QSplitter()
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.views)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([310, 900])
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)
        self.page_name = label('Open a folder to start')
        self.position = label('')
        self.page_name.hide()
        self.statusBar().addPermanentWidget(self.position)
        self.tools = ToolController(self, run_root)
        from .language_server import EditorAssistance
        self.assistance = EditorAssistance(self)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(450)
        self.refresh_timer.timeout.connect(self.refresh_project)
        self.disk_timer = QTimer(self)
        self.disk_timer.setInterval(2000)
        self.disk_timer.timeout.connect(self.poll_files)
        self.disk_timer.start()
        self.toolbar.mode_changed.connect(self.switch_mode)
        self.sidebar.open_folder_requested.connect(self.choose_folder)
        self.sidebar.new_requested.connect(self.new_file)
        self.sidebar.save_requested.connect(self.save)
        self.sidebar.source_requested.connect(self.documents.load)
        self.sidebar.file_action.connect(self.file_action)
        self.sidebar.run_all_requested.connect(self.tools.run_all)
        self.sidebar.test_result_requested.connect(self.tools.open_result)
        self.sidebar.save_target_requested.connect(self.configure_target)
        self.sidebar.standard.currentTextChanged.connect(self.standard_changed)
        for kind, combo in self.sidebar.targets.items():
            combo.currentIndexChanged.connect(lambda _, k=kind: self.target_changed(k))
        self.code_page.code_tabs.currentChanged.connect(self.active_document_changed)
        self.code_page.create_testbench_requested.connect(self.design_flow.create_testbench)
        self.code_page.insert_instance_requested.connect(self.design_flow.insert_instance)
        self.code_page.message.connect(self.statusBar().showMessage)
        self.code_page.reload_button.clicked.connect(self.documents.reload_active)
        self.code_page.keep_button.clicked.connect(self.documents.keep_active)
        self.hierarchy_page.source_requested.connect(self.documents.load)
        self.hierarchy_page.circuit_requested.connect(self.component_circuit)
        self.documents.add()
        install_actions(self)
        fit_window(self)
        # fit_window keeps the workspace within the available screen bounds.

    @property
    def editor(self):
        return self.code_page.editor

    @property
    def path(self):
        return self.documents.active.path if self.documents.active else None

    @property
    def paths(self):
        return [d.path for d in self.documents.records]

    def connect_editor(self, editor):
        editor.cursorPositionChanged.connect(self.update_position)
        editor.document().modificationChanged.connect(self.update_title)
        editor.textChanged.connect(self.source_changed)

    def source_changed(self):
        self.update_title()
        self.tools.mark_stale()
        self.refresh_timer.start()

    def choose_folder(self):
        options = QFileDialog.Option.ShowDirsOnly
        if sys.platform == 'darwin':
            # Avoid the native macOS panel's folder-selection problems.
            options |= QFileDialog.Option.DontUseNativeDialog
        folder = QFileDialog.getExistingDirectory(
            self, 'Open VHDL project folder',
            str(self.project.root) if self.project else str(Path.home()), options)
        return self.open_folder(Path(folder)) if folder else False

    def open_folder(self, root):
        if self.tools.running:
            QMessageBox.information(self, 'Run in progress', 'Stop the current run before switching project folders.')
            return False
        try:
            project = Project(root)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.warning(self, 'Cannot open project', str(error))
            return False
        if not self.documents.confirm_all():
            return False
        self.assistance.restart()
        self.documents.clear()
        self.project = project
        for combo in self.sidebar.targets.values():
            combo.blockSignals(True)
            combo.clear()
            combo.blockSignals(False)
        self.sidebar.tests.clear()
        self.tools.results.clear()
        self.tools.requests.clear()
        self.rendered_revision = -1
        self.sidebar.standard.blockSignals(True)
        self.sidebar.standard.setCurrentText(project.config['standard'])
        self.sidebar.standard.blockSignals(False)
        self.documents.add()
        self.refresh_project(force=True)
        # Restore the last edited file without forcing a design/testbench pair.
        last = project.config.get('active_file')
        if last and str((project.root / last).resolve()) in project.sources:
            self.load(project.root / last)
        self.statusBar().showMessage(f'Opened {project.root.name}. Choose a file or a run target.', 6000)
        return True

    def refresh_project(self, force=False):
        if not self.project or self.refreshing:
            return
        self.refreshing = True
        try:
            changed = self.project.refresh(self.documents.overlays())
            if self.project.revision != self.rendered_revision or force:
                self.rendered_revision = self.project.revision
                dirty = [str(d.path) for d in self.documents.records if d.editor.document().isModified()]
                self.sidebar.set_project(self.project, dirty)
                self.refresh_targets()
                self.hierarchy_page.set_project(self.project)
                self.tools.mark_stale()
                self.assistance.schedule()
            if self.project.issues:
                self.statusBar().showMessage(self.project.issues[0], 8000)
        except (OSError, ValueError) as error:
            self.statusBar().showMessage(str(error), 8000)
        finally:
            self.refreshing = False

    def poll_files(self):
        if self.project:
            changed = self.documents.check_external()
            self.refresh_project(force=changed)

    def refresh_targets(self):
        for kind, combo in self.sidebar.targets.items():
            current = combo.currentData()
            remembered = self.project.config.get('selected_' + kind)
            combo.blockSignals(True)
            combo.clear()
            selected = 0
            for target in self.project.targets(kind):
                if current and (current.name, current.entity, current.architecture, current.library) == (target.name, target.entity, target.architecture, target.library):
                    target = current
                    selected = combo.count()
                elif not current and target.name == remembered:
                    selected = combo.count()
                combo.addItem(target.name, target)
            combo.setCurrentIndex(selected if combo.count() else -1)
            combo.blockSignals(False)
            if not current:
                self.target_changed(kind)

    def target_changed(self, kind):
        target = self.sidebar.targets[kind].currentData()
        if target:
            if self.project:
                self.project.config['selected_' + kind] = target.name
            if kind == 'simulation':
                self.sidebar.stop_time.setText(target.stop_time)
                self.sidebar.wave_format.setCurrentText(target.wave_format)
            else:
                self.sidebar.circuit_detail.setCurrentText(target.circuit_detail)
        self.tools.mark_stale()

    def selected_target(self, kind):
        target = self.sidebar.targets[kind].currentData()
        if not target:
            raise ValueError('Choose a ' + kind + ' target. Right-click a source file to select one.')
        if kind == 'simulation':
            return replace(target, stop_time=self.sidebar.stop_time.text().replace(' ', ''), wave_format=self.sidebar.wave_format.currentText())
        return replace(target, circuit_detail=self.sidebar.circuit_detail.currentText())

    def persist_target(self, target):
        if not self.project:
            return
        try:
            combo = self.sidebar.targets[target.kind]
            if combo.currentData() and combo.currentData().name == target.name:
                self.project.config['selected_' + target.kind] = target.name
            self.project.save_target(target)
            if combo.currentData() and combo.currentData().name == target.name:
                combo.setItemData(combo.currentIndex(), target)
        except OSError as error:
            self.statusBar().showMessage(f'Could not save target settings: {error}', 7000)

    def configure_target(self, kind):
        from .target_dialog import TargetDialog
        try:
            target = self.selected_target(kind)
        except ValueError as error:
            self.statusBar().showMessage(str(error), 6000)
            return
        dialog = TargetDialog(target, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.persist_target(dialog.target)
            self.refresh_targets()
            combo = self.sidebar.targets[kind]
            combo.setCurrentIndex(next(i for i in range(combo.count()) if combo.itemData(i).name == dialog.target.name))

    def standard_changed(self, standard):
        if self.project:
            self.project.config['standard'] = standard
            try:
                self.project.save_config()
            except OSError as error:
                self.statusBar().showMessage(str(error), 7000)
        self.tools.mark_stale()

    def select_file_target(self, kind, path, run=True):
        if not self.project:
            return False
        self.refresh_project()
        from eitri.backend.project import Target
        candidates = [t for t in self.project.targets(kind) if (self.project.root / t.path).resolve() == Path(path).resolve()]
        # Allow explicit simulation of an entity with ports; GHDL diagnoses invalid tops.
        if not candidates and kind == 'simulation':
            candidates = [replace(t, kind='simulation') for t in self.project.targets('circuit') if (self.project.root / t.path).resolve() == Path(path).resolve()]
        if not candidates:
            QMessageBox.information(self, 'No runnable entity', 'Choose a file declaring an entity with an architecture. Packages are compiled automatically as dependencies.')
            return False
        selected = candidates[0]
        if len(candidates) > 1:
            labels = [f'{t.name} — {t.library}.{t.entity} ({t.architecture})' for t in candidates]
            value, accepted = QInputDialog.getItem(self, 'Choose run target', 'Entity / architecture', labels, 0, False)
            if not accepted:
                return False
            selected = candidates[labels.index(value)]
        self.persist_target(selected)
        self.refresh_targets()
        combo = self.sidebar.targets[kind]
        for i in range(combo.count()):
            if combo.itemData(i).name == selected.name:
                combo.setCurrentIndex(i)
                break
        if run:
            self.tools.start(kind)
        return True

    def file_action(self, action, path):
        if action in ('simulation', 'circuit'):
            self.select_file_target(action, path)
        elif action == 'instance':
            self.design_flow.insert_instance(path)
        else:
            self.load(Path(path))
            if action == 'testbench':
                self.design_flow.create_testbench()

    def component_circuit(self, entity, library, architecture):
        from eitri.backend.project import Target
        unit, arch = self.project.resolve(entity, library, architecture)
        target = Target(entity + ' component', 'circuit', entity, self.project.relative(unit.path), library, arch.name)
        self.tools.start('circuit', target=target)

    def active_document_changed(self, *_):
        self.update_title()
        self.update_position()
        self.documents.refresh_conflict()
        if self.editor:
            self.editor.setFocus()

    def update_title(self, *_):
        if not self.editor:
            return
        name = self.project.relative(self.path) if self.project and self.path else (self.path.name if self.path else 'Untitled.vhd')
        dirty = ' •' if self.editor.document().isModified() else ''
        self.code_page.document_name.setText(name + dirty + (' · read only' if self.editor.isReadOnly() else ''))
        self.setWindowTitle(f'{name}{dirty} — {self.project.root.name + " — " if self.project else ""}Eitri')
        self.code_page.create_testbench.setEnabled(bool(self.editor.toPlainText().strip()) and not self.editor.isReadOnly())

    def update_position(self):
        if self.editor:
            c = self.editor.textCursor()
            self.position.setText(f'Ln {c.blockNumber() + 1}, Col {c.positionInBlock() + 1} · VHDL')

    def switch_mode(self, index):
        self.views.setCurrentIndex(index)
        self.sidebar.options.setCurrentIndex(index)
        self.toolbar.mode_buttons.button(index).setChecked(True)
        self.page_name.setText(('Code', 'Simulation', 'Circuit diagram', 'Component hierarchy')[index])

    def load(self, path):
        return self.documents.load(path)

    def new_file(self):
        return self.design_flow.new_design()

    def open_file(self):
        return self.documents.open_file()

    def save(self):
        return self.documents.save()

    def save_as(self):
        return self.documents.save_as()

    def write(self, path):
        return self.documents.write(path)

    def confirm_discard(self):
        return self.documents.confirm_discard()

    def show_find(self):
        self.switch_mode(0)
        self.code_page.show_find()

    def quick_open(self):
        if not self.project:
            return
        files = sorted(self.project.relative(p) for p in self.project.sources)
        filename, accepted = QInputDialog.getItem(self, 'Quick open', 'File', files, 0, True)
        if accepted and filename in files:
            self.load(self.project.root / filename)

    def closeEvent(self, event):
        if not self.tools.prepare_close() or not self.documents.confirm_all():
            event.ignore()
            return
        if self.project:
            self.project.config['active_file'] = self.project.relative(self.path) if self.path else ''
            try:
                self.project.save_config()
            except OSError:
                pass
        self.tools.wave_timer.stop()
        self.tools.save_signals()
        self.disk_timer.stop()
        self.refresh_timer.stop()
        self.assistance.close()
        event.accept()


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Eitri')
    app.setOrganizationName('Eitri')
    app.setStyle('Fusion')
    window = Workspace()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
