# Tool APIs used by the application

These functions can be called from ordinary Python functions, including functions
connected to Qt signals. There are no UI dependencies in the adapters.

```python
import ghdl
import yosys
import netlistsvg
import gtkwave

analysis = ghdl.run(["-a", "--std=08", "design.vhd", "tb.vhd"],
                    cwd=project_directory, capture_output=True, timeout=60)
simulation = ghdl.run(["-r", "--std=08", "tb", "--vcd=wave.vcd"],
                      cwd=project_directory, capture_output=True, timeout=60)
synthesis = yosys.run_script("read_verilog design.v; prep -top top; write_json netlist.json",
                            cwd=project_directory, timeout=180)
svg_path = netlistsvg.render(project_directory / "netlist.json",
                            project_directory / "schematic.svg")
viewer_process = gtkwave.launch(project_directory / "wave.vcd")
```

`project_directory` is your own `pathlib.Path`. The synthesis example uses Verilog;
for synthesizable VHDL, first capture `ghdl.run(["--synth", "--std=08",
"--out=verilog", "design.vhd", "-e", "top"], capture_output=True).stdout` to a
Verilog file, then use Yosys. GHDL's supported VHDL synthesis subset applies.

| Function | Returns | Execution |
|---|---|---|
| `ghdl.run(args, ...)` | `subprocess.CompletedProcess` | Blocking, isolated native process |
| `ghdl.libghdl()` | Upstream low-level API module | In-process native library |
| `yosys.run(args, ...)` | `subprocess.CompletedProcess[str]` | Blocking, isolated YoWASP process |
| `yosys.run_script(script, ...)` | Same | Same, Yosys command language |
| `yosys.libyosys()` | `pyosys.libyosys` | In-process native library, macOS/Linux |
| `netlistsvg.render(json_path, svg_path, skin=None, timeout=60)` | Absolute `Path` to SVG | Blocking, isolated Node process |
| `gtkwave.launch(waveform, savefile=None, ...)` | `subprocess.Popen` | Returns immediately; separate viewer window |
| `gtkwave.is_available()` | `bool` | Checks discovery; no viewer launch |
| `gtkwave.version()` | `subprocess.CompletedProcess[str]` | Checks external viewer version |

Subprocess failures raise `subprocess.CalledProcessError`; captured diagnostics
are on `.stdout` / `.stderr`. Time limits raise `subprocess.TimeoutExpired`.
GHDL and Yosys accept `check=False` to inspect nonzero returns yourself. No shell
is used. Avoid interpolating untrusted filenames into the Yosys script language;
use a controlled working directory and quote according to Yosys syntax.

For lengthy jobs, your app should submit these blocking functions to a worker and
present the result afterward. Do not execute long synthesis jobs on the render
thread or update Qt widgets from tool adapters. Native `libghdl`/`libyosys` have global
state and object-lifetime constraints; do not concurrently share native objects
between callbacks. Process wrappers are the default for isolated jobs.

Use a worker for long tool jobs and deliver results to the GUI through Qt signals.
The Qt workspace connects these adapters through the separate-process pipelines
in `src/eitri/backend/pipeline.py`; see `docs/TOOLS.md`.

References:
- https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html
- https://yosyshq.readthedocs.io/projects/yosys/en/stable/using_yosys/pyosys.html
- https://github.com/nturley/netlistsvg
