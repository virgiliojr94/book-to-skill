"""Outline chapter titles that wrap onto three lines under a CHAPTER marker.

Long chapter titles in typeset PDFs are set on a large display font and wrap
onto three lines below the right-aligned ``CHAPTER N`` marker. The marker
branch only joined up to two lines, so such a chapter was never found and the
previous chapter's range swallowed it. Synthetic fixture (no source-book text).
"""

from __future__ import annotations

from book_to_skill.utils import chapter_line_ranges

_TITLES = [
    "Chapter 10 Widget Basics",
    "Chapter 11 Widget Assembly, Widget Painting, Default Widgets, and Troubleshooting",
    "Chapter 12 Final Review",
]

_LINES = [
    "                                                     CHAPTER 10",  # 1
    "",
    "Widget Basics",  # 3
    "   body of chapter ten",
    "Chapter 10: Widget Basics   601",  # running header, not a start
    "",
    "                                                     CHAPTER 11",  # 7
    "",
    "Widget Assembly, Widget",
    "Painting, Default Widgets, and",
    "Troubleshooting",
    "   body of chapter eleven",
    "Chapter 11: Widget Assembly, Widget Painting, Default Widgets, and Troubleshooting   635",
    "",
    "                                                     CHAPTER 12",  # 15
    "",
    "Final Review",
    "   body of chapter twelve",
]


def test_title_wrapped_onto_three_lines_under_marker_is_found():
    ranges = chapter_line_ranges("\n".join(_LINES), _TITLES)
    starts = {entry["title"]: entry["start_line"] for entry in ranges}
    assert starts == {_TITLES[0]: 1, _TITLES[1]: 7, _TITLES[2]: 15}
    by_title = {entry["title"]: entry for entry in ranges}
    # chapter 10 must end before chapter 11's marker instead of swallowing it
    assert by_title[_TITLES[0]]["end_line"] < 7


def test_three_line_join_requires_the_whole_title():
    # Only the first two of three title lines present -> no false match.
    lines = _LINES[:6] + [
        "                                                     CHAPTER 11",
        "",
        "Widget Assembly, Widget",
        "Painting, Default Widgets, and",
        "   body text that is not the title",
    ]
    ranges = chapter_line_ranges("\n".join(lines), _TITLES[:2])
    assert [entry["title"] for entry in ranges] == [_TITLES[0]]
