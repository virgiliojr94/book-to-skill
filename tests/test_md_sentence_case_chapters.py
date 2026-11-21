"""Sentence-case Markdown chapter titles stay on the numeric path.

``## Chapter 1 Title`` is numeric, so sibling headings are not chapters.
``## Chapter 1 title`` used to fail the lowercase-prose guard, and
``detect_structure`` then counted Background and Methods as chapters too.
A bare ``Chapter 1 title`` line is still prose.
"""

from book_to_skill.utils import _chapter_number, detect_structure


def _book(chapter_one: str, chapter_two: str) -> str:
    return "\n".join([
        "## Background",
        "intro",
        chapter_one,
        "body one",
        "## Methods",
        "body two",
        chapter_two,
        "body three",
    ])


def test_sentence_case_markdown_chapters_are_numeric():
    result = detect_structure(_book("## Chapter 1 title", "## Chapter 2 title"))

    assert result["chapters_detected"] == 2
    assert result["chapters_method"] == "numeric"
    assert result["chapter_headings_sample"] == [
        "## Chapter 1 title",
        "## Chapter 2 title",
    ]


def test_title_case_markdown_chapters_unchanged():
    result = detect_structure(_book("## Chapter 1 Title", "## Chapter 2 Title"))

    assert result["chapters_detected"] == 2
    assert result["chapters_method"] == "numeric"
    assert result["chapter_headings_sample"] == [
        "## Chapter 1 Title",
        "## Chapter 2 Title",
    ]


def test_bare_lowercase_continuation_is_still_prose():
    assert _chapter_number("## Chapter 1 title") == 1
    assert _chapter_number("== Chapter 3 title") == 3
    assert _chapter_number("Chapter 1 title") is None
    assert _chapter_number("Chapter 6 explores the topic in depth") is None
