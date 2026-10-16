import sys
from . import run


def main():
    try:
        result = run(sys.argv[1:], check=False)
        return result.returncode if result.returncode >= 0 else 128 - result.returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
