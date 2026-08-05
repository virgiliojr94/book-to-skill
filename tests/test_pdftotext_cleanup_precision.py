"""`clean_pdftotext` must not delete real content while stripping boilerplate.

Three precision problems in the page-edge cleanup:

1. The page-number test was ``[ivxlcdm]{1,7}`` — a character class, not a Roman
   numeral. Ordinary English words are built from those same letters, so
   "civil", "dim", "did", "lid", "vim" and "mild" all matched and were deleted
   whenever they stood alone on a page's first or last line.
2. Boilerplate lines were removed from *every* line of the page, though they are
   only ever *detected* at the page edges. A running header that repeats the
   section title therefore also deleted that title where it legitimately
   appeared in the body.
3. A page with a single non-blank line counted that line twice toward the
   "repeated on more than half the pages" threshold, because it is both the
   first and the last line.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.pdf import _is_page_number, clean_pdftotext
from book_to_skill.roman import roman_to_int


class TestPageNumberRecognition:
    # Real words made only of the letters I, V, X, L, C, D, M.
    WORD_FALSE_POSITIVES = ["civil", "dim", "did", "lid", "vim", "mild", "mix",
                            "MIX", "CIVIL", "livid", "vivid"]

    @pytest.mark.parametrize("word", WORD_FALSE_POSITIVES)
    def test_ordinary_word_is_not_a_page_number(self, word):
        assert not _is_page_number(word)

    @pytest.mark.parametrize("numeral", ["i", "ii", "iv", "ix", "xl", "II", "XIV",
                                         "xxviii"])
    def test_canonical_roman_is_a_page_number(self, numeral):
        assert _is_page_number(numeral)

    @pytest.mark.parametrize("numeral", ["1", "7", "42", "1999", "  12  "])
    def test_arabic_is_a_page_number(self, numeral):
        assert _is_page_number(numeral)

    @pytest.mark.parametrize("bad", ["iiii", "vv", "xxxx", "ic"])
    def test_non_canonical_roman_rejected(self, bad):
        assert not _is_page_number(bad)

    @pytest.mark.parametrize("text", ["12345", "page 4", "4.", "Chapter 1", ""])
    def test_non_page_numbers_rejected(self, text):
        assert not _is_page_number(text)


class TestWordsAtPageEdgesSurvive:
    def _pages(self, *pages):
        return "\f".join(pages)

    def test_word_only_edge_line_is_kept(self):
        raw = self._pages(
            "Chapter 1\nThe opening discussion.\ncivil",
            "Second page body text.\nmix",
            "Third page body text.\nvivid",
        )
        out = clean_pdftotext(raw)
        for word in ("civil", "mix", "vivid"):
            assert word in out, word

    def test_real_page_numbers_still_stripped(self):
        raw = self._pages(
            "Body text one.\n11",
            "Body text two.\n12",
            "Body text three.\n13",
        )
        out = clean_pdftotext(raw)
        assert "11" not in out and "12" not in out and "13" not in out
        assert "Body text one." in out

    def test_roman_front_matter_page_numbers_still_stripped(self):
        raw = self._pages(
            "Preface text one.\niv",
            "Preface text two.\nv",
            "Preface text three.\nvi",
        )
        out = clean_pdftotext(raw)
        assert "Preface text one." in out
        assert [ln for ln in out.splitlines() if ln.strip() in ("iv", "v", "vi")] == []


class TestBoilerplateRemovalIsEdgeOnly:
    def test_mid_page_heading_survives_matching_running_header(self):
        """The header repeats the section title; the real heading must survive."""
        raw = "\f".join([
            "Reliability\nOpening discussion of the topic.\n42",
            "Reliability\nMore body text on page two.\n43",
            "Reliability\nStill more body text on page three.\n44",
            "Reliability\nEnd of the previous section.\n"
            "Reliability\n"                      # genuine mid-page heading
            "This section explains the term properly.\n45",
        ])
        out = clean_pdftotext(raw)

        # Four running headers dropped, the one real mid-page heading kept.
        assert out.count("Reliability") == 1
        assert "This section explains the term properly." in out
        # Page numbers still gone.
        assert not any(str(n) in out for n in (42, 43, 44, 45))

    def test_running_headers_still_removed(self):
        raw = "\f".join([
            "DESIGNING SYSTEMS\nBody one.",
            "DESIGNING SYSTEMS\nBody two.",
            "DESIGNING SYSTEMS\nBody three.",
        ])
        out = clean_pdftotext(raw)
        assert "DESIGNING SYSTEMS" not in out
        assert "Body one." in out


class TestSingleLinePageVoting:
    def test_single_line_page_does_not_vote_twice(self):
        """A lone line is both first and last; it must count once, not twice."""
        # 4 pages. "PART ONE" is the only line on 2 of them -> 2 votes, not 4.
        # Threshold is > 4/2 == 2, so it must NOT be treated as boilerplate.
        raw = "\f".join([
            "PART ONE",
            "Chapter 1\nBody text of the first chapter.",
            "PART ONE",
            "Chapter 2\nBody text of the second chapter.",
        ])
        out = clean_pdftotext(raw)
        assert "PART ONE" in out


class TestExistingBehaviourPreserved:
    """Regression net for the cleanup introduced in #77."""

    def test_hyphenated_wrap_still_rejoined(self):
        assert "information" in clean_pdftotext("informa-\ntion is here")

    def test_short_document_keeps_content_and_drops_form_feeds(self):
        out = clean_pdftotext("Page one text.\fPage two text.")
        assert "Page one text." in out
        assert "Page two text." in out
        assert "\f" not in out

    def test_mid_page_bare_number_is_kept(self):
        raw = "\f".join([
            "Intro line.\n7\nMore text after the number.\n1",
            "Second page.\n2",
            "Third page.\n3",
        ])
        out = clean_pdftotext(raw)
        assert "7" in out  # mid-page, not an edge


class TestSharedRomanParser:
    """pdf.py and utils.py must use one Roman parser, not two copies."""

    def test_utils_aliases_the_shared_parser(self):
        from book_to_skill import utils

        assert utils._roman_to_int is roman_to_int

    def test_canonical_round_trip(self):
        assert roman_to_int("XIV") == 14
        assert roman_to_int("IIII") is None      # non-canonical
        assert roman_to_int("MIX") is None       # 1009, above the bound
        assert roman_to_int("MIX", maximum=2000) == 1009
