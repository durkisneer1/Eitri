# Simulation and Circuit

Both pages run the **current editor text**, including unsaved changes. Each run
gets its own source snapshot and build directory. You can keep editing while a
run proceeds; changed inputs mark the displayed results as out of date.

## Simulation

Component dependencies are resolved recursively and snapshotted from disk before either pipeline runs. The run log maps dependency snapshot filenames back to their original paths; exported runs include the dependency snapshots. See [EDITOR.md](EDITOR.md) for reference and discovery rules.

1. Set the VHDL standard, testbench entity and stop time in the left panel.
2. Click **Run simulation**, or press **F5**. GHDL analyzes Design then Testbench,
   elaborates the testbench, and runs until it finishes or reaches the stop time.
3. Check signals in the list to show them in the timing diagram. The filter
   narrows the list, while checked waveforms remain visible.
4. Click the diagram to move the time cursor. The signal list shows each value
   at that time. Choose Hex, Binary or Unsigned, zoom with +/−, and use Fit to
   restore the whole time range. Scroll horizontally when zoomed.
5. Export the waveform, export the complete run, or open it in GTKWave.

Generated testbenches start with an empty stimulus process. Add input changes,
a clock if needed, and assertions before running. The default stop time is 200 ns.
GHDL assertion errors fail the run and appear in the output panel.

The embedded viewer reads VCD. Selecting GHW writes both VCD for the preview and
GHW for export/GTKWave. GTKWave is an optional external installation; its absence
does not prevent simulation or embedded waveform viewing.

## Circuit

Set the top-level entity, then click **Generate circuit** or press **F6**. The
pipeline synthesizes the Design tab with GHDL, lowers it to Verilog, processes it
with Yosys, maps memories into logic, and renders the netlist with netlistsvg.
The Testbench tab is excluded from synthesis.

Drag the schematic to pan, scroll or use +/− to zoom, and click Fit for an overview.
The summary shows the top module, cell count and port count. Export SVG saves the
vector drawing; Export run also includes Verilog, original Yosys JSON, the
renderer-specific JSON, source snapshot, settings and diagnostics.

Z constants are drawn as labeled **High impedance (Z)** source boxes.
X constants use **Unknown (X)** boxes. These are display helpers because the
pinned renderer cannot handle those constants directly; the original
`netlist.json` is unmodified. SVG CSS is inlined so Qt renders wires correctly.
The diagram is a synthesized logical schematic, not device placement/routing.

## Jobs, diagnostics and files

Run and Stop are independent per page. Tool subprocesses never run on Qt's event
thread. Stage names update while the job runs; captured compiler/tool output
appears after each stage. The output panel can be resized with its splitter.
A failed or stopped run preserves the previous view, clearly labeled as such.
Closing during execution offers to stop the jobs before handling unsaved files.

Run files live in `QStandardPaths.CacheLocation/runs` (Eitri's platform cache
folder). They persist across launches until the cache is cleaned. Use **Export
run** to save a ZIP permanently; it includes source text and settings as well as
results. No file is uploaded. Failed runs can also be exported for debugging.
Diagnostics refer to `design.vhd` and `testbench.vhd`, corresponding to the two
editor tabs, regardless of their saved filenames.

## Current supported scope

- Two source buffers: the design and testbench may contain multiple VHDL design
  units. Component sources are resolved from tracked references and sibling files.
  There is no vendor IP setup or external library mapping yet.
- Basic VHDL entity identifiers and standards 1993, 2002 and 2008. Stop times are
  positive integers with fs, ps, ns, us, ms or sec units.
- Digital VCD preview preserves hierarchy, aliases and X/Z values. Real/string
  signals require the external viewer. Preview limits are 64 MB, 512 signals and
  150,000 changes; a visible warning explains any truncation. Complete waveform
  data remains available for export. Dense traces require zooming for detail.
- GHDL's synthesizable VHDL subset applies. Unsupported constructs and tool
  errors appear in the log; no schematic is fabricated on failure.
- Stages have finite timeouts, whole jobs have a 10-minute limit, and a VCD over
  256 MB stops the job to avoid runaway simulation output. Shorten the stop time
  when needed. The UI log keeps 3,000 lines; the full run log remains on disk.

End-to-end tests exercise the actual ROM simulation (including GHW), synthesis,
SVG rendering, invalid input, failed compilation, export and cancellation.
