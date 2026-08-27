"""
Guard against `extra={...}` keys that collide with LogRecord's own attributes.

`logging` builds a LogRecord and then copies `extra` onto it, raising
``KeyError: "Attempt to overwrite 'message' in LogRecord"`` if a key would shadow
a built-in attribute. It fails at call time, only on the branch that logs — so a
collision on a rarely-taken path (the draft-Style-DNA branch, in the case that
prompted this test) survives every other test and surfaces as a 500 in
production.

Scanning the source is the cheap way to catch all of them at once, including the
branches no test exercises.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "esports_poster_ai"

# logging.LogRecord's own attributes, plus the two that `Formatter` sets later
# (`message`, `asctime`) and `taskName` from Python 3.12.
RESERVED_LOG_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


def _extra_keys_in(path: Path):
    """Yield (lineno, key) for every literal key of an ``extra={...}`` argument."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "extra" or not isinstance(keyword.value, ast.Dict):
                continue
            for key in keyword.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    yield key.lineno, key.value


@pytest.mark.parametrize(
    "path", sorted(SRC.rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_log_extra_keys_do_not_shadow_logrecord(path: Path) -> None:
    collisions = [
        f"{path.relative_to(SRC)}:{lineno} uses reserved key {key!r}"
        for lineno, key in _extra_keys_in(path)
        if key in RESERVED_LOG_RECORD_ATTRS
    ]
    assert not collisions, (
        "logging `extra` keys must not shadow LogRecord attributes — "
        "this raises KeyError when the line runs:\n  " + "\n  ".join(collisions)
    )
