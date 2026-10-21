"""Project explorer, source hierarchy and explicit run target settings."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QLineEdit, QComboBox, QStackedWidget, QSplitter, QMenu,
    QScrollArea, QFrame, QLayout)
from .widgets import button, label, field


class Sidebar(QScrollArea):
    open_folder_requested = Signal()
    new_requested = Signal()
    save_requested = Signal()
    source_requested = Signal(str, int)
    file_action = Signal(str, str)
    save_target_requested = Signal(str)
    run_all_requested = Signal()
    test_result_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(270)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(12, 8, 12, 8)
        row = QHBoxLayout()
        row.addWidget(button('Open folder…', self.open_folder_requested.emit))
        row.addWidget(button('New…', self.new_requested.emit))
        row.addWidget(button('Save', self.save_requested.emit))
        layout.addLayout(row)
        self.project_name = label('No folder open', 'eyebrow')
        self.project_name.setWordWrap(True)
        layout.addWidget(self.project_name)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText('Filter files…')
        self.filter.textChanged.connect(self.filter_files)
        layout.addWidget(self.filter)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        self.explorer_tabs = QTabWidget()
        self.explorer_tabs.setMinimumHeight(160)
        self.files = QTreeWidget()
        self.files.setHeaderHidden(True)
        self.files.itemActivated.connect(self.activate)
        self.files.itemClicked.connect(self.activate)
        self.files.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.files.customContextMenuRequested.connect(self.file_menu)
        self.hierarchy = QTreeWidget()
        self.hierarchy.setHeaderHidden(True)
        self.hierarchy.itemActivated.connect(self.activate)
        self.tests = QTreeWidget()
        self.tests.setHeaderLabels(['Test / target', 'Result'])
        self.tests.itemActivated.connect(lambda item, _: self.test_result_requested.emit(item.data(0, Qt.ItemDataRole.UserRole)))
        self.explorer_tabs.addTab(self.files, 'Files')
        self.explorer_tabs.addTab(self.hierarchy, 'Hierarchy')
        self.explorer_tabs.addTab(self.tests, 'Tests')
        split.addWidget(self.explorer_tabs)
        settings = QWidget()
        form = QVBoxLayout(settings)
        form.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        form.setContentsMargins(0, 4, 0, 0)
        self.standard = QComboBox()
        self.standard.addItems(['VHDL 2008', 'VHDL 2002', 'VHDL 1993'])
        field(form, 'Language standard', self.standard)
        self.options = QStackedWidget()
        code = QWidget()
        code_layout = QVBoxLayout(code)
        code_layout.setContentsMargins(0, 0, 0, 0)
        note = label('Select a file to edit. F5 runs the selected simulation target, even while you edit another component.', 'muted')
        note.setWordWrap(True)
        code_layout.addWidget(note)
        code_layout.addWidget(button('Run all tests', self.run_all_requested.emit))
        self.options.addWidget(code)
        self.targets = {}
        for kind in ('simulation', 'circuit'):
            page = QWidget()
            f = QVBoxLayout(page)
            f.setContentsMargins(0, 0, 0, 0)
            combo = QComboBox()
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            self.targets[kind] = combo
            field(f, 'Simulation target' if kind == 'simulation' else 'Circuit target', combo)
            if kind == 'simulation':
                self.stop_time = field(f, 'Stop time', QLineEdit('200ns'))
                self.wave_format = QComboBox()
                self.wave_format.addItems(['VCD', 'GHW'])
                field(f, 'Waveforms', self.wave_format)
            else:
                self.circuit_detail = QComboBox()
                self.circuit_detail.addItems(['Simple', 'Detailed'])
                field(f, 'Circuit detail', self.circuit_detail)
            f.addWidget(button('Configure / save target…', lambda k=kind: self.save_target_requested.emit(k)))
            self.options.addWidget(page)
        hierarchy_options = QWidget()
        h = QVBoxLayout(hierarchy_options)
        text = label('Explore the source hierarchy. Each box is a component instance; lines show containment. Select a box to inspect its wiring.', 'muted')
        text.setWordWrap(True)
        h.addWidget(text)
        self.options.addWidget(hierarchy_options)
        form.addWidget(self.options)
        split.addWidget(settings)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        split.setSizes([390, 250])
        layout.addWidget(split, 1)
        self.file_path = label('')
        self.file_path.hide()

    def activate(self, item, column=0):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            self.source_requested.emit(*data)

    def set_project(self, project, dirty=()):
        expanded = set()
        def remember(item):
            if item.isExpanded():
                expanded.add(item.toolTip(0))
            for i in range(item.childCount()):
                remember(item.child(i))
        for i in range(self.files.topLevelItemCount()):
            remember(self.files.topLevelItem(i))
        self.project_name.setText(project.root.name)
        self.project_name.setToolTip(str(project.root))
        self.files.clear()
        parents = {'': self.files.invisibleRootItem()}
        for path in sorted(project.sources):
            relative = project.relative(path)
            parts = relative.split('/')
            for index in range(1, len(parts)):
                key = '/'.join(parts[:index])
                if key not in parents:
                    parents[key] = QTreeWidgetItem(parents['/'.join(parts[:index - 1])], [parts[index - 1]])
                    parents[key].setToolTip(0, key)
                    parents[key].setExpanded(key in expanded or not expanded)
            item = QTreeWidgetItem(parents['/'.join(parts[:-1])], [parts[-1] + (' •' if path in dirty else '')])
            item.setData(0, Qt.ItemDataRole.UserRole, (path, 0))
            item.setToolTip(0, relative)
        self.filter_files(self.filter.text())
        self.hierarchy.clear()
        def add(parent, entity, library, architecture, label_text, ancestors=()):
            item = QTreeWidgetItem(parent, [label_text])
            try:
                unit, arch = project.resolve(entity, library, architecture)
                item.setData(0, Qt.ItemDataRole.UserRole, (arch.path, arch.line))
                if unit.key in ancestors or len(ancestors) >= 20:
                    item.addChild(QTreeWidgetItem(['Recursive reference']))
                    return
                for inst in arch.instances:
                    add(item, inst.entity, unit.library if inst.library.lower() == 'work' else inst.library,
                        inst.architecture, f'{inst.name} : {inst.entity}', ancestors + (unit.key,))
            except ValueError as error:
                item.setToolTip(0, str(error))
                item.setText(0, label_text + ' ⚠')
        referenced = {i.entity.lower() for u in project.units for i in u.instances}
        roots = [t for t in project.targets('circuit') if t.entity.lower() not in referenced]
        for target in roots or project.targets('circuit'):
            add(self.hierarchy.invisibleRootItem(), target.entity, target.library, target.architecture, target.entity)
        self.hierarchy.expandToDepth(1)

    def filter_files(self, text):
        def visit(item):
            children = [visit(item.child(i)) for i in range(item.childCount())]
            visible = any(children) if children else text.lower() in item.toolTip(0).lower()
            item.setHidden(not visible)
            if text and children:
                item.setExpanded(True)
            return visible
        for i in range(self.files.topLevelItemCount()):
            visit(self.files.topLevelItem(i))

    def file_menu(self, point):
        item = self.files.itemAt(point)
        data = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not data:
            return
        menu = QMenu(self)
        for title, action in (('Open source', 'open'), ('Simulate…', 'simulation'), ('Generate circuit…', 'circuit'), ('Create testbench…', 'testbench'), ('Insert instance into current file…', 'instance')):
            menu.addAction(title, lambda checked=False, a=action: self.file_action.emit(a, data[0]))
        menu.exec(self.files.viewport().mapToGlobal(point))
