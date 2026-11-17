"""Run this analysis. Commands are listed in README.md. Do not edit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_engine"))
import engine  # noqa: E402

sys.exit(engine.main())
