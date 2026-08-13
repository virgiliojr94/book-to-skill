"""Numbered headings are chapters when the numbering is systematic AND the
sections carry a chapter's worth of text.

`## 1. Introduction` (a paper's section) and `## 5 Setup` (a tutorial step) are
the same string shape, so the heading line alone cannot decide. The old guard
rejected every digit-led title, which dropped the entire structure of numbered
documents — the format `--mode technical` exists to serve.

The discriminator deliberately ignores the numbers themselves: an ascending run
starting at 1 describes "Step 1 / Step 2 / Step 3" exactly as well as it
describes a paper, and requiring an unbroken run would discard a book whose
extraction lost one heading, a chapter list starting at 0, or a multi-source
corpus where numbering restarts.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import _structural_chapter_count

CHAPTER_BODY = "prose carrying the section's actual content. " * 40   # ~1.8k chars
STEP_BODY = "run the command below."                                  # ~22 chars


def document(headings, body):
    return "# The Document\n\n" + "\n\n".join(f"{h}\n{body}" for h in headings)


class TestNumberedSectionsAreCounted:
    """Every arabic form, not just the one with a dot."""

    def test_dot(self):
        doc = document(["## 1. Intro", "## 2. Method", "## 3. Results"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3

    def test_bare_space(self):
        doc = document(["## 1 Intro", "## 2 Method", "## 3 Results"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3

    def test_parenthesis(self):
        doc = document(["## 1) Intro", "## 2) Method", "## 3) Results"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3

    def test_decimal(self):
        doc = document(["## 1.1 Intro", "## 1.2 Method", "## 1.3 Results"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3


class TestNumberingIrregularitiesSurvive:
    """The count must not depend on the sequence being clean."""

    def test_numbering_starting_at_zero(self):
        """"Chapter 0: Prologue" is common; so is zero-indexing in CS books."""
        doc = document(["## 0. Prologue", "## 1. One", "## 2. Two"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3

    def test_gap_from_a_heading_lost_in_extraction(self):
        """A dropped heading must cost one chapter, not the whole document."""
        doc = document(
            ["## 1. One", "## 2. Two", "## 5. Five", "## 6. Six"], CHAPTER_BODY
        )
        assert _structural_chapter_count(doc) == 4

    def test_numbering_restarting_mid_corpus(self):
        """full_text.txt concatenates sources; numbering restarts at 1."""
        doc = document(
            ["## 1. A One", "## 2. A Two", "## 1. B One", "## 2. B Two"], CHAPTER_BODY
        )
        assert _structural_chapter_count(doc) == 4


class TestTutorialStepsStillRejected:
    """The guard this replaces existed for a reason. It must keep working."""

    def test_three_numbered_steps_are_not_chapters(self):
        """Systematic and ascending from 1 — and still a tutorial.

        This is the case that makes sequence-based detection useless: the shape
        of the numbering is identical to a paper's. Only the weight differs.
        """
        doc = document(["## 1 Install", "## 2 Configure", "## 3 Run"], STEP_BODY)
        assert _structural_chapter_count(doc) == 1   # only "# The Document"

    def test_isolated_numbered_heading(self):
        doc = document(["## 5 Setup"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 1

    def test_two_numbered_headings_are_not_a_scheme(self):
        """Below the floor of three, numbering is incidental."""
        doc = document(["## 1 Install", "## 2 Configure"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 1


class TestExistingBehaviourPreserved:
    def test_unnumbered_headings_unchanged(self):
        doc = document(["## Intro", "## Method", "## Results"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3

    def test_roman_numerals_unchanged(self):
        doc = document(["## I. Intro", "## II. Method", "## III. Results"], CHAPTER_BODY)
        assert _structural_chapter_count(doc) == 3

    def test_headings_inside_a_closed_fence_still_ignored(self):
        doc = (
            "# The Document\n\n## Alpha\ntext\n\n"
            "```\n## 1. Not a section\n## 2. Also not\n## 3. Nor this\n```\n\n"
            "## Beta\ntext\n"
        )
        assert _structural_chapter_count(doc) == 2

    def test_document_with_no_headings(self):
        assert _structural_chapter_count("just prose\nmore prose\n") == 0
