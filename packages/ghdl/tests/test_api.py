import subprocess
from unittest.mock import patch
import pytest
import ghdl


def test_arguments_are_not_shell_interpreted(tmp_path):
    binary = tmp_path / "path with spaces" / "ghdl"
    with patch("ghdl.executable", return_value=binary), patch("ghdl.subprocess.run") as run:
        ghdl.run(["-a", "file with spaces;literal.vhd"], env={"GHDL_PREFIX": "/wrong"})
        args, kwargs = run.call_args
        assert args[0] == [str(binary), "-a", "file with spaces;literal.vhd"]
        assert kwargs.get("shell", False) is False
        assert kwargs["env"]["GHDL_PREFIX"].endswith("lib/ghdl")


def test_reject_shell_string():
    with pytest.raises(TypeError):
        ghdl.run("-a file.vhd")


def test_failure_is_not_swallowed():
    with patch("ghdl.executable"), patch("ghdl.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ghdl")):
        with pytest.raises(subprocess.CalledProcessError):
            ghdl.run(["-a", "bad.vhd"])
