"""chapter_ranges for "Chapter N" headings found by the numeric scan (issue #348).

Outline books got line ranges; a PDF without an outline whose chapters were
found by the numeric scan got none, so Step 7 fell back to grep, whose first
hits are the table-of-contents lines rather than the body headings.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import book_to_skill.utils as utils  # noqa: E402

_BODY = "Body text that runs on for a while before the next heading arrives."

_WITH_TOC = [
    "Table of Contents",
    "",
    "Chapter 1. Searching Google",
    "Chapter 2. Advanced Operators",
    "Chapter 3. Research Habits",
    "",
    "Preface",
    _BODY,
    "",
    "Chapter 1. Searching Google",
    _BODY,
    "",
    "Chapter 2. Advanced Operators",
    _BODY,
    "",
    "Chapter 3. Research Habits",
    _BODY,
]


def test_ranges_start_at_body_headings_not_toc_entries():
    ranges = utils.numeric_chapter_line_ranges("\n".join(_WITH_TOC))
    assert [(r["title"], r["start_line"], r["end_line"]) for r in ranges] == [
        ("Chapter 1. Searching Google", 10, 12),
        ("Chapter 2. Advanced Operators", 13, 15),
        ("Chapter 3. Research Habits", 16, 17),
    ]


def test_running_headers_without_a_toc_keep_the_first_heading():
    lines = [
        "Chapter 1. Alpha",
        _BODY,
        "Chapter 1. Alpha",
        _BODY,
        "Chapter 2. Beta",
        _BODY,
        "Chapter 2. Beta",
        _BODY,
    ]
    ranges = utils.numeric_chapter_line_ranges("\n".join(lines))
    assert [(r["start_line"], r["end_line"]) for r in ranges] == [(1, 4), (5, 8)]


def test_numeric_chapter_ranges_in_extracted_metadata(tmp_path, monkeypatch):
    book = tmp_path / "book.txt"
    book.write_text("\n".join(_WITH_TOC) + "\n", encoding="utf-8")
    workdir = tmp_path / "out"
    monkeypatch.setattr(utils, "OUTPUT_DIR", workdir)
    monkeypatch.setattr(utils, "OUTPUT_TEXT", workdir / "full_text.txt")
    monkeypatch.setattr(utils, "OUTPUT_META", workdir / "metadata.json")
    monkeypatch.setattr(
        sys, "argv", ["extract", str(book), "--mode", "text", "--install-missing", "no"]
    )

    utils.main()

    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["chapters_method"] == "numeric"
    full_text = (workdir / "full_text.txt").read_text(encoding="utf-8").splitlines()
    starts = [full_text[r["start_line"] - 1] for r in metadata["chapter_ranges"]]
    assert starts == [
        "Chapter 1. Searching Google",
        "Chapter 2. Advanced Operators",
        "Chapter 3. Research Habits",
    ]
    assert metadata["chapter_ranges"][0]["start_line"] > 5
    assert len(metadata["sources"][0]["chapter_ranges"]) == 3


def test_a_chapter_missing_from_the_toc_keeps_its_range():
    lines = [line for line in _WITH_TOC if line != "Chapter 1. Searching Google"]
    lines.insert(lines.index("Chapter 2. Advanced Operators", 5), "Chapter 1. Searching Google")
    ranges = utils.numeric_chapter_line_ranges("\n".join(lines))
    assert [r["title"] for r in ranges] == [
        "Chapter 1. Searching Google",
        "Chapter 2. Advanced Operators",
        "Chapter 3. Research Habits",
    ]
