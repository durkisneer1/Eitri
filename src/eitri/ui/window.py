"""Eitri desktop workspace; launch with python -m eitri."""
from pathlib import Path
import dearpygui.dearpygui as dpg

MODES = ('Code', 'Simulation', 'Circuit')


class Workspace:
    def __init__(self):
        self.path = None
        self.saved_text = ''
        self.pending_open = None

    def status(self, message):
        dpg.set_value('status', message)

    def edited(self):
        dirty = dpg.get_value('source') != self.saved_text
        name = self.path.name if self.path else 'Untitled.vhd'
        dpg.set_value('document_name', name + (' *' if dirty else ''))

    def switch_mode(self, sender, app_data, user_data):
        for mode in MODES:
            dpg.configure_item(f'view_{mode}', show=mode == user_data)
            dpg.configure_item(f'options_{mode}', show=mode == user_data)
        dpg.set_value('mode_title', user_data)

    def choose_open(self, sender, app_data):
        path = Path(app_data['file_path_name'])
        if dpg.get_value('source') != self.saved_text:
            self.pending_open = path
            dpg.show_item('discard_dialog')
        else:
            self.load(path)

    def confirm_open(self):
        dpg.hide_item('discard_dialog')
        if self.pending_open is not None:
            self.load(self.pending_open)
            self.pending_open = None

    def load(self, path):
        try:
            content = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError) as error:
            self.status(f'Could not open file: {error}')
            return
        self.path = path
        self.saved_text = content
        dpg.set_value('source', content)
        dpg.set_value('file_path', str(path))
        self.edited()
        self.status(f'Opened {path.name}')

    def save(self):
        if self.path is None:
            dpg.show_item('save_dialog')
        else:
            self.write(self.path)

    def choose_save(self, sender, app_data):
        path = Path(app_data['file_path_name'])
        if not path.suffix:
            path = path.with_suffix('.vhd')
        self.write(path)

    def write(self, path):
        content = dpg.get_value('source')
        try:
            path.write_text(content, encoding='utf-8')
        except (OSError, UnicodeError) as error:
            self.status(f'Could not save file: {error}')
            return
        self.path = path
        self.saved_text = content
        dpg.set_value('file_path', str(path))
        self.edited()
        self.status(f'Saved {path.name}')

    def resize(self):
        width = dpg.get_viewport_client_width()
        height = max(260, dpg.get_viewport_client_height() - 110)
        dpg.configure_item('sidebar', height=height)
        dpg.configure_item('workspace', width=max(320, width - 302), height=height)
        dpg.configure_item('source', height=max(180, height - 100))

    def build(self):
        for tag, callback in (('open_dialog', self.choose_open), ('save_dialog', self.choose_save)):
            with dpg.file_dialog(tag=tag, show=False, width=720, height=440,
                                 modal=True, callback=callback):
                dpg.add_file_extension('.vhd')
                dpg.add_file_extension('.vhdl')
                dpg.add_file_extension('.*')
        with dpg.window(tag='discard_dialog', label='Unsaved changes', modal=True,
                        show=False, no_close=True, autosize=True):
            dpg.add_text('Discard unsaved edits and open the selected file?')
            with dpg.group(horizontal=True):
                dpg.add_button(label='Discard and open', callback=self.confirm_open)
                dpg.add_button(label='Cancel', callback=lambda: dpg.hide_item('discard_dialog'))
        with dpg.window(tag='primary', no_title_bar=True):
            with dpg.group(horizontal=True):
                dpg.add_text('EITRI', color=(105, 190, 240))
                dpg.add_spacer(width=12)
                for mode in MODES:
                    dpg.add_button(label=mode, width=100, height=30,
                                   callback=self.switch_mode, user_data=mode)
                dpg.add_spacer(width=12)
                dpg.add_button(label='Open', callback=lambda: dpg.show_item('open_dialog'))
                dpg.add_button(label='Save', callback=self.save)
                dpg.add_button(label='Save as', callback=lambda: dpg.show_item('save_dialog'))
            dpg.add_separator()
            with dpg.group(horizontal=True):
                with dpg.child_window(tag='sidebar', width=270, height=600):
                    dpg.add_text('OPTIONS & PARAMETERS', color=(105, 190, 240))
                    dpg.add_separator()
                    dpg.add_text('Source file')
                    dpg.add_text('No file opened', tag='file_path', wrap=240)
                    dpg.add_spacer(height=12)
                    dpg.add_text('VHDL standard')
                    dpg.add_combo(('2008', '1993', '2002'), default_value='2008',
                                  tag='vhdl_standard', width=-1)
                    dpg.add_text('Top-level entity')
                    dpg.add_input_text(tag='top_entity', hint='e.g. counter', width=-1)
                    dpg.add_spacer(height=16)
                    with dpg.group(tag='options_Code'):
                        dpg.add_text('Editing')
                        dpg.add_text('Open a VHDL file or start typing. Save writes UTF-8 text.', wrap=240)
                    with dpg.group(tag='options_Simulation', show=False):
                        dpg.add_text('Testbench entity')
                        dpg.add_input_text(tag='testbench', hint='e.g. counter_tb', width=-1)
                        dpg.add_text('Stop time')
                        dpg.add_input_text(tag='stop_time', default_value='1us', width=-1)
                        dpg.add_text('Waveform format')
                        dpg.add_combo(('VCD', 'GHW'), default_value='VCD', tag='waveform_format', width=-1)
                        dpg.add_text('Simulation execution is not connected yet.', wrap=240)
                    with dpg.group(tag='options_Circuit', show=False):
                        dpg.add_text('Circuit view')
                        dpg.add_text('Synthesize VHDL, then generate an SVG schematic.', wrap=240)
                        dpg.add_text('Circuit generation is not connected yet.', wrap=240)
                with dpg.child_window(tag='workspace', width=880, height=600):
                    dpg.add_text('Code', tag='mode_title', color=(105, 190, 240))
                    dpg.add_separator()
                    with dpg.group(tag='view_Code'):
                        dpg.add_text('Untitled.vhd', tag='document_name')
                        dpg.add_input_text(tag='source', multiline=True, tab_input=True,
                                           width=-1, height=500, callback=self.edited)
                        dpg.add_text('Plain-text editor; syntax highlighting pending', color=(150, 160, 175))
                    with dpg.group(tag='view_Simulation', show=False):
                        dpg.add_text('Simulation results')
                        dpg.add_text('Waveforms and simulator output will appear here.')
                        dpg.add_text('Choose a testbench and stop time in the left panel.')
                    with dpg.group(tag='view_Circuit', show=False):
                        dpg.add_text('Circuit schematic')
                        dpg.add_text('The generated netlist diagram will appear here.')
                        dpg.add_text('Choose the top-level entity in the left panel.')
            dpg.add_separator()
            dpg.add_text('Ready', tag='status', wrap=1100)


def main():
    dpg.create_context()
    try:
        workspace = Workspace()
        workspace.build()
        dpg.create_viewport(title='Eitri', width=1200, height=800,
                            min_width=800, min_height=500)
        dpg.setup_dearpygui()
        dpg.set_primary_window('primary', True)
        dpg.set_viewport_resize_callback(workspace.resize)
        dpg.show_viewport()
        workspace.resize()
        dpg.start_dearpygui()
    finally:
        dpg.destroy_context()


if __name__ == '__main__':
    main()
