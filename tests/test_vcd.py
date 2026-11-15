"""Regression coverage for VHDL std_logic states in waveform previews."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from eitri.backend.vcd import format_value, parse_vcd
from eitri.ui.simulation import SimulationPage
from eitri.ui.waveform import WaveformView


@pytest.mark.parametrize('radix', ['Hex', 'Binary', 'Unsigned'])
@pytest.mark.parametrize('state', ['U', 'X', 'Z', 'W', 'L', 'H', '-'])
def test_logic_states_remain_visible(state, radix):
    assert format_value(state.lower(), 1, radix) == state
    assert format_value(state * 32, 32, radix) == state
    assert format_value('10' + state.lower() + '0', 4, radix) == '10' + state + '0'


@pytest.mark.parametrize('radix,expected', [('Hex', '0A'), ('Binary', '00001010'), ('Unsigned', '10')])
def test_binary_values_still_convert(radix, expected):
    assert format_value('1010', 8, radix) == expected
    assert format_value('1', 1, radix) == '1'


def test_parser_preserves_scalar_and_vector_logic_states(tmp_path):
    path = tmp_path / 'logic.vcd'
    header = '$var wire 1 ! scalar $end\n$var wire 4 " bus $end\n$enddefinitions $end\n'
    states = 'uxzwlh-01'
    path.write_text(header + ''.join(f'#{i}\n{s}!\nb{s * 4} "\n' for i, s in enumerate(states)))
    scalar, bus = parse_vcd(path)['signals']
    assert scalar['events'] == [[i, s.upper()] for i, s in enumerate(states)]
    assert bus['events'] == [[i, s.upper() * 4] for i, s in enumerate(states)]


def test_uninitialized_ram_cursor_and_paint(tmp_path):
    import json
    app = QApplication.instance() or QApplication([])
    page = SimulationPage()
    data = {'signals': [{'name': 'ram.data[31:0]', 'width': 32,
                         'events': [[0, 'U' * 32], [10, '1' * 32]]}],
            'end_time': 20, 'timescale': '1 ns'}
    (tmp_path / 'wave.json').write_text(json.dumps(data))
    page.load_result(tmp_path, {'waveform': 'wave.json', 'wave_file': 'wave.vcd', 'signals': 1})
    image = QImage(800, 200, QImage.Format.Format_ARGB32)
    try:
        for radix in ('Hex', 'Binary', 'Unsigned'):
            page.radix.setCurrentText(radix)
            page.update_values(0)
            assert page.signals.topLevelItem(0).text(1) == 'U'
            with QPainter(image) as painter:
                page.wave._paint_waveform(painter)
            page.update_values(10)
            assert page.signals.topLevelItem(0).text(1) == format_value('1' * 32, 32, radix)
        assert not page.signals.signalsBlocked()
    finally:
        page.close()
        app.processEvents()


def test_painter_cleanup_on_render_failure(monkeypatch):
    app = QApplication.instance() or QApplication([])
    view = WaveformView()
    view.set_data([{'name': 'ram.data', 'width': 32, 'events': [[0, 'U' * 32]]}], 20, '1 ns')
    image = QImage(800, 200, QImage.Format.Format_ARGB32)
    painters = []

    def create_painter(_):
        painter = QPainter(image)
        painters.append(painter)
        return painter

    def fail(*args):
        raise RuntimeError('render failure')

    monkeypatch.setattr('eitri.ui.waveform.QPainter', create_painter)
    monkeypatch.setattr('eitri.ui.waveform.format_value', fail)
    try:
        with pytest.raises(RuntimeError, match='render failure'):
            view.paintEvent(None)
        assert not painters[0].isActive()
        with QPainter(image) as painter:
            assert painter.isActive()
    finally:
        view.close()
        app.processEvents()


@pytest.mark.parametrize('timescale,last,stop,expected', [
    ('1 fs', 50_000_000, '60ns', 60_000_000),
    ('10 ps', 5000, '1US', 100_000),
    ('1 ns', 50, '60ns', 60),
    ('10 ns', 5, '55ns', 5.5),
    ('1 ns', 50, '40ns', 50),
])
def test_requested_stop_keeps_final_case_visible(tmp_path, timescale, last, stop, expected):
    from eitri.backend.vcd import value_at
    path = tmp_path / 'final.vcd'
    source = (f'$timescale {timescale} $end\n$var wire 9 ! result $end\n'
              f'$enddefinitions $end\n#0\nb0 !\n#{last}\nb100000001 !\n')
    path.write_text(source, encoding='utf-8')
    original = parse_vcd(path)
    preview = parse_vcd(path, stop_time=stop)
    assert preview['end_time'] == expected
    assert preview['recorded_end_time'] == last
    assert preview['signals'] == original['signals']
    assert value_at(preview['signals'][0], expected) == '100000001'
    assert path.read_text(encoding='utf-8') == source


def test_truncated_preview_does_not_hold_potentially_stale_values(tmp_path, monkeypatch):
    monkeypatch.setattr('eitri.backend.vcd.MAX_EVENTS', 1)
    path = tmp_path / 'limited.vcd'
    path.write_text('$var wire 1 ! data $end\n$enddefinitions $end\n#0\n0!\n#10\n1!\n')
    data = parse_vcd(path, stop_time='60ns')
    assert data['end_time'] == 10
    assert 'truncated' in data['warning']


def test_final_case_can_be_selected_after_last_vcd_timestamp(tmp_path):
    import json
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    app = QApplication.instance() or QApplication([])
    path = tmp_path / 'wave.vcd'
    path.write_text('$timescale 1 ns $end\n$var wire 9 ! result $end\n'
                    '$enddefinitions $end\n#0\nb0 !\n#50\nb100000001 !\n')
    data = parse_vcd(path, stop_time='60ns')
    (tmp_path / 'wave.json').write_text(json.dumps(data))
    page = SimulationPage()
    page.resize(1100, 700)
    page.show()
    try:
        app.processEvents()
        page.load_result(tmp_path, {'waveform': 'wave.json', 'wave_file': 'wave.vcd', 'signals': 1})
        app.processEvents()
        page.wave.fit()
        width = page.wave.viewport().width() - page.wave.LEFT
        QTest.mouseClick(page.wave.viewport(), Qt.MouseButton.LeftButton,
                         pos=QPoint(page.wave.LEFT + round(width * 55 / 60), page.wave.TOP + 15))
        assert page.wave.cursor == pytest.approx(55, abs=0.2)
        assert page.signals.topLevelItem(0).text(1) == '101'
        assert 'Last recorded timestamp: 50 ns' in page.status.text()
        page.wave.zoom_by(2)
        page.wave.horizontalScrollBar().setValue(page.wave.horizontalScrollBar().maximum())
        QTest.mouseClick(page.wave.viewport(), Qt.MouseButton.LeftButton,
                         pos=QPoint(page.wave.viewport().width() - 2, page.wave.TOP + 15))
        assert 59 < page.wave.cursor <= 60
        assert page.signals.topLevelItem(0).text(1) == '101'
    finally:
        page.close()
        app.processEvents()
