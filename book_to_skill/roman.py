"""Roman numeral parsing, shared by chapter detection and PDF page-number cleanup.

Lives in its own module because ``utils`` imports ``parsers.pdf``, so the PDF
cleanup cannot import back from ``utils`` without a cycle — and duplicating the
parser is what lets two call sites drift apart.

The canonical round-trip is the point of this module. Testing "is this string
made of the letters IVXLCDM" is not the same question as "is this a Roman
numeral": ordinary English words are made of those letters too.
"""

from __future__ import annotations


ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Chapter and front-matter page numbering does not realistically exceed this, and
# the bound keeps four-letter words that happen to parse (e.g. "MIX" -> 1009)
# from being accepted.
DEFAULT_MAXIMUM = 200


def int_to_roman(n: int) -> str:
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
             (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for val, sym in table:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def roman_to_int(s: str, maximum: int = DEFAULT_MAXIMUM) -> int | None:
    """Convert a Roman numeral to int, returning None if it isn't canonical.

    Rejects non-canonical forms ("IIII", "VV") and anything above ``maximum`` by
    round-tripping through :func:`int_to_roman`.
    """
    s = s.upper()
    total = prev = 0
    for ch in reversed(s):
        v = ROMAN_VALUES.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    if total == 0 or total > maximum:
        return None
    return total if int_to_roman(total) == s else None
