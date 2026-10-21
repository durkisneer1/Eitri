"""Keep Qt alive until test widgets and deferred deletions are cleaned up."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope='session', autouse=True)
def qt_application_lifetime():
    app = QApplication.instance() or QApplication([])
    yield app
    # processEvents alone does not deliver DeferredDelete outside an event loop.
    # Destroy surviving test windows while QApplication is still fully alive,
    # rather than relying on Python/Qt's interpreter-shutdown destruction order.
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
