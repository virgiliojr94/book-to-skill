"""Regression tests: a leading "~" in an input path is expanded.

A glob has to be quoted to survive the shell and reach us as a pattern
("~/books/*.epub"), but quoting also stops the shell expanding the tilde.
`glob.glob` and `Path` both treat "~" as a literal directory name, so before
this fix the README's own quoted-glob example matched nothing and exited with
"No supported files found".
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import resolve_input_files  # noqa: E402


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Point ~ at a temp directory on POSIX and Windows alike."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def test_tilde_glob_matches_files(fake_home):
    """The README's quoted-glob example resolves instead of returning []."""
    books = fake_home / "books"
    books.mkdir()
    (books / "one.md").write_text("# One", encoding="utf-8")
    (books / "two.md").write_text("# Two", encoding="utf-8")

    result = resolve_input_files(["~/books/*.md"])

    assert [p.name for p in result] == ["one.md", "two.md"]


def test_tilde_file_resolves_under_home(fake_home):
    """A quoted "~/file.md" is a real path, not a "~" directory under cwd."""
    target = fake_home / "book.md"
    target.write_text("# Book", encoding="utf-8")

    result = resolve_input_files(["~/book.md"])

    assert result == [target.resolve()]
    assert "~" not in str(result[0])


def test_tilde_directory_is_walked(fake_home):
    """Directory expansion sees through the tilde too."""
    docs = fake_home / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A", encoding="utf-8")
    (docs / "ignored.bin").write_text("binary", encoding="utf-8")

    result = resolve_input_files(["~/docs"])

    assert [p.name for p in result] == ["a.md"]


def test_plain_paths_are_unchanged(tmp_path):
    """expanduser is a no-op for paths that do not start with "~"."""
    target = tmp_path / "plain.md"
    target.write_text("# Plain", encoding="utf-8")

    assert resolve_input_files([str(target)]) == [target.resolve()]


def test_unresolvable_tilde_user_is_left_alone(tmp_path, monkeypatch):
    """"~nosuchuser/..." has no expansion; it must stay reportable, not crash."""
    monkeypatch.chdir(tmp_path)

    result = resolve_input_files(["~nosuchuser-book-to-skill/book.md"])

    assert len(result) == 1
    assert result[0].name == "book.md"
