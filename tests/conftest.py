"""
Pytest configuration. Adds `src/` to sys.path so tests can `import
esports_poster_ai` without requiring `pip install -e .`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
