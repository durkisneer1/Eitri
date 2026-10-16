"""Installed-wheel integration test; intentionally independent of pytest."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

# Deliberately remove toolchain paths and existing GHDL configuration.
for key in ("GHDL", "GHDL_PREFIX", "VUNIT_GHDL_PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
    os.environ.pop(key, None)
scripts = Path(sys.executable).parent
os.environ["PATH"] = str(scripts)
if os.name == "nt":
    os.environ["PATH"] += os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")

import ghdl

assert "site-packages" in str(ghdl.__file__), ghdl.__file__
assert ghdl.executable().is_file()
cli = shutil.which("ghdl")
assert cli, "Wheel did not register the ghdl console command"
subprocess.run([cli, "--version"], check=True)
subprocess.run([sys.executable, "-m", "ghdl", "--version"], check=True)
for command in ("ghdl-dom", "ghdl-ls"):
    entrypoint = shutil.which(command)
    assert entrypoint, command
    subprocess.run([entrypoint, "--help"], check=True, capture_output=True, timeout=30)
result = ghdl.run(["--version"], capture_output=True)
assert "GHDL 6.0.0" in result.stdout

with tempfile.TemporaryDirectory(prefix="ghdl wheel smoke ") as directory:
    os.chdir(directory)
    Path("gate.vhd").write_text('''
library ieee;
use ieee.std_logic_1164.all;
entity gate is port(a, b: in std_logic; y: out std_logic); end;
architecture rtl of gate is begin y <= a and b; end;
''')
    Path("tb.vhd").write_text('''
library ieee;
use ieee.std_logic_1164.all;
entity tb is end;
architecture test of tb is
  signal a, b, y: std_logic := '0';
begin
  dut: entity work.gate port map(a, b, y);
  process begin
    wait for 1 ns;
    assert y = '0' report "initial gate output incorrect" severity failure;
    a <= '1'; b <= '1';
    wait for 1 ns;
    assert y = '1' report "gate output incorrect" severity failure;
    report "WHEEL_SIMULATION_OK";
    wait;
  end process;
end;
''')
    ghdl.run(["-a", "--std=08", "gate.vhd", "tb.vhd"])
    ghdl.run(["-e", "--std=08", "tb"])
    simulated = ghdl.run(["-r", "--std=08", "tb", "--assert-level=error", "--vcd=wave.vcd"],
                         capture_output=True, timeout=30)
    assert "WHEEL_SIMULATION_OK" in simulated.stdout + simulated.stderr
    assert Path("wave.vcd").stat().st_size > 0
    synthesized = ghdl.run(["--synth", "--std=08", "gate"], capture_output=True, timeout=30)
    assert "entity gate" in synthesized.stdout.lower()
    failed = ghdl.run(["-a", "nonexistent.vhd"], check=False, capture_output=True)
    assert failed.returncode != 0
    # Direct import must select the bundled library even with a conflicting prefix.
    os.environ["GHDL_PREFIX"] = str(Path(directory) / "nonexistent-prefix")
    from pyGHDL import libghdl
    assert ghdl.libghdl() is libghdl
    from pyGHDL.libghdl import errorout_console
    libghdl.initialize()
    errorout_console.Install_Handler()
    assert libghdl.set_option("--std=08")
    assert libghdl.analyze_init_status() == 0
    assert libghdl.analyze_file("gate.vhd") != 0
print("CLI, Python wrapper, simulation, IEEE libraries, synthesis and libghdl passed")
