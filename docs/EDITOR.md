# Folder workspace

Run `PYTHONPATH=src .venv/bin/python -m eitri` from the source checkout, or
launch the installed `eitri` command. The app starts with a blank editor;
choose **Open folder…** when you are ready to select a project. On macOS this
uses Qt's folder picker instead of the native Finder panel. The left panel
scrolls when the window is too short to fit the explorer and target settings.
Try [the learning CPU](../examples/learning_cpu/README.md) for a complete example.

From a terminal, `eitri .` opens the current directory, and
`eitri "/path/to/project folder"` opens that project. Relative paths and `~` are
supported. Plain `eitri` opens a blank workspace. Invalid paths are reported in
the terminal before launching a window. All forms return control to the terminal;
add `--foreground` to keep the app attached while debugging.

## Files and editing

The left explorer lists VHDL files recursively. Select a file to display it in
one editor area. Every open file retains its unsaved buffer, undo history,
cursor and scroll position when you switch files. There are no special Design
or Testbench document roles. **Quick open** (Command/Ctrl+P) offers a searchable
file selector. **Save all** is Command/Ctrl+Alt+S.

The explorer's context menu can open a file, simulate an entity in it, generate
its circuit, create a testbench, or insert an instance into the current editor.
Normal F5/F6 commands run the selected named target, independently of the file
being edited. If a file offers multiple runnable entities/architectures, Eitri
asks which one to use.

Files changed externally reload automatically when their buffers are clean.
Dirty buffers show **Reload from disk** / **Keep my edits**, and saving also
checks for a conflicting disk version. Opening a different project or closing
the application checks every dirty buffer. UTF-8 writes use QSaveFile so a
partial write does not replace the original. Generated source never replaces
an existing file without confirmation.

**New design** creates an entity/architecture skeleton. **Insert instance**
reads a project entity and inserts a direct instantiation with a unique label,
generic defaults and named port-map placeholders. It places the instance before
the destination architecture's closing `end`, outside processes and declarations,
and selects the first connection placeholder. The cursor chooses an architecture
when inside one; otherwise a file with multiple architectures offers a destination
picker. A complete architecture is required. Selected source text is preserved,
and one Undo removes the insertion. Replace `<...>` with actual connections
before compiling. **Create testbench** generates the interface,
signals and an empty stimulus process; its destination is selectable. Package
context clauses and custom port types are retained. Initial values are supplied
for STD_LOGIC inputs; custom types may need manual initialization. Clocks,
resets, stimulus and assertions are always written by the user.

## VHDL assistance

The bundled GHDL language server runs in its own process. It receives the same
folder sources and open-buffer overrides used by builds, with the selected
VHDL standard and configured libraries. Edits synchronize after a 400 ms pause.
Errors/warnings appear underlined and in the problem list, including problems
in files not currently open. Activate a problem to navigate to its location.
Hover shows declaration information; F12 or **Go to definition** opens the
source. Project files remain editable; external standard-library files open
read-only. Switching documents does not discard any edits.

The assistance panel reserves its own space, even when there are no diagnostics,
so clearing errors does not shift the code. Drag its divider to resize it. The
top-right docking control moves it between the bottom and right of the editor;
each position remembers its size. Use the close control, the **Problems** button,
or Command/Ctrl+J to hide/show the panel without disabling assistance. Docking,
visibility and sizes are remembered across launches. Theme changes preserve
diagnostics and panel layout. After reported problems clear, a short forge-themed
message appears; edits awaiting validation show **Checking your changes…**.

Turn **VHDL assistance** off to stop the server. If it fails, the status tooltip
shows the error; toggle off/on to retry. The bundled server does not support
completion or rename. GHDL LS uses Latin-1 source columns; unsupported Unicode
characters are replaced only in its analysis copy, never in the saved UTF-8 file.

Lexical highlighting, indentation, line numbers, Undo/Redo and Find work
independently of the server. Tab advances to the next four-column stop; with a
selection it indents all selected lines. Shift+Tab removes one indentation level
from the current or selected lines. A selection ending at the next line's start
does not indent that line. Each block indentation is one undoable edit.
Backspace in leading whitespace at a four-column stop removes one indentation
level; between stops or after code it deletes a single character. Enter carries
the current indentation forward.

## Component hierarchy

The explorer's **Hierarchy** tab provides source navigation. The separate
**Component hierarchy** view (F7) draws instance cards and parent/child edges.
Choose a root entity/architecture. Select a card to see its source, instance
path, generic map and port associations. Open its definition or wiring, or
request a circuit for that component. Double-click a parent to expand/collapse;
use Fit, pinch zoom, two-finger pan and SVG export.

This is a source hierarchy, not a simulator elaboration report. A generate
statement is shown once at its source location; actual replication, condition
selection and generic evaluation belong to GHDL. Recursive/missing/ambiguous
references are annotated and expansion is bounded. Selecting an entity for a
component circuit uses that entity's defaults or a saved target's overrides;
it does not infer its parent's effective generic values.

## Project metadata and discovery

Eitri discovers `.vhd` and `.vhdl` files below the opened folder. Hidden folders,
symlinked source files, `.git`, `.venv`, `venv`, `node_modules`, `build`, `dist`,
`runs`, `analysis-cache` and `.eitri` are excluded. Build outputs normally live
in the application cache outside the project.

An optional `.eitri.json` stores the language standard, named targets, generic
overrides, stop times, waveform format, checked signal names, selected targets
and last edited file. It is portable and can be committed with source code.
Relative source paths are used in targets. For custom libraries/exclusions:

```json
{
  "version": 1,
  "standard": "VHDL 2008",
  "exclude": ["vendor/unused/*"],
  "libraries": {"common": ["shared/*.vhd", "shared/*.vhdl"]},
  "targets": []
}
```

Unmapped files use `work`. Reopen the folder after manually changing project
metadata. Automatic ordering supports entity/architecture dependencies,
component/direct entity instances, package imports and package bodies. Ambiguous
architectures require an explicit choice. Explicit VHDL configurations,
context-declaration dependency expansion, extended identifiers and complex
binding specifications are not fully indexed; GHDL remains authoritative for
semantic validation. Dependencies must be within the opened project tree.

The index is tolerant while editing and is not a second VHDL compiler. A target
build includes its reachable files; unrelated unfinished components need not
block it. Dependency cycles and missing bindings receive actionable errors.
For inseparable design units with file-level dependency cycles, split the units
into separate files.
