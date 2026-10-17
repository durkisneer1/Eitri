"""Keep repaired native-wheel compatibility in the final application wheel."""
from email.parser import Parser
from pathlib import Path
import runpy
from unittest.mock import patch

import pytest
from packaging.tags import parse_tag


@pytest.fixture
def release_setup():
    with patch("setuptools.setup"):
        return runpy.run_path(str(Path(__file__).resolve().parents[1] / "setup.py"))


@pytest.mark.parametrize("platform", [
    "manylinux_2_34_x86_64.manylinux_2_35_x86_64",
    "macosx_15_0_arm64",
    "win_amd64",
])
def test_native_platforms_survive_wheel_metadata(release_setup, tmp_path, monkeypatch, platform):
    wheel = tmp_path / f"ghdl_bundled-6.0.0.post1-py3-none-{platform}.whl"
    wheel.touch()
    monkeypatch.setenv("EITRI_GHDL_WHEEL", str(wheel))
    command = release_setup["PlatformWheel"](release_setup["BinaryDistribution"]())
    command.ensure_finalized()
    assert command.get_tag() == ("py3", "none", platform)
    metadata = tmp_path / "eitri_hdl-0.1.0.dist-info"
    metadata.mkdir()
    command.write_wheelfile(str(metadata))
    headers = Parser().parsestr((metadata / "WHEEL").read_text())
    assert headers["Root-Is-Purelib"] == "false"
    actual = {tag for value in headers.get_all("Tag") for tag in parse_tag(value)}
    assert actual == parse_tag(f"py3-none-{platform}")


@pytest.mark.parametrize("tag", ["py3-none-any", "cp312-cp312-manylinux_2_35_x86_64"])
def test_rejects_native_wheel_with_incompatible_tags(release_setup, tmp_path, monkeypatch, tag):
    wheel = tmp_path / f"ghdl_bundled-6.0.0.post1-{tag}.whl"
    wheel.touch()
    monkeypatch.setenv("EITRI_GHDL_WHEEL", str(wheel))
    with pytest.raises(RuntimeError, match="py3-none native wheel"):
        release_setup["native_wheel"]()
