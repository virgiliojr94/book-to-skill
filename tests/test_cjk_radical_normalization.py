"""Kangxi radicals must be folded to the ideographs they stand in for (#274).

A PDF whose embedded font subset has no correct Unicode mapping emits a radical
where a character belongs, so a Chinese book extracts "判断⼒" instead of
"判断力". Nothing looks wrong on the page and the run reports success, which is
what makes this worth fixing at the extraction chokepoint: every later grep,
chapter-heading match and topic index is built from the corrupted text.
"""

import sys
import unicodedata
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.sanitize import (
    _KANGXI_RADICAL_RANGE,
    fold_cjk_radicals,
    sanitize_extracted_text,
)

# The shapes that actually show up in Chinese extractions: 一 (U+2F00), 人
# (U+2F08), 自 (U+2F1B), 生 (U+2F25), 大 (U+2F27), 而 (U+2F3D).
CORRUPTED = "纳⽡尔宝典 第⼀章 判断⼒ ⾃由 ⽣ ⼤ ⽽ ⼒"
REPAIRED = "纳瓦尔宝典 第一章 判断力 自由 生 大 而 力"


class TestKangxiRadicalsFolded:
    def test_reported_chinese_passage_becomes_searchable(self):
        assert fold_cjk_radicals(CORRUPTED) == REPAIRED

    def test_fold_replaces_rather_than_removes(self):
        # A radical and its ideograph are both one character, so a fold cannot
        # change the length of the text — only what it says.
        folded = fold_cjk_radicals(CORRUPTED)

        assert len(folded) == len(CORRUPTED)

    def test_every_folded_radical_maps_to_one_ideograph(self):
        """No radical may expand to a sequence or to another radical."""
        for codepoint in range(_KANGXI_RADICAL_RANGE[0], _KANGXI_RADICAL_RANGE[1] + 1):
            radical = chr(codepoint)
            folded = fold_cjk_radicals(radical)
            if folded == radical:  # unassigned code point, nothing to fold
                continue
            assert len(folded) == 1, f"U+{codepoint:04X} folded to {folded!r}"
            assert _KANGXI_RADICAL_RANGE[0] > ord(folded) or ord(folded) > _KANGXI_RADICAL_RANGE[1], (
                f"U+{codepoint:04X} folded to another radical"
            )

    def test_agrees_with_unicode_compatibility_decomposition(self):
        """The table is NFKC, not a hand-written opinion."""
        assert fold_cjk_radicals("⼀") == unicodedata.normalize("NFKC", "⼀") == "一"


class TestNormalizationIsScoped:
    """NFKC must not be applied to the whole text — it rewrites legitimate prose."""

    @pytest.mark.parametrize(
        "text",
        [
            "ﬁle ﬁrst",  # ligatures
            "①②③",  # circled digits
            "㍿",  # squared katakana
            "中文",  # already-normal ideographs
            "ＡＢＣ １２３",  # full-width forms
            "Ⅳ",  # Roman numeral four
            "㊤",  # parenthesized ideograph
        ],
    )
    def test_prose_outside_the_block_is_byte_for_byte_preserved(self, text):
        assert fold_cjk_radicals(text) == text


class TestSanitizeExtractionPath:
    def test_sanitize_folds_radicals_without_counting_them_as_removed(self):
        sanitized, removed = sanitize_extracted_text(CORRUPTED)

        assert sanitized == REPAIRED
        # Radicals are a legibility fix, not a security strip, so they must not
        # inflate the "[security] removed N" count the CLI reports.
        assert removed == 0

    def test_invisible_stripping_still_works_alongside_the_fold(self):
        sanitized, removed = sanitize_extracted_text("第⼀章\u200b")

        assert sanitized == "第一章"
        assert removed == 1

    def test_radicals_are_not_reported_as_invisible(self):
        """is_invisible_codepoint drives the scanner; a radical must not drift in."""
        from book_to_skill.sanitize import is_invisible_codepoint

        assert is_invisible_codepoint(0x2F00) is False