"""Private subprocess entry point; never starts on import."""
import sys

if __name__ == "__main__":
    from yowasp_yosys import run_yosys
    sys.exit(run_yosys(sys.argv[1:]))
