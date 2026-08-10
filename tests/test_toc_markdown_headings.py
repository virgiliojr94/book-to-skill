"""ToC detection must survive Markdown/AsciiDoc heading markup.

Kept in its own file so it does not collide with upstream edits to
test_book_to_skill.py on a future pull.

Before this fix, _TOC_PATTERN was ^\\s*(table of contents|contents|...)\\s*$,
which requires the header alone on its line. Every Markdown document writes it
as "## Table of Contents", so has_toc was False for the entire Markdown corpus
and detect_structure emitted a spurious "chapter mapping may miss or duplicate
sections" warning. This is the same blind spot #91/#92 fixed for chapter
headings; the sibling ToC pattern was left behind.
"""
import pytest

from book_to_skill.utils import _TOC_PATTERN, detect_structure


@pytest.mark.parametrize("line", [
    "Table of Contents",            # bare (the only form that worked before)
    "  Contents",                   # indented
    "# Contents",                   # ATX level 1
    "## Table of Contents",         # ATX level 2 — the common Markdown form
    "###### Contents",              # ATX level 6
    "== Table of Contents",         # AsciiDoc
    "**Contents**",                 # bold
    "__Table of Contents__",        # bold, underscore form
    "*Contents*",                   # italic
    "## **Table of Contents**",     # heading + bold
    "Contents:",                    # trailing colon
    "## Table of Contents  ",       # trailing whitespace
    "## SUMÁRIO",                   # non-English, uppercase
    "## 目录",                       # CJK
    "目次：",                        # CJK with fullwidth colon
    "## Inhaltsverzeichnis",
    "## Table des matières",
])
def test_toc_header_forms_are_detected(line):
    assert _TOC_PATTERN.search(line), f"should match: {line!r}"


@pytest.mark.parametrize("line", [
    "the contents of this chapter are",   # inline prose
    "Contents of the box",                # line does not end at the header
    "Table of Contents for Part II",      # qualified, not a bare header
    "No table of contents was provided",
    "discontents",                        # substring, not a header
])
def test_prose_mentions_are_not_detected(line):
    assert not _TOC_PATTERN.search(line), f"should NOT match: {line!r}"


def test_markdown_document_reports_has_toc():
    """End-to-end: the regression this fix targets."""
    doc = (
        "# The Decision Ledger\n\n"
        "## Table of Contents\n\n"
        "- Chapter 1 - The Reversibility Gate\n"
        "- Chapter 2 - The Cost-of-Delay Triangle\n\n"
        "## Chapter 1 - The Reversibility Gate\n\nBody text.\n\n"
        "## Chapter 2 - The Cost-of-Delay Triangle\n\nMore body text.\n"
    )
    result = detect_structure(doc)
    assert result["has_toc"] is True
    assert result["chapters_detected"] == 2


def test_document_without_toc_still_reports_false():
    doc = (
        "# Some Book\n\n"
        "## Chapter 1 - Opening\n\nBody text mentioning the contents of the room.\n"
    )
    assert detect_structure(doc)["has_toc"] is False
