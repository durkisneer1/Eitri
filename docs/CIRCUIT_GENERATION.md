# Circuit generation: review and maintenance contract

The pipeline has three responsibilities, with separate artifacts:

1. **Elaboration:** GHDL compiles the selected entity/architecture, libraries,
   generics and dependency snapshot into `design.v`. Both project and individual
   source workflows converge on the same circuit renderer.
2. **Synthesis:** Yosys resolves hierarchy and processes into `netlist.json`.
   Simple retains components and memories. Detailed flattens hierarchy and
   maps memories to registers and selection logic; register enables stay visible.
3. **Presentation:** `schematic.json` is a copy with educational symbols and
   routing helpers. The SVG skin supplies geometry; colors and fonts affect
   presentation only. `netlist.json` remains unchanged.

## Findings addressed

- Binary case decoding was exposed as compiler-generated comparators and a
  parallel mux. Recognition now uses the decoder's complete binary truth table,
  independent of VHDL names, bit numbering and branch order.
- Ordinary 2:1 muxes and recognized decoded muxes now share the same display
  representation in Simple and the same expansion machinery in Detailed.
- Shared decoder outputs are retained when another cell or external port uses
  them. Multiple drivers, incomplete and overlapping decoders are not simplified.
- Identical mux columns become wires, repeated columns share logic, and repeated
  wires receive a fan-out symbol. These rules apply to any bit pattern, not just
  sign extension. Constant zero branches can become enable AND gates.
- Unused X/Z net aliases no longer create floating unknown-value boxes. Actual
  X/Z connections and outputs remain visible and distinct from binary constants.
- A component instance named like an internal mux symbol cannot accidentally
  trigger the mux expansion path.
- Stock skin aliases conflated multi-bit logical tests and reductions with
  bitwise gates. Zero tests and reductions now have explicit labels; parallel
  bitwise gates have a multiplicity label. Connections and signedness parameters
  are preserved.
- Compiler-generated cell names containing periods broke netlistsvg's custom
  captions. SVG labels are restored from the display artifact without renaming
  cells or changing the vendored renderer.
- UI, preview and SVG export colors now share a light/dark palette. Theme changes
  do not alter generated netlists or require synthesis.

## Verification

Tests cover synthesized conditional mux chains, selected assignments, unsigned
addition, XOR, signed comparison, shifts, parity reduction, scalar replication,
signed resizing, enabled registers and asynchronous reset. For both modes,
renderer-only symbols are translated back to standard Yosys cells and checked
against the original netlist with equivalence passes. Async registers use the
same `async2sync` model on both sides; sequential checks establish correspondence
of matching state, not arbitrary power-on state or analog timing.

Independent exhaustive selector/walking-data checks cover 2-, 4-, 8- and 16-way
muxes with 1-, 3- and 7-bit data, shuffled net IDs and shuffled decoder branches.
Additional regressions cover shared decoders, overlapping/incomplete decoders,
multiple drivers, X/Z, naming collisions, unchanged source netlists and operator
labels. Existing integration tests cover RAM mapping, component hierarchy,
selective expansion with unexpanded siblings, project dependencies and SVG
loading. The original lab mux/extender cases remain regression fixtures.

## Deliberate limits

- These are synthesized binary logic diagrams. VHDL U/X/Z propagation and delta
  cycles belong in simulation; a binary-equivalent drawing need not reproduce
  nine-state VHDL behavior. X can mean a synthesis don't-care.
- Detailed is an RTL logic view: arithmetic, comparison and register operators
  remain symbols. It does not promise a transistor/FPGA technology implementation.
- Recognition is bounded to four independent selector bits and a small decoder
  cone. Larger or unsupported cones stay explicit. Priority chains need not look
  identical to parallel case statements, even if their functions match.
- GHDL's default rejection of inferred latches is retained. Diagnostics are
  surfaced; the renderer does not silently rewrite an incomplete assignment.
- The source hierarchy diagram represents source containment, not elaborated
  generate counts. The synthesized circuit is the elaborated hardware view.
- Existing memory/hierarchy tests check structural preservation and rendering;
  they are not a formal proof of every possible VHDL design or upstream compiler.

Future transformations should define a cell-level rule, preserve an untouched
synthesis artifact, refuse cases outside their proven domain, and add behavioral
or equivalence checks across multiple widths and topologies. Adding an entity-
or signal-name exception is not an acceptable general solution.
