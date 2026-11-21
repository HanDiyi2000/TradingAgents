"""Run the original analysis example from the repository root."""

from pathlib import Path
from runpy import run_path

if __name__ == "__main__":
    run_path(str(Path(__file__).parent / "src" / "main.py"), run_name="__main__")
