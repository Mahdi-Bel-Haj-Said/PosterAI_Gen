"""
Tests for project-root discovery — no network, no filesystem beyond tmp_path.

These exist because of a production outage: the VPS installed the package with
`pip install .`, which copies it into `site-packages`. The old
`Path(__file__).parents[2]` then resolved to `<venv>/lib/pythonX.Y`, so every
data directory pointed inside the virtualenv and generation failed with
"Backgrounds directory not found" for a directory that was present the whole
time. Case B below is that exact layout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from esports_poster_ai.config import _detect_project_root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal project tree: marker file plus a data directory."""
    root = tmp_path / "repo"
    (root / "backgrounds").mkdir(parents=True)
    (root / "src" / "esports_poster_ai").mkdir(parents=True)
    (root / "pyproject.toml").touch()
    return root


def test_editable_src_layout(repo: Path):
    """The `src/` layout — dev machines and an editable install."""
    config_py = repo / "src" / "esports_poster_ai" / "config.py"
    config_py.touch()
    assert _detect_project_root(config_py) == repo


def test_copied_into_venv_inside_repo(repo: Path):
    """`pip install .` with the venv inside the repo — the layout that broke."""
    pkg = repo / ".venv" / "lib" / "python3.10" / "site-packages" / "esports_poster_ai"
    pkg.mkdir(parents=True)
    config_py = pkg / "config.py"
    config_py.touch()
    assert _detect_project_root(config_py) == repo


def test_falls_back_to_cwd_when_package_is_elsewhere(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Venv outside the repo — systemd's WorkingDirectory identifies the root."""
    pkg = tmp_path / "elsewhere" / "site-packages" / "esports_poster_ai"
    pkg.mkdir(parents=True)
    config_py = pkg / "config.py"
    config_py.touch()

    monkeypatch.chdir(repo)
    assert _detect_project_root(config_py) == repo


def test_env_override_wins(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An explicit override beats every heuristic."""
    monkeypatch.setenv("EPAI_PROJECT_ROOT", str(repo))
    stray = tmp_path / "somewhere" / "config.py"
    stray.parent.mkdir(parents=True)
    stray.touch()
    assert _detect_project_root(stray) == repo
