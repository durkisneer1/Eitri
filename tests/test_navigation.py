"""Trackpad input should pan smoothly; only pinching changes circuit scale."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QNativeGestureEvent, QPointingDevice, QWheelEvent
from PySide6.QtWidgets import QApplication
from eitri.ui.circuit import SchematicView
from eitri.ui.waveform import WaveformView


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def wheel(view, pixels, angles=QPoint(), phase=Qt.ScrollPhase.ScrollUpdate):
    event = QWheelEvent(QPointF(100, 100), QPointF(100, 100), pixels, angles,
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        phase, False)
    QApplication.sendEvent(view.viewport(), event)


@pytest.mark.parametrize('view_class', [SchematicView, WaveformView])
def test_trackpad_pans_both_axes_without_zoom(app, view_class):
    view = view_class()
    view.resize(600, 400)
    if isinstance(view, SchematicView):
        view.scene().setSceneRect(0, 0, 4000, 4000)
        scale = view.transform().m11()
    else:
        view.set_data([{'name': str(i), 'width': 1, 'events': [[0, '0']]} for i in range(50)], 100, '1 ns')
        view.zoom_by(4)
        scale = view.zoom
    view.show()
    app.processEvents()
    try:
        h, v = view.horizontalScrollBar(), view.verticalScrollBar()
        h.setValue(200)
        v.setValue(200)
        wheel(view, QPoint(24, -48), QPoint(1, -1))
        assert (h.value(), v.value()) == (176, 248)
        wheel(view, QPoint(-7, 9), phase=Qt.ScrollPhase.ScrollMomentum)
        assert (h.value(), v.value()) == (183, 239)
        wheel(view, QPoint(), phase=Qt.ScrollPhase.ScrollEnd)
        assert (h.value(), v.value()) == (183, 239)
        assert (view.transform().m11() if isinstance(view, SchematicView) else view.zoom) == scale
    finally:
        view.close()


def test_native_pinch_zoom_uses_incremental_magnification(app):
    view = SchematicView()
    view.scene().setSceneRect(0, 0, 4000, 4000)
    view.show()
    app.processEvents()
    try:
        before = view.transform().m11()
        for kind, value in ((Qt.NativeGestureType.BeginNativeGesture, 0),
                            (Qt.NativeGestureType.ZoomNativeGesture, .02),
                            (Qt.NativeGestureType.EndNativeGesture, 0)):
            event = QNativeGestureEvent(kind, QPointingDevice.primaryPointingDevice(), 2,
                                        QPointF(100, 100), QPointF(100, 100), QPointF(100, 100),
                                        value, QPointF())
            QApplication.sendEvent(view.viewport(), event)
        assert view.transform().m11() == pytest.approx(before * 1.02)
    finally:
        view.close()


def test_waveform_mouse_wheel_moves_signal_rows(app):
    view = WaveformView()
    view.resize(600, 400)
    view.set_data([{'name': str(i), 'width': 1, 'events': []} for i in range(50)], 100, '1 ns')
    view.show()
    app.processEvents()
    try:
        view.verticalScrollBar().setValue(500)
        wheel(view, QPoint(), QPoint(0, -120), Qt.ScrollPhase.NoScrollPhase)
        assert view.verticalScrollBar().value() - 500 == QApplication.wheelScrollLines() * view.ROW
    finally:
        view.close()
