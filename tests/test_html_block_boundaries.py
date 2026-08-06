"""The stdlib HTML parser must emit a text boundary when a block element closes.

`_HTMLTextExtractor` is the dependency-free fallback for HTML files *and* for
EPUB extraction when BeautifulSoup is not installed. It only emitted "\\n" on a
block element's *opening* tag, and its tag list omitted table and definition-list
elements, so text from adjacent blocks concatenated:

    <h2>Chapter 1</h2>Introduction   ->   "Chapter 1Introduction"

That silently destroys chapter detection. `_EXPLICIT_CHAPTER` requires a word
boundary after the chapter number, and there is none between "1" and "I", so the
heading is not counted and the book reports 0 chapters while extraction still
"succeeds".
"""

import sys
import zipfile
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.epub import extract_with_zipfile
from book_to_skill.parsers.html import _HTMLTextExtractor
from book_to_skill.utils import detect_structure


def _text(fragment: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(fragment)
    return parser.get_text()


def _chapters(fragment: str) -> int:
    return detect_structure(_text(fragment))["chapters_detected"]


class TestBlockBoundaryChapterDetection:
    """Four layouts that occur in real converted ebooks, all previously 0."""

    TABLE_TOC = (
        "<html><body><h1>Contents</h1><table>"
        "<tr><td>Chapter 1</td><td>Reliable Applications</td><td>1</td></tr>"
        "<tr><td>Chapter 2</td><td>Data Models</td><td>27</td></tr>"
        "<tr><td>Chapter 3</td><td>Storage and Retrieval</td><td>69</td></tr>"
        "</table></body></html>"
    )
    HEADING_THEN_SECTION = (
        "<html><body>"
        "<h2>Chapter 1</h2><section>Reliable Applications.</section>"
        "<h2>Chapter 2</h2><section>Data Models.</section>"
        "<h2>Chapter 3</h2><section>Storage and Retrieval.</section>"
        "</body></html>"
    )
    HEADING_THEN_BARE_TEXT = (
        "<html><body>"
        "<h2>Chapter 1</h2>Reliable Applications."
        "<h2>Chapter 2</h2>Data Models."
        "<h2>Chapter 3</h2>Storage and Retrieval."
        "</body></html>"
    )
    DEFINITION_LIST_TOC = (
        "<html><body><dl>"
        "<dt>Chapter 1</dt><dd>Reliable Applications</dd>"
        "<dt>Chapter 2</dt><dd>Data Models</dd>"
        "<dt>Chapter 3</dt><dd>Storage and Retrieval</dd>"
        "</dl></body></html>"
    )

    @pytest.mark.parametrize(
        "layout",
        ["TABLE_TOC", "HEADING_THEN_SECTION", "HEADING_THEN_BARE_TEXT",
         "DEFINITION_LIST_TOC"],
    )
    def test_three_chapters_detected(self, layout):
        assert _chapters(getattr(self, layout)) == 3

    def test_table_row_stays_on_one_line(self):
        """Cells are tab-joined, matching the stdlib DOCX fallback's rows."""
        lines = [ln for ln in _text(self.TABLE_TOC).splitlines() if ln.strip()]
        assert lines[1] == "Chapter 1\tReliable Applications\t1"

    def test_heading_text_not_glued_to_body_text(self):
        assert "Chapter 1Reliable" not in _text(self.HEADING_THEN_BARE_TEXT)
        assert "Chapter 1" in _text(self.HEADING_THEN_BARE_TEXT).splitlines()


class TestInlineTextUnchanged:
    """Inline elements must NOT gain boundaries — that would break words."""

    def test_inline_whitespace_preserved(self):
        assert _text("<p><b>bold</b> <i>italic</i> tail</p>") == "bold italic tail"

    def test_inline_elements_do_not_split_a_word(self):
        # "hyper" + "text" is one word split by markup; a boundary here would
        # turn it into two.
        assert _text("<p>hyper<span>text</span></p>") == "hypertext"

    def test_anchor_inside_sentence_stays_inline(self):
        assert _text('<p>see <a href="#x">chapter 4</a> for more</p>') == (
            "see chapter 4 for more"
        )


class TestSeparatorHygiene:
    """Deferred boundaries: no leading blank line, no runs of blank lines."""

    def test_no_leading_separator(self):
        assert _text("<p>First paragraph.</p>") == "First paragraph."

    def test_nested_blocks_collapse_to_one_separator(self):
        assert _text("<div><div><p>a</p></div></div><p>b</p>") == "a\nb"

    def test_layout_whitespace_between_blocks_dropped(self):
        assert _text("<p>a</p>\n    \n  <p>b</p>") == "a\nb"

    def test_br_still_breaks(self):
        assert _text("<p>line one<br/>line two</p>") == "line one\nline two"

    def test_skip_tag_content_still_excluded(self):
        assert _text("<style>x{}</style>keep") == "keep"
        assert _text("<p>a</p><script>var i=1;</script><p>b</p>") == "a\nb"


class TestConvergenceWithBeautifulSoup:
    """The fallback should agree with the bs4 path on chapter count."""

    def test_same_chapter_count_as_bs4(self):
        bs4 = pytest.importorskip("bs4")
        soup = bs4.BeautifulSoup(
            TestBlockBoundaryChapterDetection.TABLE_TOC, "html.parser"
        )
        bs4_count = detect_structure(soup.get_text(separator="\n"))[
            "chapters_detected"
        ]
        stdlib_count = _chapters(TestBlockBoundaryChapterDetection.TABLE_TOC)
        assert stdlib_count == bs4_count == 3


class TestEpubStdlibPath:
    """The same fix reaches EPUB, which shares this parser."""

    def _make_epub(self, path: Path) -> Path:
        container = (
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>'
        )
        opf = (
            '<?xml version="1.0"?><package version="3.0" '
            'xmlns="http://www.idpf.org/2007/opf"><manifest>'
            '<item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
            "</manifest><spine><itemref idref=\"c1\"/></spine></package>"
        )
        # A heading immediately followed by a <section>, as many EPUB
        # converters emit.
        chapter = (
            "<html><body>"
            "<h2>Chapter 1</h2><section>Reliable Applications.</section>"
            "<h2>Chapter 2</h2><section>Data Models.</section>"
            "</body></html>"
        )
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr("META-INF/container.xml", container)
            zf.writestr("content.opf", opf)
            zf.writestr("c1.xhtml", chapter)
        return path

    def test_epub_chapters_detected_without_ebooklib(self, tmp_path):
        epub = self._make_epub(tmp_path / "book.epub")
        text = extract_with_zipfile(str(epub))

        assert text is not None
        assert "Chapter 1Reliable" not in text
        assert detect_structure(text)["chapters_detected"] == 2
