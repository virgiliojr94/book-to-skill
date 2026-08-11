"""An unbalanced code fence must not swallow the rest of the document.

`_structural_chapter_count` skips headings inside fenced code blocks, which is
right — a `## comment` in a shell example is not a chapter. But it tracked the
fence by toggling a boolean on every ``` or ~~~ line, so a fence that never
closed put the scanner "inside a code block" for the remainder of the file and
every heading after it was dropped.

This is the structural fallback, which only runs for books with no "Chapter N"
headings — i.e. Markdown/AsciiDoc technical docs, exactly the sources most
likely to contain fenced blocks. Extraction can lose a closing fence, and a book
about Markdown can contain a stray one.

Toggling also ignored which fence character opened the block, so a "```" block
could be closed by an unrelated "~~~" line.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.utils import _closed_fence_line_numbers, _structural_chapter_count

SECTIONS = [
    "## Getting Started\nInstall the toolchain.\n",
    "## Configuration\nEdit the config file.\n",
    "## Writing Markdown\nA fenced block looks like this:\n",
    "## Deployment\nShip it.\n",
    "## Monitoring\nWatch the dashboards.\n",
    "## Scaling\nAdd replicas.\n",
    "## Security\nRotate credentials.\n",
    "## Troubleshooting\nRead the logs.\n",
]


def _book(third_section_tail: str) -> str:
    body = list(SECTIONS)
    body[2] = body[2] + third_section_tail
    return "# The Handbook\n\n" + "\n".join(body)


class TestUnbalancedFenceDoesNotSwallowHeadings:
    def test_unclosed_backtick_fence_keeps_later_sections(self):
        broken = _book("\n```\nnot closed\n")

        assert _structural_chapter_count(broken) == 8

    def test_matches_the_balanced_document(self):
        balanced = _book("\n```\nclosed\n```\n")
        broken = _book("\n```\nnot closed\n")

        assert _structural_chapter_count(broken) == _structural_chapter_count(balanced)

    def test_unclosed_tilde_fence_keeps_later_sections(self):
        text = "# Book\n\n## Alpha\na\n\n~~~\n\n## Beta\nb\n\n## Gamma\nc\n"

        assert _structural_chapter_count(text) == 3

    def test_trailing_lone_fence_marker(self):
        text = "# Book\n\n## Alpha\na\n\n## Beta\nb\n\n```\n"

        assert _structural_chapter_count(text) == 2


class TestBalancedFencesStillSuppressHeadings:
    """The original guard must keep working: real code blocks are skipped."""

    def test_heading_inside_a_closed_fence_is_not_counted(self):
        text = (
            "# Book\n\n## Alpha\na\n\n"
            "```sh\n# Not a heading\n## Also not a heading\n```\n\n"
            "## Beta\nb\n"
        )

        assert _structural_chapter_count(text) == 2

    def test_multiple_closed_fences(self):
        text = (
            "# Book\n\n## Alpha\n```\n## fake one\n```\n\n"
            "## Beta\n```\n## fake two\n```\n\n"
            "## Gamma\nreal\n"
        )

        assert _structural_chapter_count(text) == 3

    def test_setext_heading_inside_a_closed_fence_is_not_counted(self):
        text = (
            "# Book\n\n## Alpha\na\n\n"
            "```\nFake Title\n==========\n```\n\n"
            "## Beta\nb\n"
        )

        assert _structural_chapter_count(text) == 2

    def test_tilde_fence_suppresses_when_closed(self):
        text = "# Book\n\n## Alpha\na\n\n~~~\n## fake\n~~~\n\n## Beta\nb\n"

        assert _structural_chapter_count(text) == 2


class TestFenceCharacterMustMatch:
    """CommonMark: a fence is closed by the same character, not any fence."""

    def test_backtick_fence_not_closed_by_tilde(self):
        lines = ["```", "code", "~~~", "more code"]

        # No matching closer, so nothing is treated as fenced.
        assert _closed_fence_line_numbers(lines) == set()

    def test_matching_pair_is_detected(self):
        lines = ["before", "```", "code", "```", "after"]

        assert _closed_fence_line_numbers(lines) == {1, 2, 3}

    def test_longer_fence_markers(self):
        lines = ["````", "code with ``` inside", "````"]

        assert _closed_fence_line_numbers(lines) == {0, 1, 2}

    def test_no_fences_at_all(self):
        assert _closed_fence_line_numbers(["a", "b", "c"]) == set()

    def test_indented_fence_is_recognised(self):
        lines = ["  ```", "code", "  ```"]

        assert _closed_fence_line_numbers(lines) == {0, 1, 2}


class TestExistingBehaviourPreserved:
    def test_bare_digit_titles_still_rejected(self):
        text = "# Book\n\n## 5 Setup\na\n\n## 6 Teardown\nb\n\n## Real One\nc\n"

        # Both digit-led titles are rejected, leaving "# Book" at depth 1 and
        # "## Real One" at depth 2. No level reaches 2 distinct titles, so the
        # thin-document fallback sums them: 1 + 1.
        assert _structural_chapter_count(text) == 2

    def test_setext_headings_still_counted(self):
        text = "Alpha\n=====\n\ntext\n\nBeta\n====\n\ntext\n"

        assert _structural_chapter_count(text) == 2

    def test_document_with_no_headings(self):
        assert _structural_chapter_count("just prose\nmore prose\n") == 0
