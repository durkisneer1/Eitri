# Eitri

I'm building Eitri as a small, modern VHDL workspace for my school lab assignments.

I wanted to work at home without installing a 30–40 GB Vivado setup full of features I'd never need just to learn VHDL. I couldn't find an alternative that felt both complete enough and modern enough for what I wanted, so I started making my own.

With Eitri, I can write designs and testbenches, reuse components, simulate signals, and see how my code becomes a circuit all in one app. It uses PySide6 for the interface, GHDL for VHDL simulation and synthesis, and Yosys with netlistsvg for circuit diagrams. My focus is learning and experimenting with VHDL, not replacing a complete FPGA implementation toolchain.

## A look inside

These screenshots show my 4-bit full adder, built from four 1-bit adders.

**Write designs and testbenches**

![VHDL editor showing my four-bit full adder](https://github.com/durkisneer1/Eitri/raw/refs/heads/main/docs/screenshots/code.png)

**Simulate and inspect waveforms**

![GHDL simulation showing adder inputs, sum and carry](https://github.com/durkisneer1/Eitri/raw/refs/heads/main/docs/screenshots/simulation.png)

**View component connections or expand them into logic gates**

![Simple circuit view showing four connected full-adder components](https://github.com/durkisneer1/Eitri/raw/refs/heads/main/docs/screenshots/circuit-simple.png)

![Detailed circuit view showing the full adder's logic gates](https://github.com/durkisneer1/Eitri/raw/refs/heads/main/docs/screenshots/circuit-detailed.png)

## Running Eitri

Eitri is available on [PyPI as `eitri-hdl`](https://pypi.org/project/eitri-hdl/). Install it with Python 3.11 or newer:

```sh
python -m pip install eitri-hdl
```

Then open the app from your terminal:

```sh
eitri
```

If you installed into a virtual environment, activate it before running `eitri`. You can also launch the app with `python -m eitri`.

[Editor guide](https://github.com/durkisneer1/Eitri/blob/main/docs/EDITOR.md) · [Simulation and circuit tools](https://github.com/durkisneer1/Eitri/blob/main/docs/TOOLS.md) · [GPL-3.0-or-later license](https://github.com/durkisneer1/Eitri/blob/main/LICENSE)

## Contributing to the app

See [docs/CONTRIBUTING.md](https://github.com/durkisneer1/Eitri/blob/main/docs/CONTRIBUTING.md) for a map of the UI modules,
signal flow, and where to add controls or change behavior. Start with
`src/eitri/ui/window.py` for the overall composition.
