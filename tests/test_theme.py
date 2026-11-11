"""Live theme changes cover existing/custom surfaces and persist on restart."""
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette
from eitri.ui.theme import apply_theme, current_mode, theme_color
from eitri.ui.window import Workspace


def test_live_theme_and_saved_preference(tmp_path, monkeypatch, qt_application_lifetime):
    app = qt_application_lifetime
    import eitri.ui.window as window_module
    settings = QSettings(str(tmp_path / 'appearance.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr(window_module, 'QSettings', lambda *args: settings)
    window = Workspace(run_root=tmp_path / 'runs')
    try:
        window.show()
        app.processEvents()
        assert current_mode() == 'Dark'
        window.editor.setPlainText('entity example is end; -- a comment')
        window.editor.document().setModified(False)
        old_color = window.editor.highlighter.styles['keyword'].foreground().color().name()
        svg = tmp_path / 'sample.svg'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"><rect width="300" height="100" fill="#242423"/><text x="10" y="30" fill="#eee7da">Circuit</text></svg>')
        window.circuit_page.view.load_svg(svg)
        window.circuit_page.view.zoom_by(1.4)
        transform = window.circuit_page.view.transform()
        original = svg.read_bytes()
        from eitri.backend.project import Project
        from eitri.ui.hierarchy import ComponentCard
        window.hierarchy_page.set_project(Project(Path(__file__).parents[1] / 'examples/learning_cpu'))
        card = next(item for item in window.hierarchy_page.view.scene().items() if isinstance(item, ComponentCard))
        card.setSelected(True)
        hierarchy_transform = window.hierarchy_page.view.transform()
        window.theme_toggle.click()
        app.processEvents()
        assert current_mode() == 'Light'
        assert settings.value('appearance') == 'Light'
        assert app.palette().color(QPalette.ColorRole.Text).lightness() < 100
        assert window.editor.highlighter.styles['keyword'].foreground().color().name() != old_color
        assert window.circuit_page.view.backgroundBrush().color().name() == theme_color('#242423')
        assert window.circuit_page.view.transform() == transform
        assert svg.read_bytes() == original
        assert card.isSelected()
        assert card.brush().color().name() == theme_color('#3c4a50')
        assert window.hierarchy_page.view.transform() == hierarchy_transform
        from PySide6.QtWidgets import QFileDialog
        exported = tmp_path / 'export.svg'
        monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(exported), ''))
        window.circuit_page.svg_file = svg
        window.circuit_page.export_svg()
        assert 'fill="' + theme_color('#242423') + '"' in exported.read_text()
        assert svg.read_bytes() == original
        window.documents.add()
        assert window.editor.highlighter.styles['keyword'].foreground().color().name() == theme_color('#bba7c4')
        assert window.theme_toggle.text() == 'Dark mode'
        # A second workspace loads the preference without resetting it.
        second = Workspace(run_root=tmp_path / 'second')
        assert current_mode() == 'Light'
        second.close()
        second.deleteLater()
        svg.unlink()  # Theme switching must not depend on retained run files.
        window.theme_toggle.click()
        assert current_mode() == 'Dark'
    finally:
        window.close()
        window.deleteLater()
        apply_theme('Dark')
