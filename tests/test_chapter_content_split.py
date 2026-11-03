"""Outline chapter_ranges trim part conclusions and back matter."""

from __future__ import annotations

from book_to_skill.utils import chapter_line_ranges

_FILLER = "x" * 5000
_END_TITLES = [
    "Part I Conclusion",
    "Part II Conclusion",
    "Bibliography",
    "Index",
]


def _database_internals_fixture() -> tuple[str, list[str]]:
    lines: list[str] = []
    for number in range(1, 15):
        lines.append(f"CHAPTER {number}")
        lines.append(f"Topic {number}")
        lines.append(f"body-{number}")
        if number == 7:
            lines.extend(["Part I Conclusion", _FILLER, "part1-conclusion"])
        if number == 14:
            lines.extend(
                [
                    "Part II Conclusion",
                    _FILLER,
                    "part2-conclusion",
                    "Bibliography",
                    _FILLER,
                    "bib-content",
                    "Index",
                    _FILLER,
                    "index-content",
                ]
            )
    titles = [f"Chapter {n}. Topic {n}" for n in range(1, 15)]
    return "\n".join(lines), titles


def test_chapter_ranges_stop_before_part_conclusions_and_back_matter():
    text, titles = _database_internals_fixture()
    ranges = chapter_line_ranges(text, titles, range_end_titles=_END_TITLES)
    by_title = {entry["title"]: entry for entry in ranges}
    ch7 = by_title["Chapter 7. Topic 7"]
    ch14 = by_title["Chapter 14. Topic 14"]
    lines = text.splitlines()
    assert lines[ch7["end_line"]].startswith("Part I Conclusion")
    assert lines[ch14["end_line"]].startswith("Part II Conclusion")
    assert "Part I Conclusion" not in lines[ch7["start_line"] - 1 : ch7["end_line"]]
    assert "Bibliography" not in lines[ch14["start_line"] - 1 : ch14["end_line"]]


def test_page_headers_and_toc_leaders_do_not_start_chapters():
    text = "\n".join(
        [
            "  1. Introduction and Overview. . . . . . . . . . . . . . . . . 7",
            "806 | Chapter 1: Introduction and Overview",
            "                                                                        CHAPTER 1",
            "                                 Introduction and Overview",
            "body",
        ]
    )
    ranges = chapter_line_ranges(
        text, ["Chapter 1. Introduction and Overview"], range_end_titles=[]
    )
    assert len(ranges) == 1
    assert ranges[0]["start_line"] == 3


def test_lone_index_word_in_prose_does_not_end_chapter():
    text = "\n".join(
        [
            "CHAPTER 1",
            "Widgets",
            "We build an index structure for faster lookup.",
            "More body text.",
            "",
            "Part I Conclusion",
            "tail",
        ]
    )
    ranges = chapter_line_ranges(
        text,
        ["Chapter 1. Widgets"],
        range_end_titles=["Part I Conclusion"],
    )
    body = "\n".join(text.splitlines()[ranges[0]["start_line"] - 1 : ranges[0]["end_line"]])
    assert "index structure" in body
    assert "Part I Conclusion" not in body
