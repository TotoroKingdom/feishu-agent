"""Backward-compatible wrapper for the full local CI command."""

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.full_ci_local import main


if __name__ == "__main__":
    main()
