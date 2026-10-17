"""One public distribution, assembled from adapters and a repaired GHDL wheel.

Set EITRI_GHDL_WHEEL to a wheel produced by the native workflow. Never retag
native binaries: the application inherits the input wheel's platform tag.
"""
import os
from pathlib import Path, PurePosixPath
import zipfile

from packaging.utils import parse_wheel_filename
from setuptools import Distribution, find_packages, setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py

ROOT = Path(__file__).parent


def native_wheel():
    path = Path(os.environ.get("EITRI_GHDL_WHEEL", ""))
    if not path.is_file():
        raise RuntimeError("Set EITRI_GHDL_WHEEL to a built, repaired ghdl-bundled wheel")
    name, version, _, tags = parse_wheel_filename(path.name)
    if name != "ghdl-bundled" or str(version) != "6.0.0.post1":
        raise RuntimeError("Expected ghdl-bundled 6.0.0.post1")
    platforms = {tag.platform for tag in tags}
    if "any" in platforms or any(
        tag.interpreter != "py3" or tag.abi != "none" for tag in tags
    ):
        raise RuntimeError("Expected a py3-none native wheel")
    # auditwheel may advertise multiple compatible manylinux policies. Keep
    # the complete compressed platform field, including its original order.
    return path, path.stem.rsplit("-", 1)[1]


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


class BundledBuild(build_py):
    def run(self):
        wheel, _ = native_wheel()
        payload = ROOT / "packages/netlistsvg/src/netlistsvg/_vendor/node_modules/netlistsvg/bin/netlistsvg.js"
        if not payload.is_file():
            raise RuntimeError("Run scripts/prepare_netlistsvg.py before building")
        super().run()
        with zipfile.ZipFile(wheel) as archive:
            for member in archive.infolist():
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise RuntimeError("Unsafe wheel member")
                if member.is_dir():
                    continue
                if path.parts[0].endswith(".dist-info"):
                    if len(path.parts) < 3 or path.parts[1] != "licenses":
                        continue
                    path = PurePosixPath("ghdl", "_licenses", *path.parts[2:])
                if path.parts[0].endswith(".data"):
                    raise RuntimeError("Unsupported wheel .data layout")
                target = Path(self.build_lib).joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
                target.chmod((member.external_attr >> 16) & 0o777 or 0o644)


class PlatformWheel(bdist_wheel):
    def get_tag(self):
        _, platform = native_wheel()
        return "py3", "none", platform


setup(
    packages=find_packages("src") + ["yosys", "netlistsvg", "gtkwave"],
    package_dir={"": "src", **{
        name: f"packages/{name}/src/{name}"
        for name in ("yosys", "netlistsvg", "gtkwave")
    }},
    distclass=BinaryDistribution,
    cmdclass={"build_py": BundledBuild, "bdist_wheel": PlatformWheel},
)
