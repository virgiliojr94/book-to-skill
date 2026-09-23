"""Regression tests: the Calibre path must not reuse an earlier source's output.

`extract_with_ebook_convert()` treats "exit code 0 and the output file exists"
as success. The work directory is shared by every source in one batch, and by
separate runs whenever BOOK_SKILL_WORKDIR is set explicitly, so when a
conversion reports success without writing anything, output left by an earlier
source or an earlier *run* satisfies that check: one book's text is returned for
another source and recorded under *its* name in metadata.json. Nothing
downstream can tell, which is the same failure mode as the shared
work-directory bug (see test_per_run_workdir.py).

The fix converts into a fresh TemporaryDirectory per call, so "the file
exists" can only be true for a file this call wrote — regardless of what
earlier runs left behind, even with the same pid.

No Calibre install is required — `shutil.which` and `subprocess.run` are patched.
"""

import importlib
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.exceptions import ExtractionError  # noqa: E402

BOOK_A_TEXT = "TEXT OF BOOK A\n"


@pytest.fixture
def calibre_module(monkeypatch, tmp_path):
    """Import the parser against an isolated work directory.

    config reads BOOK_SKILL_WORKDIR at import time, so it is imported after the
    env var is set — and reloaded so a previously imported config cannot leave
    the real temp work directory in place.
    """
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(tmp_path))
    import book_to_skill.config as config

    importlib.reload(config)
    import book_to_skill.parsers.calibre as calibre

    importlib.reload(calibre)
    yield calibre, tmp_path
    # Leave the module-level OUTPUT_DIR pointing somewhere harmless for later tests.
    monkeypatch.delenv("BOOK_SKILL_WORKDIR", raising=False)
    importlib.reload(config)
    importlib.reload(calibre)


def _convert_without_writing(calibre, source_name="bookB.mobi"):
    """Model ebook-convert reporting success while writing nothing."""
    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", return_value=mock.Mock(returncode=0)):
        return calibre.extract_with_ebook_convert(source_name)


def test_output_name_is_unique_per_call(calibre_module):
    """Two conversions must not share one output file."""
    calibre, workdir = calibre_module
    seen = []

    def record_output_path(argv, **_kwargs):
        seen.append(Path(argv[2]))
        Path(argv[2]).write_text(f"text {len(seen)}\n", encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=record_output_path):
        first = calibre.extract_with_ebook_convert("bookA.mobi")
        second = calibre.extract_with_ebook_convert("bookB.mobi")

    assert first == "text 1\n"
    assert second == "text 2\n", "the second conversion read the first one's file"
    assert seen[0] != seen[1]
    # Both live inside the shared work directory (in per-call subdirectories)...
    assert seen[0].parent.parent == workdir and seen[1].parent.parent == workdir
    # ...but in different per-call directories, and neither survives the call.
    assert seen[0].parent != seen[1].parent
    leftovers = [p for p in workdir.iterdir()]
    assert leftovers == [], "per-call directories must be cleaned up on exit"


def test_success_without_output_does_not_reuse_an_earlier_result(calibre_module):
    """A previous source's output must not satisfy a later, empty conversion."""
    calibre, workdir = calibre_module

    def run_writes_output(argv, **_kwargs):
        Path(argv[2]).write_text(BOOK_A_TEXT, encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=run_writes_output):
        text_a = calibre.extract_with_ebook_convert("bookA.mobi")
    assert text_a == BOOK_A_TEXT

    # Same run, next source: success reported, nothing written.
    assert _convert_without_writing(calibre) is None

    # And nothing from either conversion is left in the work directory.
    leftovers = [p for p in workdir.iterdir()]
    assert leftovers == [], "per-call directories must be cleaned up on exit"


def test_reused_workdir_with_same_pid_across_interpreters(calibre_module):
    """Two fresh interpreters sharing a workdir, same mocked pid: no reuse.

    This is the shape the reviewer demonstrated: a per-process unique name
    (pid + counter) is not unique *across runs*, because a reused pid in a
    second interpreter collapses back to the first run's name. A fresh
    TemporaryDirectory per call cannot be addressed from outside the call, so
    the second conversion cannot be satisfied by the first run's output.
    """
    calibre, workdir = calibre_module

    def run_writes_output(argv, **_kwargs):
        Path(argv[2]).write_text(BOOK_A_TEXT, encoding="utf-8")
        return mock.Mock(returncode=0)

    # "First interpreter": converts successfully under the reused pid.
    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=run_writes_output), \
         mock.patch.object(calibre.os, "getpid", return_value=4242):
        first = calibre.extract_with_ebook_convert("bookA.mobi")
    assert first == BOOK_A_TEXT

    # Simulate a fresh interpreter seeing the same shared work directory:
    # pid is reused (mocked), the module state (any counters) is reset, and a
    # plant from the first run occupies the name the old scheme would reuse.
    importlib.reload(calibre)
    plant = workdir / "ebook-convert-output-4242-0.txt"
    plant.write_text("STALE TEXT FROM ANOTHER RUN\n", encoding="utf-8")

    # "Second interpreter": reports success, writes nothing.
    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", return_value=mock.Mock(returncode=0)), \
         mock.patch.object(calibre.os, "getpid", return_value=4242):
        second = calibre.extract_with_ebook_convert("bookB.mobi")

    assert second is None, "the second run was satisfied by the first run's file"
    # The plant itself is untouched — the fix ignores rather than deletes it.
    assert plant.read_text(encoding="utf-8") == "STALE TEXT FROM ANOTHER RUN\n"


def test_success_with_existing_output_still_returns_text(calibre_module):
    """The guard must still accept a conversion that genuinely writes output."""
    calibre, _workdir = calibre_module

    def run_writes_output(argv, **_kwargs):
        Path(argv[2]).write_text("FRESH BODY\n", encoding="utf-8")
        return mock.Mock(returncode=0)

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", side_effect=run_writes_output):
        assert calibre.extract_with_ebook_convert("book.mobi") == "FRESH BODY\n"


def test_nonzero_exit_returns_none(calibre_module):
    """A failed conversion stays a failure, whether or not a file exists."""
    calibre, workdir = calibre_module
    (workdir / "leftover.txt").write_text("STALE\n", encoding="utf-8")

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.subprocess, "run", return_value=mock.Mock(returncode=1)):
        assert calibre.extract_with_ebook_convert("book.mobi") is None


def test_missing_ebook_convert_returns_none(calibre_module):
    """No Calibre on PATH is a skip, not an error."""
    calibre, _workdir = calibre_module

    with mock.patch.object(calibre.shutil, "which", return_value=None):
        assert calibre.extract_with_ebook_convert("book.mobi") is None


def test_unwritable_output_dir_raises(calibre_module):
    """A work directory that cannot host the temp dir fails loudly.

    Swallowing the OSError and returning None would be indistinguishable from
    "converted fine, wrote nothing" — the silent-failure shape this function
    refuses. The exception names the directory and the cause.
    """
    calibre, workdir = calibre_module
    unwritable = workdir / "not-a-dir"
    unwritable.write_text("occupied\n", encoding="utf-8")

    with mock.patch.object(calibre.shutil, "which", return_value="/usr/bin/ebook-convert"), \
         mock.patch.object(calibre.tempfile, "TemporaryDirectory") as tmp_dir:
        tmp_dir.side_effect = OSError(13, "Permission denied")
        with pytest.raises(ExtractionError, match="cannot create a conversion directory"):
            calibre.extract_with_ebook_convert("book.mobi")
