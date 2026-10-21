# Simulation and circuit targets

Open a folder, then choose a **Simulation target** or **Circuit target** in the
left panel. Targets identify entities and architectures, not editor roles.
Editing an adder does not change a selected CPU testbench. Right-click a source
file to choose a target from that file. F5 runs the selected simulation; F6
builds the selected circuit.

**Configure / save target** gives a run a reusable name and optional generic
overrides. Stop time, waveform format and circuit detail are set on their pages
and saved when run. Sources come from a project snapshot that includes unsaved
changes in every open buffer. Package and component dependencies are ordered
before their users. Diagnostics map back to the original source paths;
double-click an error/assertion location in the log to open it.

Each run has an immutable source snapshot and exportable artifacts. Editing
while a run is active cannot change it. Older results are marked stale after
source changes. Exports include `source_*.vhd`, `sources.json` mapping those
files to their original paths, `request.json`, `run.log`, and generated outputs.

Analysis is cached outside the project by project, target, language standard,
tool version and source/library list. Unchanged analyzed prefixes are reused;
a changed source and subsequent files in dependency order are reanalyzed.
Only successfully analyzed states are cached. Concurrent workers use isolated
analysis directories if a cache is busy. Simulation results and source exports
are always fresh. Interrupted cache owners may leave a lock; subsequent runs
safely use isolated analysis until that cache is cleared.

## Simulation

GHDL analyzes the selected target's dependencies, elaborates its architecture,
and simulates with generic overrides until completion or the selected stop time.
Assertion severity error/failure fails a run. A successful process exit means
no failing assertion was encountered, not that the design has complete test
coverage. Add explicit assertions and timeout/watchdog checks to your tests.

**Run all tests** snapshots discovered no-port testbench targets and saved
simulation targets, then runs them sequentially. The **Tests** explorer tab
shows queued/running/passed/failed/cancelled results. Activate a result to reopen
its log and waveforms. A failed test does not prevent the remaining tests from
running. Stop cancels both the active simulation and queued tests.

Check signals to display them. Checked signal names are remembered per target.
Choose Binary, Hex or Unsigned; VHDL uninitialized/unknown states remain visible.
Click the waveform to move the cursor, use +/− and Fit to zoom, and pan with
trackpad scrolling. VCD powers the embedded preview; GHW output also produces a
VCD preview. Export individual waveforms or a ZIP of the complete run.
GTKWave is an optional external viewer.

The default stop time is 200 ns. Preview limits are 64 MB, 150,000 changes and
512 signals. Dense traces ask you to zoom in. Real/string signals are omitted
from the digital preview. The full waveform remains available for export.
Workers stop after ten minutes or if their VCD exceeds 256 MB.

## Circuits

GHDL lowers the selected hierarchy to Verilog; Yosys builds a netlist and
netlistsvg draws it. **Simple** keeps component and memory blocks. **Detailed**
expands hierarchy and inferred memory into registers and logic.

In a Simple circuit, select a component and choose **Expand** to replace that
component with its implementation while retaining sibling blocks. **Collapse
all** restores the block view. Expansion rerenders the displayed run's immutable
source snapshot; regenerate the target to include newer edits.

Two-finger scrolling pans; pinching zooms. Dragging, +/− and Fit also work.
SVG exports preserve vector detail and the display theme. Original synthesis
netlists retain X/Z constants; renderer-only `Unknown (X)` and `High impedance
(Z)` boxes make those values visible. X may represent an inactive don't-care
input rather than a faulty design.

Use **Component hierarchy** to explore source relationships and port maps
without synthesis, then compare that structure with the circuit implementation.
