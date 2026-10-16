"""Platform wheels containing executables/ctypes libraries, no CPython ABI."""
from pathlib import Path
from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


class PlatformWheel(bdist_wheel):
    def run(self):
        root = Path(__file__).parent / "src" / "ghdl" / "_native"
        if not any((root / "bin").glob("ghdl*")):
            raise RuntimeError("Build and stage GHDL first; see scripts/build-native.sh")
        if not any((root / "lib").glob("libghdl-*")):
            raise RuntimeError("The wheel must contain libghdl and matching bindings")
        super().run()

    def get_tag(self):
        _, _, platform = super().get_tag()
        return "py3", "none", platform


setup(distclass=BinaryDistribution, cmdclass={"bdist_wheel": PlatformWheel})
