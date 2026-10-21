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
| Visible document editor and Find | `code_page.py` |
| Open, save, overwrite protection, unsaved-edit dialogs | `documents.py` |
| Text input, indentation, line numbers, current-line shading | `editor.py` |
| VHDL keywords, tokens and syntax colors | `highlighting.py` |
| Menus and keyboard shortcuts | `actions.py` |
| Colors, borders, fonts, spacing inside controls | `theme.py` |
| Preferred window dimensions and screen limits | `sizing.py` |
| Minimal design and testbench generators | `templates.py` |
| Startup, new-design form and generation workflow | `design_dialog.py`, `components_dialog.py`, `design_flow.py` |
| Folder indexing, library bindings, target snapshots | `backend/project.py` |
| Cached project analysis and source-mapped diagnostics | `backend/project_pipeline.py` |
| Legacy source-reference utilities | `backend/dependencies.py` |
| Language server transport, mirrors and diagnostics | `language_server.py` |
| Interactive component hierarchy and SVG export | `hierarchy.py` |
| Named targets and generic override form | `target_dialog.py` |
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
application: for example, `Sidebar.open_folder_requested` connects to
`Workspace.choose_folder`, which creates a `Project` index.
The document controller creates or restores a buffer when a file is selected. It receives the window explicitly; there are no global widget variables.

`Workspace.editor` and `Workspace.path` refer to the selected document.
`DocumentController.records` owns a buffer per opened path, so undo history,
cursor position and unsaved text survive file switches. Only one editor is
visible. `Project.sources` combines disk sources with these buffer overrides;
LSP, hierarchy and run snapshots share this view. `Target` objects select an
entity/library/architecture independently of the active editor.

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
