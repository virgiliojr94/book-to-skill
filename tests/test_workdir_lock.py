"""Concurrent extractions must not silently share one workdir.

Kept in its own file so it does not collide with upstream edits to
test_book_to_skill.py on a future pull.

BOOK_SKILL_WORKDIR defaults to a single <tempdir>/book_skill_work for every
run, so two extractions running at once overwrite each other's full_text.txt.
The damage is silent: the losing run still writes its own metadata.json, which
then describes text it did not produce. claim_workdir() makes the second run
refuse to start instead.
"""
import os

import pytest

from book_to_skill.exceptions import ExtractionError
from book_to_skill.utils import claim_workdir, release_workdir, _WORKDIR_LOCK_NAME


def test_claim_creates_workdir_and_lock(tmp_path):
    wd = tmp_path / "work"
    claim_workdir(wd)
    assert wd.is_dir()
    assert (wd / _WORKDIR_LOCK_NAME).read_text().strip() == str(os.getpid())


def test_same_process_can_reclaim(tmp_path):
    """Re-entry within one run is not a collision."""
    wd = tmp_path / "work"
    claim_workdir(wd)
    claim_workdir(wd)  # must not raise


def test_live_holder_blocks_second_run(tmp_path):
    """A different, living PID means a concurrent run: refuse."""
    wd = tmp_path / "work"
    wd.mkdir()
    # PID 1 always exists and is never this process.
    (wd / _WORKDIR_LOCK_NAME).write_text("1")

    with pytest.raises(ExtractionError) as exc:
        claim_workdir(wd)
    msg = str(exc.value)
    assert "already in use" in msg
    assert "BOOK_SKILL_WORKDIR" in msg, "the error must name the way out"


def test_stale_lock_is_reclaimed(tmp_path):
    """A crashed run must not wedge the next one."""
    wd = tmp_path / "work"
    wd.mkdir()
    dead = _find_unused_pid()
    (wd / _WORKDIR_LOCK_NAME).write_text(str(dead))

    claim_workdir(wd)  # must not raise
    assert (wd / _WORKDIR_LOCK_NAME).read_text().strip() == str(os.getpid())


@pytest.mark.parametrize("junk", ["", "   ", "not-a-pid", "\x00"])
def test_unreadable_lock_is_treated_as_free(tmp_path, junk):
    wd = tmp_path / "work"
    wd.mkdir()
    (wd / _WORKDIR_LOCK_NAME).write_text(junk)
    claim_workdir(wd)  # must not raise


def test_release_removes_only_our_lock(tmp_path):
    wd = tmp_path / "work"
    claim_workdir(wd)
    release_workdir(wd)
    assert not (wd / _WORKDIR_LOCK_NAME).exists()

    (wd / _WORKDIR_LOCK_NAME).write_text("1")
    release_workdir(wd)
    assert (wd / _WORKDIR_LOCK_NAME).exists(), "must not steal another run's lock"


def test_release_is_safe_when_absent(tmp_path):
    release_workdir(tmp_path / "never-created")  # must not raise


def _find_unused_pid() -> int:
    for pid in range(320000, 400000):
        try:
            os.kill(pid, 0)
        except OSError:
            return pid
    pytest.skip("no free PID found to simulate a stale lock")
