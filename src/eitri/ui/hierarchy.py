"""Interactive source hierarchy: expand instances, inspect wiring, open source."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPen, QPainterPath, QFont
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QPushButton, QSplitter, QTextBrowser, QFileDialog, QGraphicsRectItem, QGraphicsTextItem)
from .circuit import SchematicView


class ComponentCard(QGraphicsRectItem):
    def __init__(self, page, node, x, y):
        super().__init__(0, 0, 248, 92)
        self.page, self.node = page, node
        self.setPos(x, y)
        self.setBrush(QColor('#3c4a50' if not node.get('error') else '#623f38'))
        self.setPen(QPen(QColor('#a4b2b7'), 1.4))
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable)
        self.setToolTip(node['key'] + ' : ' + node['entity'] + '\nDouble-click to expand/collapse. Select to inspect connections.')
        title = QGraphicsTextItem(node['label'], self)
        title.setDefaultTextColor(QColor('#eee7da'))
        font = QFont()
        font.setPointSize(12)
        title.setFont(font)
        title.setPos(12, 7)
        title.setTextWidth(224)
        detail = QGraphicsTextItem(node['entity'] + ('  ▸' if node['key'] in page.collapsed else '  ▾') if node.get('children') else node['entity'], self)
        detail.setDefaultTextColor(QColor('#c4b48e'))
        detail.setPos(12, 43)
        detail.setTextWidth(224)
        self.text_items = (title, detail)  # Keep Python-owned graphics children alive.
        for item in self.text_items:
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.page.inspect(self.node)

    def mouseDoubleClickEvent(self, event):
        if self.node.get('children'):
            key = self.node['key']
            if key in self.page.collapsed:
                self.page.collapsed.remove(key)
            else:
                self.page.collapsed.add(key)
            self.page.draw()
        else:
            self.page.open_definition()
        event.accept()


class HierarchyPage(QWidget):
    source_requested = Signal(str, int)
    circuit_requested = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.project = None
        self.root_node = None
        self.selected = None
        self.collapsed = set()
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel('Hierarchy'))
        self.top = QComboBox()
        self.top.setMinimumContentsLength(10)
        self.top.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.top.currentIndexChanged.connect(self.rebuild)
        row.addWidget(self.top, 1)
        for title, callback in (('+', lambda: self.view.zoom_by(1.3)), ('−', lambda: self.view.zoom_by(1 / 1.3)),
                                ('Fit', lambda: self.view.fit()), ('Expand all', self.expand_all), ('Export…', self.export_svg)):
            b = QPushButton(title)
            b.clicked.connect(callback)
            row.addWidget(b)
        layout.addLayout(row)
        self.note = QLabel('Source structure, not elaborated hardware. Select a card to inspect its port map; double-click to expand.')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        split = QSplitter()
        self.view = SchematicView()
        split.addWidget(self.view)
        details = QWidget()
        self.inspector = details
        side = QVBoxLayout(details)
        self.details = QTextBrowser()
        self.details.setPlaceholderText('Select a component to see its definition, instance location and connections.')
        side.addWidget(self.details)
        for title, callback in (('Open definition', self.open_definition), ('Open instance / wiring', self.open_instance),
                                ('Generate component circuit', self.generate_circuit)):
            b = QPushButton(title)
            b.clicked.connect(callback)
            side.addWidget(b)
        split.addWidget(details)
        split.setSizes([800, 280])
        details.hide()
        layout.addWidget(split, 1)

    def set_project(self, project):
        self.project = project
        previous = self.top.currentData()
        self.top.blockSignals(True)
        self.top.clear()
        for target in project.targets('circuit'):
            self.top.addItem(f'{target.library}.{target.entity} ({target.architecture})', (target.entity, target.library, target.architecture))
        index = self.top.findData(previous)
        if index >= 0:
            self.top.setCurrentIndex(index)
        self.top.blockSignals(False)
        self.rebuild()

    def rebuild(self, *_):
        if not self.project or not self.top.currentData():
            self.view.scene().clear()
            return
        count = [0]
        def node(entity, library, architecture, label, key, ancestors, parent=None, instance=None):
            count[0] += 1
            result = dict(entity=f'{library}.{entity}', label=label, key=key, children=[], parent=parent, instance=instance)
            try:
                unit, arch = self.project.resolve(entity, library, architecture)
                result.update(unit=unit, architecture=arch)
                identity = (unit.key, arch.name.lower())
                if identity in ancestors:
                    raise ValueError('Recursive component reference — expansion stopped.')
                if count[0] > 400 or len(ancestors) > 24:
                    raise ValueError('Display limit reached. Choose a smaller root to explore this branch.')
                for inst in arch.instances:
                    lib = library if inst.library.lower() == 'work' else inst.library.lower()
                    result['children'].append(node(inst.entity, lib, inst.architecture, inst.name,
                        key + '/' + inst.name, ancestors + (identity,), arch, inst))
            except ValueError as error:
                result['error'] = str(error)
            return result
        entity, library, architecture = self.top.currentData()
        self.root_node = node(entity, library, architecture, entity, entity, ())
        self.selected = None
        self.details.clear()
        self.draw()

    def draw(self):
        scene = self.view.scene()
        scene.clear()
        if not self.root_node:
            return
        def width(node):
            children = [] if node['key'] in self.collapsed else node['children']
            node['span'] = max(280, sum(width(child) for child in children))
            return node['span']
        width(self.root_node)
        def place(node, left, depth):
            x, y = left + (node['span'] - 248) / 2, depth * 160
            scene.addItem(ComponentCard(self, node, x, y))
            if node['key'] not in self.collapsed:
                offset = left
                for child in node['children']:
                    cx = offset + child['span'] / 2
                    path = QPainterPath()
                    path.moveTo(x + 124, y + 92)
                    path.lineTo(x + 124, y + 122)
                    path.lineTo(cx, y + 122)
                    path.lineTo(cx, y + 160)
                    edge = scene.addPath(path, QPen(QColor('#bfa779'), 1.5))
                    edge.setZValue(-1)
                    place(child, offset, depth + 1)
                    offset += child['span']
        place(self.root_node, 0, 0)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self.view.fit()

    def export_svg(self):
        if not self.root_node:
            return
        filename, _ = QFileDialog.getSaveFileName(self, 'Export component hierarchy', 'component-hierarchy.svg', 'SVG image (*.svg)')
        if not filename:
            return
        from PySide6.QtSvg import QSvgGenerator
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QSize, QRectF
        import math
        bounds = self.view.scene().sceneRect()
        generator = QSvgGenerator()
        generator.setFileName(filename)
        generator.setSize(QSize(math.ceil(bounds.width()), math.ceil(bounds.height())))
        target = QRectF(0, 0, bounds.width(), bounds.height())
        generator.setViewBox(target)
        generator.setTitle('Eitri component hierarchy')
        with QPainter(generator) as painter:
            painter.fillRect(target, QColor('#242423'))
            self.view.scene().render(painter, target, bounds)

    def expand_all(self):
        self.collapsed.clear()
        self.draw()

    def inspect(self, node):
        self.selected = node
        self.inspector.show()
        text = f'Instance path\n{node["key"]}\n\nDesign\n{node["entity"]}'
        if 'unit' in node:
            text += f'\n\nDefinition\n{self.project.relative(node["unit"].path)}:{node["unit"].line + 1}\n\nArchitecture\n{node["architecture"].name}'
        if node.get('instance'):
            inst = node['instance']
            text += f'\n\nInstantiation\n{self.project.relative(node["parent"].path)}:{inst.line + 1}\n\nConnections / generic map\n{inst.associations or "No port associations."}'
        if node.get('error'):
            text += '\n\nNeeds attention\n' + node['error']
        text += '\n\nGenerate statements are shown as source instances; conditions and replication are resolved during compilation.'
        self.details.setPlainText(text)

    def open_definition(self):
        if self.selected and 'unit' in self.selected:
            unit = self.selected['unit']
            self.source_requested.emit(unit.path, unit.line)

    def open_instance(self):
        if self.selected and self.selected.get('instance'):
            self.source_requested.emit(self.selected['parent'].path, self.selected['instance'].line)

    def generate_circuit(self):
        if self.selected and 'unit' in self.selected:
            unit = self.selected['unit']
            self.circuit_requested.emit(unit.name, unit.library, self.selected['architecture'].name)
