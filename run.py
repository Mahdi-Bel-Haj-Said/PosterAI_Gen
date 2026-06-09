"""
Thin shim that preserves `python run.py --input ...` without requiring
`pip install -e .` first. Adds `src/` to sys.path and delegates to the
package CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from esports_poster_ai.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
