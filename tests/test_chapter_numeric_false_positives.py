"""Prose and code lines must not turn into chapters in the numeric scan.

`detect_structure()` counts distinct numbers from explicit "Chapter N" headings,
and that count wins over the structural (Markdown) count as soon as two numbers
match. Two shapes of ordinary input produced numbers that were not headings
(issue #237):

* a sentence wrapped at the column limit, where the continuation line starts
  with a cross-reference —
  ``...as we cover in\\nChapter 6. Closures create types that only the compiler...``
  — and the capital letter after the period defeats the lowercase-only prose
  guard in ``_HEADING_TAIL``;
* a code sample holding a unified diff, where ``1  + use crate::trpl::StreamExt;``
  satisfies the plain numbered-heading pattern.

The tail of a heading is judged from the line above it: a period tail is prose
when the paragraph continues into it and the tail reads as a sentence rather
than a title. A line that stands on its own keeps its heading, including a bare
"Chapter 6.".
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import _chapter_number, detect_structure

CHAPTER_BODY = "prose carrying the section's actual content. " * 40

# A sentence wrapped at the column limit: the continuation line opens with the
# cross-reference and the previous line does not end a sentence.
WRAP_PREV = "The borrow checker rules are explained in more detail as we cover in"
WRAP_LINE = "Chapter 4. References are indicated by the & symbol and borrow the value they"

FENCED_DIFF = "```diff\n1  + use crate::trpl::StreamExt;\n2  - use std::io::prelude::*;\n```\n"


class TestWrappedProseIsNotAChapter:
    def test_capitalized_continuation_line_is_not_a_heading(self):
        assert _chapter_number(WRAP_LINE, prev_line=WRAP_PREV) is None

    def test_parenthetical_continuation_line_is_not_a_heading(self):
        line = "Chapter 17.) We have seen a solution to this problem a few times now: We can"
        assert _chapter_number(line, prev_line=WRAP_PREV) is None

    def test_standalone_period_heading_is_kept(self):
        # "Chapter 6." on a line of its own carries no context that makes it
        # prose, so it stays a heading (see the maintainer note on #237).
        assert _chapter_number("Chapter 6.") == 6

    def test_bare_tail_inside_a_wrapped_sentence_is_not_a_heading(self):
        # "... that we discussed in / Chapter 6." is one sentence (Rust Book,
        # ch09-02).
        assert _chapter_number("Chapter 6.", prev_line="`Result` using a basic tool, the `match` expression that we discussed in") is None

    def test_title_sized_tail_after_an_unfinished_line_is_kept(self):
        # The plain-text fixture layout: heading lines separated by a body line
        # that is not a sentence.
        assert _chapter_number("Chapter 2. Understanding Models", prev_line="body") == 2

    def test_long_tail_on_a_marked_heading_is_trusted(self):
        assert (
            _chapter_number(
                "## Chapter 4. References are indicated by the `&` symbol and borrow the value they"
            )
            == 4
        )

    def test_long_tail_on_a_standalone_line_is_kept(self):
        # Conservative on purpose: without the enclosing paragraph there is no
        # evidence that a sentence wrapped, so the line keeps its heading — the
        # shape a PDF extractor produces once it has lost the wrap.
        assert (
            _chapter_number(
                "Chapter 13. Closures and iterators create types that only the compiler knows or"
            )
            == 13
        )

    def test_heading_after_a_finished_sentence_is_kept(self):
        assert _chapter_number("Chapter 6. Enums", prev_line="Section one ends here.") == 6

    def test_colon_tail_after_prose_is_kept(self):
        # A colon introduces a title, not a sentence: "see Chapter 6: Enums".
        assert _chapter_number("Chapter 6: Enums", prev_line=WRAP_PREV) == 6

    def test_heading_controls_are_retained(self):
        kept = (
            "Chapter 6",
            "# Chapter 6",
            "## Chapter 6: Enums",
            "Chapter 1. Intro",
            "Capítulo 5",
            "Unit 1 — How to Write an Introduction",
            "## i. introduction",
        )
        for line in kept:
            assert _chapter_number(line) is not None, line


class TestCodeLinesAreNotChapters:
    def test_bare_diff_lines_are_not_chapters(self):
        assert _chapter_number("1  + use crate::trpl::StreamExt;") is None
        assert _chapter_number("12  - use std::io::prelude::*;") is None

    def test_plain_numbered_heading_is_kept(self):
        assert _chapter_number("1  Introduction") == 1

    def test_fenced_diff_does_not_count(self):
        text = (
            "## Real One\n" + CHAPTER_BODY + "\n\n"
            + FENCED_DIFF + "\n"
            + "## Real Two\n" + CHAPTER_BODY + "\n"
        )

        result = detect_structure(text)

        assert result["chapters_method"] == "structural"
        assert result["chapters_detected"] == 2
        assert result["chapter_headings_sample"] == []

    def test_prose_and_code_do_not_steal_the_numeric_branch(self):
        text = (
            WRAP_PREV + "\n" + WRAP_LINE + "\npoint at.\n\n"
            + FENCED_DIFF + "\n"
            + "## Real One\n" + CHAPTER_BODY + "\n\n"
            + "## Real Two\n" + CHAPTER_BODY + "\n\n"
            + "## Real Three\n" + CHAPTER_BODY + "\n"
        )

        result = detect_structure(text)

        assert result["chapters_method"] == "structural"
        assert result["chapters_detected"] == 3
        assert result["chapter_headings_sample"] == []


class TestRealNumericBooksAreUnaffected:
    def test_chapter_headings_still_count(self):
        text = "\n\n".join(
            f"Chapter {n}: Title {n}\n{CHAPTER_BODY}" for n in (1, 2, 3)
        )

        result = detect_structure(text)

        assert result["chapters_method"] == "numeric"
        assert result["chapters_detected"] == 3
        assert result["chapter_headings_sample"] == [
            "Chapter 1: Title 1",
            "Chapter 2: Title 2",
            "Chapter 3: Title 3",
        ]
