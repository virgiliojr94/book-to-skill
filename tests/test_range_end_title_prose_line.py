"""A wrapped prose line equal to a front-matter title must not end a chapter.

Top-level outline titles such as "Contents" or "Index" are used as range-end
markers. A paragraph that wraps so that its last line is just "contents." used
to normalize to "contents" and cut the chapter in mid-paragraph. Synthetic
fixture (no source-book text).
"""

from __future__ import annotations

from book_to_skill.utils import chapter_line_ranges

_TITLES = ["Chapter 1. Widgets", "Chapter 2. Gadgets"]

_LINES = [
    "CHAPTER 1",  # 1
    "Widgets",
    "   A summary message never carries the database",
    "   contents.",  # 4: prose continuation, not the "Contents" heading
    "",
    "   More widget text that belongs to chapter one.",  # 6
    "CHAPTER 2",  # 7
    "Gadgets",
    "   gadget text",
    "",
    "Index",  # 11: a real end-matter heading still ends the range
    "",
    "   index entries",
]


def test_prose_line_matching_end_title_does_not_cut_chapter():
    ranges = chapter_line_ranges(
        "\n".join(_LINES), _TITLES, range_end_titles=["Contents", "Index"]
    )
    by_title = {entry["title"]: entry for entry in ranges}
    assert by_title["Chapter 1. Widgets"]["end_line"] == 6
    assert by_title["Chapter 2. Gadgets"]["end_line"] == 10
