r"""A setext title made only of punctuation is not a chapter heading.

`_structural_chapter_count` has two heading branches. The ATX branch rejects a
title with no word character — that is what keeps a `=====` table border or a
`***` thematic break from being counted:

    if title and re.search(r"\w", title):

The setext branch had no equivalent. So the *identical string* was rejected as
`## ***` and accepted as `***` sitting above a row of `-`. Two thematic breaks
in a row, an ASCII box rule, a row of dots, or a punctuation table border above
an underline all minted a phantom heading.

The function's own docstring claims "thematic breaks, table borders, and
front-matter `---` do not match", which was only true while the underline was
shorter than the line above it.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import _structural_chapter_count

# Two real sections in every fixture below, so any count above 2 is a phantom.
# `___` is deliberately NOT here: "_" is a word character to `\w`, so it is kept
# by both branches. See TestSharedUnderscoreGap.
PUNCTUATION_TITLES = ["***", "+-----+", ".......", "|||||", "* * *", "###", "-- --"]


def _with_setext(title: str) -> str:
    """A book whose middle holds `title` underlined by an equally long rule."""
    return (
        "# Book\n\n## Alpha\na\n\n"
        f"{title}\n{'-' * max(3, len(title))}\n\n"
        "## Beta\nb\n"
    )


def _with_atx(title: str) -> str:
    return f"# Book\n\n## Alpha\na\n\n## {title}\n\n## Beta\nb\n"


class TestPunctuationOnlySetextTitleRejected:
    @pytest.mark.parametrize("title", PUNCTUATION_TITLES)
    def test_no_phantom_heading(self, title):
        assert _structural_chapter_count(_with_setext(title)) == 2

    @pytest.mark.parametrize("title", PUNCTUATION_TITLES)
    def test_matches_the_atx_branch(self, title):
        """The same string must be judged the same way by both branches."""
        assert _structural_chapter_count(_with_setext(title)) == (
            _structural_chapter_count(_with_atx(title))
        )

    def test_two_thematic_breaks_in_a_row(self):
        """`***` then `---` are both valid thematic breaks, not a heading."""
        text = "# Book\n\n## Alpha\na\n\n***\n---\n\n## Beta\nb\n"

        assert _structural_chapter_count(text) == 2

    def test_underline_longer_than_the_punctuation_run(self):
        """The length guard does not help when the rule is the longer line."""
        text = "# Book\n\n## Alpha\na\n\n***\n" + "-" * 40 + "\n\n## Beta\nb\n"

        assert _structural_chapter_count(text) == 2


class TestRealSetextHeadingsStillCounted:
    """The branch must keep doing its job."""

    def test_word_titles_still_counted(self):
        text = "Alpha\n=====\n\ntext\n\nBeta\n====\n\ntext\n"

        assert _structural_chapter_count(text) == 2

    def test_mixed_punctuation_and_words_is_kept(self):
        """A word character anywhere is enough — titles carry punctuation."""
        text = (
            "Chapter One -- Beginnings\n-------------------------\n\ntext\n\n"
            "Chapter Two -- Endings\n----------------------\n\ntext\n"
        )

        assert _structural_chapter_count(text) == 2

    def test_title_with_digits_and_punctuation(self):
        text = "1.2 Scope\n---------\n\ntext\n\n1.3 Limits\n----------\n\ntext\n"

        assert _structural_chapter_count(text) == 2

    def test_cjk_setext_title_counted(self):
        r"""`\w` is Unicode-aware, so a CJK title is not punctuation."""
        text = "\u7b2c\u4e00\u7ae0\n====\n\ntext\n\n\u7b2c\u4e8c\u7ae0\n====\n\ntext\n"

        assert _structural_chapter_count(text) == 2

    def test_snake_case_title_kept(self):
        assert _structural_chapter_count(_with_setext("snake_case_title")) == 3


class TestSharedUnderscoreGap:
    """`___` is a thematic break but `_` is a word character, so both branches
    still count it. Pre-existing and identical on either side — pinned here so
    the parity this PR establishes is visible, and so closing the gap later is a
    deliberate change to BOTH branches rather than a silent divergence.
    """

    def test_underscore_rule_still_counted_by_both_branches(self):
        setext = _structural_chapter_count(_with_setext("___"))
        atx = _structural_chapter_count(_with_atx("___"))

        assert setext == atx == 3


class TestUnaffectedBehaviour:
    def test_document_with_no_headings(self):
        assert _structural_chapter_count("just prose\nmore prose\n") == 0

    def test_setext_still_needs_a_long_enough_underline(self):
        text = "# Book\n\n## Alpha\na\n\nA long paragraph line here.\n---\n\n## Beta\nb\n"

        assert _structural_chapter_count(text) == 2

    def test_blank_line_above_underline_is_not_a_heading(self):
        text = "# Book\n\n## Alpha\na\n\n\n-------\n\n## Beta\nb\n"

        assert _structural_chapter_count(text) == 2
