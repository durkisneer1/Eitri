"""Vector schematic viewer with pan/zoom and export controls."""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QHBoxLayout, QPushButton
from .job_page import JobPage
from .fonts import monospace_family
from eitri.backend.schematic_theme import CANVAS


class SchematicView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        # Match the SVG canvas so zooming and panning have no visible seam.
        self.setBackgroundBrush(QColor(CANVAS))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumHeight(100)

    def load_svg(self, path):
        # netlistsvg font-family lists are misread as one name by Qt SVG.
        # Resolve a local font for the preview; leave exported SVG unchanged.
        import xml.etree.ElementTree as ET
        root = ET.parse(path).getroot()
        family = monospace_family()
        for element in root.iter():
            if 'font-family' in element.attrib:
                element.set('font-family', family)
            if 'font-family' in element.get('style', ''):
                import re
                element.set('style', re.sub(r'font-family\s*:[^;]+', 'font-family:' + family, element.get('style')))
        item = QGraphicsSvgItem()
        renderer = QSvgRenderer(ET.tostring(root), item)
        item.setSharedRenderer(renderer)
        if not item.renderer().isValid():
            raise ValueError('The generated SVG could not be rendered.')
        self.scene().clear()
        self.scene().addItem(item)
        self.scene().setSceneRect(item.boundingRect().adjusted(-20, -20, 20, 20))
        self.fit()

    def zoom_by(self, factor):
        current = self.transform().m11()
        if 0.001 <= current * factor <= 100:
            self.scale(factor, factor)

    def fit(self):
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        # Trackpad swipes (including momentum) are scrolling, not zooming.
        delta = event.pixelDelta()
        if not delta.isNull():
            for bar, distance in ((self.horizontalScrollBar(), delta.x()),
                                  (self.verticalScrollBar(), delta.y())):
                bar.setValue(bar.value() - distance)
            event.accept()
        else:
            super().wheelEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.NativeGesture:
            kind = event.gestureType()
            if kind == Qt.NativeGestureType.ZoomNativeGesture:
                self.zoom_by(1 + event.value())
                event.accept()
                return True
            if kind in (Qt.NativeGestureType.BeginNativeGesture,
                        Qt.NativeGestureType.EndNativeGesture):
                event.accept()
                return True
        return super().viewportEvent(event)


class CircuitPage(JobPage):
    def __init__(self, parent=None):
        super().__init__('Generate circuit', parent)
        self.svg_file = None
        self.view = SchematicView()
        # These controls transform the view, leaving exported SVG data unchanged.
        tools = QHBoxLayout()
        for text, callback in (('+', lambda: self.view.zoom_by(1.4)), ('−', lambda: self.view.zoom_by(1 / 1.4)), ('Fit', self.view.fit)):
            item = QPushButton(text)
            item.clicked.connect(callback)
            tools.addWidget(item)
        tools.addStretch()
        self.save_svg = QPushButton('Export SVG…')
        self.save_svg.setEnabled(False)
        self.save_svg.clicked.connect(self.export_svg)
        tools.addWidget(self.save_svg)
        self.result_layout.addLayout(tools)
        self.result_layout.addWidget(self.view, 1)

    def load_result(self, directory, result):
        path = directory / result['svg']
        self.view.load_svg(path)
        self.svg_file = path
        self.save_svg.setEnabled(True)
        self.has_result = True
        self.status.setText(f'{result["top"]} · {result.get("detail", "Detailed")} · {result["cells"]} cells · {result["ports"]} ports. Drag or scroll to pan; pinch or use +/− to zoom.')

    def export_svg(self):
        if self.svg_file:
            self.export_file(self.svg_file, 'Export circuit schematic', 'SVG image (*.svg)')
