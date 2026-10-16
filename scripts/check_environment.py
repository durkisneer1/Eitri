"""Report imports/backend readiness without creating a GUI window."""
import ghdl
import yosys
import netlistsvg
import gtkwave
import dearpygui.dearpygui as dpg

print("Dear PyGui: import OK")
print("GHDL:", ghdl.run(["--version"], capture_output=True, timeout=15).stdout.splitlines()[0])
print("Yosys:", yosys.run(["-V"], timeout=180).stdout.strip())
print("netlistsvg:", "packaged renderer ready" if netlistsvg.is_available() else "payload missing")
print("GTKWave:", str(gtkwave.executable()) if gtkwave.is_available() else "native viewer not installed (adapter import OK)")
