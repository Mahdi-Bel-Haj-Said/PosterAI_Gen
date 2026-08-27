"""
Pytest configuration. Adds `src/` to sys.path so tests can `import
esports_poster_ai` without requiring `pip install -e .`, and pins the
deployment-toggle settings so the suite is hermetic.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# ---------------------------------------------------------------------------
# Hermetic settings.
#
# `Settings` reads the repo's real `.env`, so anything a developer flips there
# leaks into the tests. Turning on API_KEY_REQUIRED (which production needs)
# makes 34 API tests fail purely because they don't send a Bearer key — a red
# suite that says nothing about the code.
#
# These toggles are deployment posture, not behaviour under test, so pin them to
# the single-tenant defaults the API tests were written against. A test that
# wants the enforced path should set it explicitly and clear the settings cache:
#
#     monkeypatch.setenv("API_KEY_REQUIRED", "true")
#     get_settings.cache_clear()
#
# Set before any import of `esports_poster_ai.config`, because `get_settings` is
# `lru_cache`d and the first call wins for the whole session.
# ---------------------------------------------------------------------------
_TEST_ENV_DEFAULTS = {
    "API_KEY_REQUIRED": "false",
    "WEBHOOKS_ENABLED": "false",
    "CORS_ALLOW_ORIGINS": "*",
}

for _name, _value in _TEST_ENV_DEFAULTS.items():
    os.environ[_name] = _value
