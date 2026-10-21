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
