# A tiny accumulator CPU

Open this folder in Eitri. The CPU executes `LOAD 1`, `ADD 2`, `ADD 3`, then
`HALT`; its result is 6. This is a teaching example, not a general-purpose ISA.

1. Open **Component hierarchy** (F7), choose `work.cpu (rtl)`, and follow
   `u_datapath → u_alu → u_add`. Select a card to inspect its port map. Use
   **Open definition** or **Open instance / wiring** to jump into the source.
   Double-click a parent to collapse or expand its children.
2. Keep `cpu_tb` selected as the simulation target. Edit `rtl/alu/adder.vhd`;
   F5 still runs the CPU testbench, with your unsaved adder edits included.
3. Try changing `+` to `-` in the adder. **Run all tests** runs the adder, ALU,
   and CPU testbenches against one set of source snapshots. Open a failed
   result and double-click its assertion location to jump to the test.
   Undo the adder change and run the suite again.
4. Generate the `cpu` circuit with **Simple** detail. Choose `u_datapath` in
   the component selector and click **Expand**. Its logic appears while the
   program ROM stays a block. **Collapse all** restores the block view;
   **Detailed** expands all component hierarchy and inferred memory.
5. Check signals in the waveform list. Their selection is saved with the
   target. Export the run to retain the source snapshot, source map, logs,
   and waveforms together.

The `rtl/cpu_types.vhd` package is found and compiled before its users.
Subfolders do not imply separate VHDL libraries: this example uses `work`.
The clock and assertions are manually written in `tb/cpu_tb.vhd`.
`std.env.stop` ends successful tests; the CPU test also has a watchdog assertion
so a CPU that never halts fails instead of silently reaching the stop time.
