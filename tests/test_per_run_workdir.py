"""Regression tests: each run gets its own work directory.

Every extraction used to write to one fixed path ($TMPDIR/book_skill_work),
so two runs started at the same time — routine when several agent sessions
share a machine — silently overwrote each other's full_text.txt and
metadata.json. Nothing errored: the run that finished second simply replaced
the first one's output, and an agent waiting on metadata.json could pick up a
*different document's* extraction and build a skill from the wrong source.

The default now carries the PID. BOOK_SKILL_WORKDIR still overrides it, and an
empty BOOK_SKILL_WORKDIR must not collapse to Path("") — i.e. the current
directory, which the run would then populate and chmod to 0700.
"""

import importlib
import os
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.config import default_output_dir  # noqa: E402


def _reimport_config(monkeypatch, workdir_env):
    """Re-evaluate config.py's module-level OUTPUT_DIR under a given env."""
    if workdir_env is None:
        monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    else:
        monkeypatch.setenv("BOOK_SKILL_WORKDIR", workdir_env)
    import book_to_skill.config as config

    return importlib.reload(config)


def test_default_workdir_is_unique_per_process(monkeypatch):
    """Two concurrent runs must not share a directory."""
    monkeypatch.setattr(os, "getpid", lambda: 1111)
    first = default_output_dir()
    monkeypatch.setattr(os, "getpid", lambda: 2222)
    second = default_output_dir()

    assert first != second
    assert "1111" in first.name
    assert "2222" in second.name


def test_default_workdir_is_sibling_not_child_of_legacy_path(monkeypatch):
    """An older cleanup that removes "book_skill_work" must not hit a live run.

    Nesting under the legacy directory would mean a stale cleanup routine
    deleting a concurrent extraction's output, which is worse than the bug
    being fixed. The per-run directory is therefore a sibling.
    """
    monkeypatch.setattr(os, "getpid", lambda: 4242)
    legacy = Path(tempfile.gettempdir()) / "book_skill_work"

    assert legacy not in default_output_dir().parents


def test_default_workdir_lives_in_tempdir(monkeypatch):
    monkeypatch.setattr(os, "getpid", lambda: 4242)

    assert default_output_dir().parent == Path(tempfile.gettempdir())


def test_env_override_wins(monkeypatch, tmp_path):
    chosen = tmp_path / "private-workdir"
    config = _reimport_config(monkeypatch, str(chosen))

    assert config.OUTPUT_DIR == chosen
    assert config.OUTPUT_TEXT == chosen / "full_text.txt"
    assert config.OUTPUT_META == chosen / "metadata.json"


def test_empty_env_override_does_not_become_cwd(monkeypatch):
    """BOOK_SKILL_WORKDIR="" must fall back, not resolve to Path("")."""
    config = _reimport_config(monkeypatch, "")

    assert config.OUTPUT_DIR != Path("")
    assert config.OUTPUT_DIR != Path.cwd()
    assert config.OUTPUT_DIR.parent == Path(tempfile.gettempdir())


def test_unset_env_uses_per_run_default(monkeypatch):
    config = _reimport_config(monkeypatch, None)

    assert config.OUTPUT_DIR.name.startswith("book_skill_work-")
    assert str(os.getpid()) in config.OUTPUT_DIR.name


def test_config_restored_for_other_tests(monkeypatch):
    """Reloading config in this module must not leak into the rest of the suite."""
    config = _reimport_config(monkeypatch, None)

    assert config.OUTPUT_TEXT.parent == config.OUTPUT_DIR
    assert config.OUTPUT_META.parent == config.OUTPUT_DIR
