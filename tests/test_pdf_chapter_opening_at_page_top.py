"""A chapter opening must survive running-header removal.

`clean_pdftotext` treats the first/last non-blank line of each page as a
boilerplate candidate and drops every edge occurrence of any string repeated on
more than half the pages. #161's fix confined that to page edges so a *mid-page*
heading identical to the running header survives.

But a chapter opening is not mid-page: books start a chapter at the top of a
page, which is exactly where the running header sits. When a chapter runs long
enough for its title to cross the "more than half the pages" threshold — a
single long chapter in a short extract is enough — the genuine opening is
deleted along with the headers, and the chapter disappears from
`detect_structure` entirely. Nothing is logged.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.pdf import clean_pdftotext  # noqa: E402
from book_to_skill.utils import detect_structure  # noqa: E402


class TestChapterOpeningAtPageTop:
    # Chapter 1 spans four pages with its title as the running header, so the
    # title is the first line of 4 of 5 pages and crosses the threshold.
    LONG_CHAPTER = "\f".join(
        [f"CHAPTER 1\nProse page {i} of chapter one.\n{i}" for i in range(1, 5)]
        + ["CHAPTER 2\nProse of chapter two.\n5"]
    )

    def test_chapter_opening_is_not_deleted(self):
        out = clean_pdftotext(self.LONG_CHAPTER)

        assert "CHAPTER 1" in out

    def test_both_chapters_are_still_detected(self):
        out = clean_pdftotext(self.LONG_CHAPTER)

        assert detect_structure(out)["chapters_detected"] == 2

    def test_repeated_running_headers_are_still_removed(self):
        """Only the opening survives; the continuation-page copies go."""
        out = clean_pdftotext(self.LONG_CHAPTER)

        assert out.count("CHAPTER 1") == 1

    def test_body_text_and_page_numbers_unaffected(self):
        out = clean_pdftotext(self.LONG_CHAPTER)

        assert "Prose page 3 of chapter one." in out
        assert "\n3\n" not in out

    def test_non_heading_running_header_is_still_fully_removed(self):
        """A running header that is not a chapter heading keeps its old handling."""
        raw = "\f".join([
            "Reliability\nOpening discussion.\n42",
            "Reliability\nMore body text.\n43",
            "Reliability\nStill more body text.\n44",
        ])
        out = clean_pdftotext(raw)

        assert "Reliability" not in out
