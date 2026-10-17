# Qt workspace

Run `python -m eitri` in the project virtual environment. PySide6-Essentials supplies Qt Core, Gui and Widgets; no browser or WebEngine is needed. The previous Dear PyGui version remains in Git history.

The workspace provides a charcoal and aged-brass theme with a Copperplate wordmark (Palatino/Georgia fallback), Code / Simulation / Circuit navigation icons centered beneath the wordmark in the left column, with tooltips, an edge-to-edge split workspace with a draggable sidebar divider and full-height right-hand pages, and native open/save dialogs.

On launch, choose **Open existing design** or **Create new design**. New designs ask for an entity name and optional ports: input/output, STD_LOGIC or STD_LOGIC_VECTOR, and vector width. A width of 8 generates (7 downto 0). Click **Next: Components…** to optionally import existing VHDL entities and choose an instance count for each. With no components, the saved file contains only the entity and an empty architecture.

The Components step generates only component declarations and instance templates with named port maps, such as `A => <A>`. Replace every angle-bracket placeholder with your connection before compiling. Declare only the internal signals you need—for example, three signals for a four-adder carry chain. No per-port signals are generated. Generic defaults remain in the component declaration; add a generic map when you need overrides. **Back** returns to the ports form.

Component source files stay separate. New designs record their paths in VHDL comments such as `-- eitri-source: "../components/FullAdder.vhd"`. Paths are relative to the containing file (absolute when Windows drive boundaries require it). They survive reopening, and Save As rebases them to keep pointing to the same files. Keep referenced files with the design when sharing it.

Before each run, Eitri follows these references recursively and resolves component declarations and direct `entity work.Name` instantiations against sibling .vhd/.vhdl files. It matches entity names, not filenames. Missing sources, ambiguous definitions and circular dependencies produce an error before tools start. Explicit references choose between ambiguous sibling definitions. Current disk contents are snapshotted with the two editor buffers, and dependencies compile before their parent designs. Edited dependency files are picked up on the next run; existing results are snapshots.

This resolver supports basic entity names in the work library. External library mapping, automatic package discovery and configuration-based bindings are not supported; package sources can be included explicitly in dependency order. Existing files with embedded component implementations continue to work without migration. The component-import form retains the same STD_LOGIC interface restrictions as testbench generation.


On the Design tab, **Create Testbench** reads the current design text and writes a sibling file: adder.vhd becomes adder_TB.vhd (or .vhdl remains .vhdl). The testbench entity uses the design entity name plus _TB, even if the filename differs. It includes a component declaration, connected signals, initialized inputs and an empty stimulus process. Add your own clock, input changes and assertions. Existing testbench files require confirmation before replacement.

Generation supports STD_LOGIC and constrained STD_LOGIC_VECTOR ports, grouped port names, and integer/positive/natural/boolean generics with defaults. Unsupported interfaces show an explanation; they can still be edited manually. Files with multiple entities prompt you to select one.

The preferred launch size is 1140 × 620, reduced automatically to leave room on smaller screens. Code contains independent Design and Testbench tabs, each retaining its file, edits, cursor position and undo history. New starts a new design/testbench pair. **Open design…** checks both buffers for unsaved changes and clears the old testbench; **Open testbench…** changes only the testbench, regardless of the selected tab. Both explicit Open actions and context-labeled Save actions live in the Code sidebar. Save, Undo and Find act on the selected tab. Closing checks both tabs. Settings remain in memory while switching modes.


## Editor

`CodeEditor` uses QPlainTextEdit for text, selections and undo/redo, with a custom gutter and QSyntaxHighlighter. Highlighting recognizes case-insensitive VHDL keywords, common types, numbers, quoted literals, line comments, extended identifiers and multiline block comments. It is lexical styling, not a compiler or language server: there is no semantic validation, autocomplete or error reporting yet.

The editor supports line numbers, current-line shading, four-space Tab insertion, indentation carried onto a new line, and find with wraparound. Standard platform shortcuts cover New, Open, Save, Save As, Undo, Redo and Find (Command on macOS, Control on Windows/Linux). Find is case-insensitive.

UTF-8 files are saved through QSaveFile so an incomplete write does not replace the original. Unsaved edits prompt Save / Discard / Cancel when closing, opening another file, or creating a new file. Line endings normalize to LF. Settings are not yet persisted between launches.

Simulation and Circuit run the packaged tools in background processes. See [TOOLS.md](TOOLS.md) for controls, artifacts, supported inputs, and preview limits.

## Implementation

See [CONTRIBUTING.md](CONTRIBUTING.md) for the module map and common changes.
The window composes independent toolbar, sidebar and code-page widgets. File
operations live in `documents.py`; editor behavior and syntax rules are separated
into `editor.py` and `highlighting.py`.

Official Qt reference: https://doc.qt.io/qtforpython-6/examples/example_widgets_richtext_syntaxhighlighter.html

Run headless UI tests with `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_ui.py -q`. The test module also defaults to the offscreen platform when no platform was explicitly set.

The Norse-inspired wordmark uses system fonts; no font download is required. The editor and regular controls retain readable fonts.
