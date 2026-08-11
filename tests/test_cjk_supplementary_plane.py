"""`estimate_tokens` must count supplementary-plane CJK, not just the BMP.

#103 made the estimate CJK-aware because ideographs are not whitespace-delimited:
without it a space-less Chinese or Japanese book collapses to a handful of
"words" and the cost pre-flight under-reports by ~1000x.

`_CJK_RE` only covered the Basic Multilingual Plane, so Unified Ideographs
Extension B and later (U+20000 and up) fell straight through to the
whitespace-word branch and hit exactly the undercount #103 set out to fix — one
plane up. Those extensions carry classical Chinese, Cantonese, Hong Kong and
Taiwan place and personal names, and Japanese 人名用漢字.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.config import CJK_CHARS_PER_TOKEN
from book_to_skill.utils import estimate_tokens

BMP = "一二三四五六七八九十"                                    # common ideographs
SIP = "\U00020000\U00020001\U0002a700\U0002b740\U0002ceb0"   # Ext B / C / D / E


class TestSupplementaryPlaneCounted:
    def test_sip_matches_bmp_for_the_same_length(self):
        bmp_text = BMP * 200
        sip_text = SIP * 400  # same character count

        assert len(bmp_text) == len(sip_text)
        assert estimate_tokens(sip_text) == estimate_tokens(bmp_text)

    def test_sip_only_text_is_not_one_token(self):
        text = SIP * 400

        # The old behaviour: a space-less run counts as a single "word".
        assert estimate_tokens(text) > 1000

    def test_estimate_tracks_the_configured_ratio(self):
        text = SIP * 400

        assert estimate_tokens(text) == pytest.approx(
            len(text) / CJK_CHARS_PER_TOKEN, rel=0.01
        )

    def test_mixed_plane_text_is_consistent(self):
        """A book mixing common and rare ideographs estimates evenly."""
        mixed = (BMP * 180) + (SIP * 40)
        all_bmp = BMP * 200

        assert len(mixed) == len(all_bmp)
        assert estimate_tokens(mixed) == estimate_tokens(all_bmp)

    @pytest.mark.parametrize(
        "codepoint, name",
        [
            (0x20000, "Ext B start"),
            (0x2A6DF, "Ext B end"),
            (0x2A700, "Ext C start"),
            (0x2B740, "Ext D start"),
            (0x2CEB0, "Ext E start"),
            (0x2EBF0, "Ext I start"),
            (0x30000, "Ext G start"),
            (0x3134E, "Ext G end"),
            # Extension H sits ABOVE Extension G, so a range that stopped at the
            # end of G let 4,192 assigned ideographs fall through. Both ends are
            # probed so the plane boundary cannot regress to a block boundary.
            (0x31350, "Ext H start"),
            (0x323AF, "Ext H end"),
        ],
    )
    def test_extension_ranges_are_covered(self, codepoint, name):
        text = chr(codepoint) * 300

        assert estimate_tokens(text) > 100, name


class TestExistingBehaviourPreserved:
    """The #103 behaviour for the BMP and for Latin must not change."""

    def test_bmp_cjk_unchanged(self):
        text = BMP * 200

        assert estimate_tokens(text) == pytest.approx(
            len(text) / CJK_CHARS_PER_TOKEN, rel=0.01
        )

    @pytest.mark.parametrize(
        "sample",
        ["第一章 緒論", "제1장 총칙", "こんにちは世界", "你好世界"],
    )
    def test_short_cjk_samples_still_counted(self, sample):
        assert estimate_tokens(sample) >= 1

    def test_latin_text_unaffected(self):
        text = "the quick brown fox jumps over the lazy dog " * 100

        # Pure Latin takes the word branch; no CJK found.
        assert estimate_tokens(text) == int(len(text.split()) / 0.75)

    def test_empty_text(self):
        assert estimate_tokens("") == 0

    def test_latin_with_a_single_sip_character(self):
        """One rare ideograph must not flip Latin onto a wrong scale."""
        text = ("word " * 100) + "\U00020000"

        # 100 Latin words plus one CJK char: dominated by the Latin branch.
        assert 120 < estimate_tokens(text) < 145


class TestNonCjkSupplementaryPlanesExcluded:
    """Emoji and other astral characters are not ideographs."""

    @pytest.mark.parametrize(
        "char, name",
        [
            ("\U0001F600", "emoji"),
            ("\U0001D400", "math bold capital A"),
            ("\U0001F1E6", "regional indicator"),
        ],
    )
    def test_astral_non_cjk_takes_the_word_branch(self, char, name):
        # A space-less run of these is one "word", as before — they are not
        # CJK and must not be pulled into the ideograph branch.
        assert estimate_tokens(char * 300) == 1, name
