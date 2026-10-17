# Working on Eitri

Start with `src/eitri/ui/window.py`. `Workspace.__init__` creates the toolbar,
sidebar and pages, then connects their signals to actions. There is no generated
UI code or special registration system: these are ordinary Python classes.

## Where to make a change

All paths in this table are relative to `src/eitri/ui/`.

| Change | File |
|---|---|
| Overall layout, view switching, status bar, signal connections | `window.py` |
| Wordmark, top buttons, mode selection | `toolbar.py` |
| Options and parameters on the left | `sidebar.py` |
| Design/Testbench tabs and Find | `code_page.py` |
| Open, save, overwrite protection, unsaved-edit dialogs | `documents.py` |
| Text input, indentation, line numbers, current-line shading | `editor.py` |
| VHDL keywords, tokens and syntax colors | `highlighting.py` |
| Menus and keyboard shortcuts | `actions.py` |
| Colors, borders, fonts, spacing inside controls | `theme.py` |
| Preferred window dimensions and screen limits | `sizing.py` |
| Minimal design and testbench generators | `templates.py` |
| Startup, new-design form and generation workflow | `design_dialog.py`, `components_dialog.py`, `design_flow.py` |
| Source references and recursive dependency snapshots | `backend/dependencies.py` |
| Entity/port parsing and validation | `backend/vhdl.py` |
| Simulation signal list and controls | `simulation.py` |
| Digital waveform painting, zoom and cursor | `waveform.py` |
| Circuit SVG viewer and controls | `circuit.py` |
| Shared Run/Stop/log/export layout | `job_page.py` |
| Snapshot settings and route results | `tool_controller.py` |
| Background process lifecycle and cancellation | `jobs.py` |
| Shared label/button/field constructors | `widgets.py` |

## How the pieces communicate

Widgets own their layouts. They emit signals when an action belongs to the
application: for example, `Toolbar.open_requested` connects to
`Workspace.open_file`, which delegates to `DocumentController.open_file`.
The controller opens a native dialog and loads the selected file into the active
editor. It receives the window explicitly; there are no global widget variables.

`Workspace.editor` and `Workspace.path` refer to the selected document.
`CodePage.editors` contains the two separate editor widgets, so undo history,
cursor position and unsaved text survive tab switches. `Workspace.paths` stores
their corresponding disk paths. File operations must preserve this separation.

To add a sidebar setting, create the control in `Sidebar` and keep a named
attribute on it, like `self.stop_time`. The application can read it through
`self.sidebar.stop_time.text()`. To add a toolbar action, emit a signal from
`Toolbar` and connect it in `Workspace.__init__`.

The tool adapters live under `packages/`, independently of the GUI.
`ToolController` snapshots editors/settings and starts `JobRunner`. It launches
`backend/pipeline.py` in a separate Python process. A Qt timer polls its log and
completion, then the controller passes results to the correct page. Qt widgets
are updated only on the GUI thread; Stop terminates the worker and its tool tree.

`src/eitri/backend/pipeline.py` owns command sequencing and timeouts; `vcd.py`
owns waveform parsing; `schematic.py` prepares renderer-compatible display
artifacts without changing the original synthesis netlist. These modules do not
import Qt and can be tested independently. The Qt files have section comments
explaining layout groups, signal wiring, and which state survives a run.

## Run and check

Activate `.venv`, then run `python -m eitri`. Because the package is installed in
editable mode, changes to Python source take effect on the next launch.

Run `python -m pytest tests/test_ui.py -q` for editor and document behavior.
The UI tests default to Qt's offscreen backend. Run `python -m pytest -q` for the
full suite, including the ROM simulation and tool-adapter checks. For a headless
manual render, set `QT_QPA_PLATFORM=offscreen` before creating QApplication.

The preferred window size is 1140 × 620 logical pixels. `sizing.py` reduces it
when necessary using Qt's available screen rectangle, which excludes the menu
bar and Dock. It reserves additional space around the window and its title bar.
