from __future__ import annotations

import html
import html.parser
from book_to_skill.parsers.text import read_text_file


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Minimal HTML → plain text converter using stdlib only."""

    SKIP_TAGS = {"script", "style", "head"}

    # Block-level elements. A boundary is emitted both when they open and when
    # they CLOSE — closing matters, because without it the text of two adjacent
    # blocks concatenates ("<h2>Chapter 1</h2>Intro" -> "Chapter 1Intro"), which
    # destroys chapter detection: _EXPLICIT_CHAPTER requires a word boundary
    # after the number, and "1I" has none.
    BLOCK_TAGS = frozenset({
        "address", "article", "aside", "blockquote", "br", "dd", "details",
        "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer",
        "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr",
        "li", "main", "nav", "ol", "p", "pre", "section", "table", "tbody",
        "tfoot", "thead", "tr", "ul",
    })
    # Table cells are separated by a tab rather than a newline so a row stays on
    # one line — the same convention the stdlib DOCX fallback already uses for
    # tab-joined table rows, and what keeps a table-formatted table of contents
    # ("Chapter 1 | Introduction | 1") parseable as a single heading line.
    CELL_TAGS = frozenset({"td", "th"})

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        # Strongest boundary awaiting the next non-blank text run. Deferring it
        # (instead of appending immediately) means nested blocks such as
        # "<div><p>x" collapse to one separator rather than a run of blank lines.
        self._pending = ""

    def _mark(self, separator: str) -> None:
        # "\n" outranks "\t": a row/block boundary must not be downgraded to a
        # cell boundary by a <td> that opens straight after a <tr>.
        if separator == "\n" or not self._pending:
            self._pending = separator

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag in self.BLOCK_TAGS:
            self._mark("\n")
        elif tag in self.CELL_TAGS:
            self._mark("\t")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if tag in self.BLOCK_TAGS:
            self._mark("\n")
        elif tag in self.CELL_TAGS:
            self._mark("\t")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._pending:
            if not data.strip():
                # Whitespace-only text between tags is layout indentation. It
                # cannot satisfy a pending boundary, and emitting it before the
                # boundary would just add trailing spaces — drop it and keep
                # waiting for real content.
                return
            # Suppress a leading separator so the output does not start with a
            # blank line.
            if self._parts:
                self._parts.append(self._pending)
            self._pending = ""
        self._parts.append(data)

    def get_text(self) -> str:
        # HTMLParser(convert_charrefs=True) already decoded entities in
        # handle_data; do NOT unescape again or double-encoded entities
        # (e.g. "&amp;amp;") collapse incorrectly.
        return "".join(self._parts)


def extract_html_content(raw_html: str) -> str:
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_html, "html.parser")
        for element in soup(["script", "style", "head"]):
            element.decompose()
        return soup.get_text(separator="\n")
    except ImportError:
        parser = _HTMLTextExtractor()
        parser.feed(raw_html)
        return parser.get_text()


def extract_html_file(path: str) -> str | None:
    raw = read_text_file(path)
    if raw is None:
        return None
    return extract_html_content(raw)
