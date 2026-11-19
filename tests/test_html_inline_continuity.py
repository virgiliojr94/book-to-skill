"""BeautifulSoup HTML and EPUB extraction must not split inline text nodes.

``soup.get_text(separator="\\n")`` inserts a newline between every text node,
including nodes separated only by inline markup. That splits a chapter number
or a syntax-highlighted token and still exits successfully. The stdlib
extractor is the control: it already keeps inline text continuous.
"""

import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.html import _HTMLTextExtractor, extract_html_content
from book_to_skill.utils import detect_structure

bs4 = pytest.importorskip("bs4")

STYLED_CHAPTERS = (
    "<html><body>"
    "<h2>Chapter <span>1</span>: Syntax</h2>"
    "<p>A hyper<span>text</span> term remains continuous.</p>"
    "<h2>Chapter <span>2</span>: Safety</h2>"
    "<p>Only retry when the failure is temporary.</p>"
    "</body></html>"
)
PLAIN_CHAPTERS = STYLED_CHAPTERS.replace("<span>", "").replace("</span>", "")
STYLED_CODE = (
    "<pre><code>if enabled:\n"
    "    <span>print</span>(\"ok\")\n"
    "</code></pre>"
)


def _stdlib(fragment: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(fragment)
    return parser.get_text()


class TestBeautifulSoupInlineContinuity:
    def test_styled_heading_matches_plain_and_stdlib(self):
        styled = extract_html_content(STYLED_CHAPTERS)
        plain = extract_html_content(PLAIN_CHAPTERS)
        assert "hyper\ntext" not in styled
        assert "hypertext" in styled
        assert "Chapter 1: Syntax" in styled
        assert detect_structure(styled)["chapters_detected"] == 2
        assert detect_structure(plain)["chapters_detected"] == 2
        assert detect_structure(_stdlib(STYLED_CHAPTERS))["chapters_detected"] == 2

    def test_highlighted_code_keeps_indentation(self):
        extracted = extract_html_content(STYLED_CODE)
        assert extracted == "if enabled:\n    print(\"ok\")\n"
        compile(extracted, "<synthetic-not-executed>", "exec")

    def test_leading_spaces_and_nested_spans_stay_on_the_line(self):
        raw = "<pre><code>  <span>return <b>value</b></span>\n</code></pre>"
        extracted = extract_html_content(raw)
        assert extracted == "  return value\n"

    def test_block_list_and_table_boundaries_remain(self):
        raw = (
            "<h2>Chapter 1</h2><p>Body</p>"
            "<p>line one<br>line two</p>"
            "<ul><li>alpha</li><li>beta</li></ul>"
            "<table><tr><td>Chapter 2</td><td>Models</td></tr></table>"
        )
        extracted = extract_html_content(raw)
        assert "Chapter 1\nBody" in extracted
        assert "line one\nline two" in extracted
        assert "alpha\nbeta" in extracted
        assert "Chapter 2\tModels" in extracted
        assert detect_structure(extracted)["chapters_detected"] == 2

    def test_inline_markup_and_entities_do_not_add_separators(self):
        raw = "<p>see <b>bold</b> <i>italic</i> <a href=\"#x\">chapter 4</a> & more</p>"
        assert extract_html_content(raw) == "see bold italic chapter 4 & more"

    def test_script_and_style_still_stripped(self):
        raw = "<html><head><title>ignored</title></head><body><style>x{}</style><p>kept</p><script>nope()</script></body></html>"
        extracted = extract_html_content(raw)
        assert "kept" in extracted
        assert "nope" not in extracted
        assert "ignored" not in extracted
        assert "x{}" not in extracted


ebooklib = pytest.importorskip("ebooklib")


class TestEpubInlineContinuity:
    def test_ebooklib_keeps_inline_chapter_text(self, tmp_path):
        from ebooklib import epub

        from book_to_skill.parsers.epub import extract_with_ebooklib, extract_with_zipfile

        book = epub.EpubBook()
        book.set_identifier("synthetic-inline-continuity")
        book.set_title("Synthetic continuity")
        book.set_language("en")
        chapters = []
        for number, title in [(1, "Syntax"), (2, "Safety")]:
            chapter = epub.EpubHtml(title=title, file_name=f"c{number}.xhtml", lang="en")
            chapter.content = (
                f"<h2>Chapter <span>{number}</span>: {title}</h2>"
                "<p>A hyper<span>text</span> term remains continuous.</p>"
            )
            book.add_item(chapter)
            chapters.append(chapter)
        book.toc = tuple(chapters)
        book.add_item(epub.EpubNav())
        book.spine = chapters
        path = tmp_path / "inline-continuity.epub"
        epub.write_epub(str(path), book)

        preferred = extract_with_ebooklib(str(path))
        fallback = extract_with_zipfile(str(path))
        assert preferred is not None
        assert "hyper\ntext" not in preferred
        assert "hypertext" in preferred
        assert detect_structure(preferred)["chapters_detected"] == 2
        assert detect_structure(fallback)["chapters_detected"] == 2
