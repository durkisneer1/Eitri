# Editor integration options

Eitri currently uses Dear PyGui 2.3.1's multiline input_text widget. It supports editing, selection, undo and tab input, but does not expose per-token text styling. The editor is plain text; syntax highlighting is not implemented.

For an IDE with integrated VHDL highlighting, the recommended direction is PySide6 (Qt): QPlainTextEdit for editing and QSyntaxHighlighter for VHDL token styles. Qt owns cursor movement, selection and undo while a highlighter formats the document. VHDL rules still need implementing, including comments, strings, case-insensitive keywords, identifiers and literals. Line numbers and diagnostics would be additional features.

Official example: https://doc.qt.io/qtforpython-6/examples/example_widgets_richtext_syntaxhighlighter.html

Dear ImGui Bundle exposes a color text editor, but it is a separate GUI binding, not a drop-in Dear PyGui widget. Its current Python language list does not include VHDL. Verify custom language support before choosing it.

Bindings: https://github.com/pthom/imgui_bundle/blob/main/bindings/imgui_bundle/imgui_color_text_edit.pyi

Monaco is another capable editor, but needs a browser/webview host and a VHDL language definition. Embedding it inside Dear PyGui adds cross-platform integration work.

Source: https://github.com/microsoft/monaco-editor

Tokenizing text alone does not implement an editor. A Pygments-backed colored preview could coexist with the plain input, but would not provide syntax highlighting inside the editable text.

# Current workspace scope

Launch with `python -m eitri` after activating the project virtual environment. The toolbar switches Code, Simulation and Circuit views; each retains its controls while hidden. File open, save, save-as, and confirmation before replacing unsaved content are connected. Closing the application currently does not prompt about unsaved content: save before closing.

Simulation and circuit generation are placeholders; the controls are not yet connected to the tool adapters. The UI currently edits one file at a time.
