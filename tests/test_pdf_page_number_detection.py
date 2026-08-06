"""Regression tests: edge-of-page cleanup must not delete real one-word lines.

`clean_pdftotext` drops a bare page number when it is a page's first or last
non-blank line. The Roman branch of that pattern used to be `[ivxlcdm]{1,7}`
with `re.IGNORECASE`, which matches any short word built from those letters, so
"MIX", "CIVIL", "DIM", "MILD" and "VIVID" were deleted without a trace whenever
they were the only word on such a line — the shape of a part title or a display
heading.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.pdf import _PDF_PAGE_NUM, clean_pdftotext  # noqa: E402


# Words made only of Roman-numeral letters that are not canonical numerals.
NOT_NUMERALS = ["MIX", "CIVIL", "DIM", "MILD", "VIVID", "LIVID", "DID", "ILL"]

# Numerals that really are used to paginate front matter. Every canonical value
# in 1-99 must still be stripped — the fix must not trade false positives for
# false negatives.
REAL_NUMERALS = [
    "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
    "xi", "xiv", "xix", "xx", "xxxix", "xl", "xlii", "xlix",
    "l", "li", "lxxxviii", "xc", "xcix",
]


@pytest.mark.parametrize("word", NOT_NUMERALS)
def test_roman_letter_words_are_not_page_numbers(word):
    assert _PDF_PAGE_NUM.match(word) is None
    assert _PDF_PAGE_NUM.match(word.lower()) is None


@pytest.mark.parametrize("numeral", REAL_NUMERALS)
def test_real_roman_numerals_still_match(numeral):
    assert _PDF_PAGE_NUM.match(numeral) is not None
    assert _PDF_PAGE_NUM.match(numeral.upper()) is not None


@pytest.mark.parametrize("digits", ["1", "42", "999", "1234"])
def test_arabic_page_numbers_still_match(digits):
    assert _PDF_PAGE_NUM.match(digits) is not None


def test_every_canonical_numeral_1_to_99_matches():
    """Exhaustive: no value in the supported range regressed into a miss."""
    ones = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix"]
    tens = ["", "x", "xx", "xxx", "xl", "l", "lx", "lxx", "lxxx", "xc"]
    for value in range(1, 100):
        numeral = tens[value // 10] + ones[value % 10]
        assert _PDF_PAGE_NUM.match(numeral) is not None, f"{value} -> {numeral}"


def test_letters_outside_the_1_to_99_range_are_kept():
    """"C"/"D"/"M" alone are not page numbers in the supported range."""
    for letter in ("c", "d", "m", "C", "D", "M"):
        assert _PDF_PAGE_NUM.match(letter) is None


def test_blank_line_is_not_a_page_number():
    """The pattern must not match emptily now that a branch is optional."""
    assert _PDF_PAGE_NUM.match("") is None
    assert _PDF_PAGE_NUM.match("   ") is None


def test_non_numeral_words_still_rejected():
    for word in ("Chapter", "Introduction", "the", "42a"):
        assert _PDF_PAGE_NUM.match(word) is None


def _pages(*pages):
    return "\f".join(pages)


def test_part_title_at_page_edge_survives():
    """End to end: a one-word display line is no longer eaten by the cleaner."""
    raw = _pages(
        "MIX\nReal content on page 1.\n1",
        "CIVIL\nReal content on page 2.\n2",
        "VIVID\nReal content on page 3.\n3",
    )
    out = clean_pdftotext(raw)

    assert "MIX" in out
    assert "CIVIL" in out
    assert "VIVID" in out
    # The actual page numbers are still stripped.
    assert not any(line.strip() in {"1", "2", "3"} for line in out.splitlines())


def test_front_matter_roman_numbers_still_stripped():
    raw = _pages(*(f"Preface text on page {n}.\n{n}" for n in ("ii", "iii", "iv")))
    out = clean_pdftotext(raw)

    assert not any(line.strip() in {"ii", "iii", "iv"} for line in out.splitlines())
    assert "Preface text on page ii." in out
