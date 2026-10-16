from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

class CheckedBuild(build_py):
    def run(self):
        payload = Path(__file__).parent / "src/netlistsvg/_vendor/node_modules/netlistsvg/bin/netlistsvg.js"
        if not payload.is_file():
            raise RuntimeError("Prepare JavaScript payload with scripts/prepare_netlistsvg.py first")
        super().run()

setup(cmdclass={"build_py": CheckedBuild})
