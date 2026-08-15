"""Regression test: a filename containing a literal "[" or "]" resolves as
a literal path, not a glob character class.

`resolve_input_files()` treated any path containing "*", "?", or "[" as a
glob pattern, even when the path already exists on disk as-is. A filename
like "The C++ Programming Language [4th Edition].pdf" was mangled by
`glob.glob()`'s character-class syntax and matched nothing, so the CLI
failed with "No supported files found" even though the file exists.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import resolve_input_files  # noqa: E402


def test_literal_bracket_filename_resolves(tmp_path):
    target = tmp_path / "The C++ Programming Language [4th Edition].pdf"
    target.write_bytes(b"%PDF-1.4")

    result = resolve_input_files([str(target)])

    assert result == [target.resolve()]


def test_literal_bracket_directory_is_walked(tmp_path):
    books = tmp_path / "[Archive] Books"
    books.mkdir()
    (books / "one.md").write_text("# One", encoding="utf-8")

    result = resolve_input_files([str(books)])

    assert [p.name for p in result] == ["one.md"]


def test_real_glob_patterns_still_expand(tmp_path):
    (tmp_path / "one.md").write_text("# One", encoding="utf-8")
    (tmp_path / "two.md").write_text("# Two", encoding="utf-8")

    result = resolve_input_files([str(tmp_path / "*.md")])

    assert [p.name for p in result] == ["one.md", "two.md"]


def test_nonexistent_bracket_path_falls_through_to_glob(tmp_path):
    missing = tmp_path / "[missing].pdf"

    result = resolve_input_files([str(missing)])

    assert result == []
