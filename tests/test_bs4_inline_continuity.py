"""BeautifulSoup extraction preserves inline text and structural boundaries."""

import json
import sys

import pytest

from book_to_skill.parsers.html import extract_html_content
from book_to_skill.utils import detect_structure, main


def _chapter_html(styled):
    span_open, span_close = ("<span>", "</span>") if styled else ("", "")
    return (
        "<html><body>"
        f"<h2>Chapter {span_open}1{span_close}: Syntax</h2>"
        f"<p>A hyper{span_open}text{span_close} term remains continuous.</p>"
        f"<h2>Chapter {span_open}2{span_close}: Safety</h2>"
        "<p>Only retry when the failure is temporary.</p>"
        "</body></html>"
    )


def _write_epub(epub, path, styled=None, body=None):
    book = epub.EpubBook()
    book.set_identifier("synthetic-inline-continuity")
    book.set_title("Synthetic continuity")
    book.set_language("en")
    chapters = []
    chapter_specs = ((1, "Code", body),) if body is not None else (
        (1, "Syntax", None),
        (2, "Safety", None),
    )
    for number, title, chapter_body in chapter_specs:
        chapter = epub.EpubHtml(
            title=title,
            file_name=f"c{number}.xhtml",
            lang="en",
        )
        span_open, span_close = ("<span>", "</span>") if styled else ("", "")
        chapter.content = chapter_body or (
            f"<h2>Chapter {span_open}{number}{span_close}: {title}</h2>"
            f"<p>A hyper{span_open}text{span_close} term remains continuous.</p>"
        )
        book.add_item(chapter)
        chapters.append(chapter)
    book.toc = tuple(chapters)
    book.add_item(epub.EpubNav())
    book.spine = chapters
    epub.write_epub(str(path), book)
    return path


@pytest.mark.parametrize("parser", ["html", "epub"])
def test_styled_and_plain_chapters_have_identical_text(parser, tmp_path, monkeypatch):
    pytest.importorskip("bs4")

    if parser == "html":
        monkeypatch.setitem(sys.modules, "trafilatura", None)
        styled = extract_html_content(_chapter_html(True))
        plain = extract_html_content(_chapter_html(False))
    else:
        epub = pytest.importorskip("ebooklib.epub")
        from book_to_skill.parsers.epub import extract_with_ebooklib

        styled = extract_with_ebooklib(str(_write_epub(epub, tmp_path / "styled.epub", True)))
        plain = extract_with_ebooklib(str(_write_epub(epub, tmp_path / "plain.epub", False)))
        assert styled is not None
        assert plain is not None

    assert styled == plain
    assert "Chapter 1: Syntax" in styled
    assert "hypertext" in styled
    assert detect_structure(styled)["chapters_detected"] == 2
    assert detect_structure(plain)["chapters_detected"] == 2


@pytest.mark.parametrize(
    ("fragment", "expected"),
    [
        (
            '<pre><code>if enabled:\n    <span>print</span>("ok")\n</code></pre>',
            'if enabled:\n    print("ok")\n',
        ),
        (
            "<pre><code>if enabled:\n    <span>print(\n"
            '        <span>"ok"</span>\n    )</span>\n</code></pre>',
            'if enabled:\n    print(\n        "ok"\n    )\n',
        ),
    ],
)
@pytest.mark.parametrize("parser", ["html", "epub"])
def test_preformatted_code_keeps_text_nodes_verbatim(
    fragment, expected, parser, tmp_path, monkeypatch
):
    pytest.importorskip("bs4")

    if parser == "html":
        monkeypatch.setitem(sys.modules, "trafilatura", None)
        extracted = extract_html_content(fragment)
        assert extracted == expected
    else:
        epub = pytest.importorskip("ebooklib.epub")
        from book_to_skill.parsers.epub import extract_with_ebooklib

        extracted = extract_with_ebooklib(
            str(_write_epub(epub, tmp_path / "code.epub", body=fragment))
        )
        assert extracted is not None

    # EPUB output also carries the nav document; the code itself must be intact.
    assert expected in extracted
    compile(expected, "<synthetic-not-executed>", "exec")


def test_cli_persists_styled_inline_text_and_chapter_metadata(tmp_path, monkeypatch):
    pytest.importorskip("bs4")
    source = tmp_path / "styled.html"
    source.write_text(_chapter_html(True), encoding="utf-8")
    workdir = tmp_path / "workdir"

    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(workdir))
    monkeypatch.setitem(sys.modules, "trafilatura", None)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", workdir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", workdir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", workdir / "metadata.json")
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *args: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["extract.py", str(source), "--install-missing", "no"],
    )

    main()

    full_text = (workdir / "full_text.txt").read_text(encoding="utf-8")
    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    assert "Chapter 1: Syntax" in full_text
    assert "hypertext" in full_text
    assert metadata["chapters_detected"] == 2


def test_deeply_nested_markup_uses_iterative_bs4_traversal(monkeypatch):
    pytest.importorskip("bs4")
    monkeypatch.setitem(sys.modules, "trafilatura", None)
    depth = 3000
    raw = "<div>" * depth + "nested text" + "</div>" * depth

    assert extract_html_content(raw) == "nested text"


def test_blocks_tables_inline_entities_and_comments(monkeypatch):
    pytest.importorskip("bs4")
    monkeypatch.setitem(sys.modules, "trafilatura", None)
    raw = (
        "<!DOCTYPE html><html><head><title>HIDDEN HEAD</title></head><body>"
        "<h2>Chapter <b>1</b>: <i>Syntax</i></h2>"
        '<p>See <a href="#x">hyper<span>text</span></a> &amp;lt; docs.'
        "<br>Next line.</p>"
        "<ul><li>First</li><li>Second</li></ul>"
        "<table><tr><th>A</th><th>B</th></tr>"
        "<tr><td>1</td><td>2</td></tr></table>"
        "<!-- HIDDEN COMMENT --><script>HIDDEN SCRIPT</script>"
        "<style>HIDDEN STYLE</style></body></html>"
    )

    extracted = extract_html_content(raw)

    assert extracted == (
        "Chapter 1: Syntax\n"
        "See hypertext &lt; docs.\nNext line.\n"
        "First\nSecond\n"
        "A\tB\n1\t2"
    )
