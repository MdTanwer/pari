"""Executable module entrypoint for PARI.

Allows running PARI via:
    python -m pari
    python -m pari.cli
"""

import sys

from pari.cli import main


if __name__ == "__main__":
    sys.exit(main())
