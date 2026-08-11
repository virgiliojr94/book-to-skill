"""Running-header removal must be confined to page edges.

`clean_pdftotext` collects boilerplate candidates from the first and last
non-blank line of each page (`nb[0]` / `nb[-1]`), but then removed every
occurrence of those strings from *every* line of the page. Books very commonly
set the running header to the chapter or section title, so the header string and
a genuine heading are byte-identical — and the genuine heading was deleted along
with the headers.

Separately, a page whose only content is one line counted that line twice toward
the "repeated on more than half the pages" threshold, because it is both `nb[0]`
and `nb[-1]`.

Both failures delete real text, and they are silent: nothing is logged, and
`metadata.json` shows no sign that a line went missing. Since #101 the cleanup
also runs on the pypdf and pdfminer paths, so this applies to every PDF
extractor rather than just pdftotext.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.pdf import clean_pdftotext


class TestBoilerplateRemovalIsEdgeOnly:
    # Running header "Reliability" tops every page; on the last page the same
    # string is also the genuine section heading, mid-page.
    HEADER_MATCHES_HEADING = "\f".join([
        "Reliability\nOpening discussion of the topic.\n42",
        "Reliability\nMore body text on page two.\n43",
        "Reliability\nStill more body text on page three.\n44",
        "Reliability\nEnd of the previous section.\n"
        "Reliability\n"                       # <- genuine mid-page heading
        "This section explains the term properly.\n45",
    ])

    def test_mid_page_heading_survives(self):
        out = clean_pdftotext(self.HEADER_MATCHES_HEADING)

        assert out.count("Reliability") == 1

    def test_surrounding_body_text_intact(self):
        out = clean_pdftotext(self.HEADER_MATCHES_HEADING)

        assert "This section explains the term properly." in out
        assert "End of the previous section." in out

    def test_running_headers_are_still_removed(self):
        out = clean_pdftotext(self.HEADER_MATCHES_HEADING)

        # The four page-top occurrences are gone; only the mid-page one remains.
        assert not out.startswith("Reliability")
        assert out.splitlines()[0] == "Opening discussion of the topic."

    def test_page_numbers_are_still_removed(self):
        out = clean_pdftotext(self.HEADER_MATCHES_HEADING)

        assert not any(str(n) in out for n in (42, 43, 44, 45))

    def test_plain_running_header_still_stripped(self):
        """No genuine mid-page occurrence: behaviour must be unchanged."""
        raw = "\f".join([
            "DESIGNING SYSTEMS\nBody one.",
            "DESIGNING SYSTEMS\nBody two.",
            "DESIGNING SYSTEMS\nBody three.",
        ])
        out = clean_pdftotext(raw)

        assert "DESIGNING SYSTEMS" not in out
        assert "Body one." in out and "Body three." in out

    def test_footer_boilerplate_still_stripped(self):
        raw = "\f".join([
            "Body one.\nO'Reilly Media",
            "Body two.\nO'Reilly Media",
            "Body three.\nO'Reilly Media",
        ])
        out = clean_pdftotext(raw)

        assert "O'Reilly Media" not in out
        assert "Body two." in out


class TestSingleLinePageVoting:
    def test_part_divider_page_is_not_stripped(self):
        """A lone line is both first and last; it must vote once, not twice.

        Four pages, two of which contain only "PART ONE". That is 2 votes, and
        the threshold is `> 4/2 == 2`, so it must NOT be treated as boilerplate.
        Double-counting pushed it to 4 and deleted both divider pages.
        """
        raw = "\f".join([
            "PART ONE",
            "Chapter 1\nBody text of the first chapter.",
            "PART ONE",
            "Chapter 2\nBody text of the second chapter.",
        ])
        out = clean_pdftotext(raw)

        assert out.count("PART ONE") == 2

    def test_genuinely_repeated_single_line_page_still_stripped(self):
        """Over the threshold on honest counting, so it should still go."""
        raw = "\f".join(["NOTICE"] * 3 + ["Chapter 1\nReal body text."])
        out = clean_pdftotext(raw)

        # 3 votes out of 4 pages, threshold > 2 -> still boilerplate.
        assert "NOTICE" not in out
        assert "Real body text." in out


class TestExistingBehaviourPreserved:
    """Regression net for #77, #101 and #119."""

    def test_hyphenated_wrap_still_rejoined(self):
        assert "information" in clean_pdftotext("informa-\ntion is here")

    def test_short_document_keeps_content_and_drops_form_feeds(self):
        out = clean_pdftotext("Page one text.\fPage two text.")

        assert "Page one text." in out and "Page two text." in out
        assert "\f" not in out

    def test_mid_page_bare_number_is_kept(self):
        raw = "\f".join([
            "Intro line.\n7\nMore text after the number.\n1",
            "Second page.\n2",
            "Third page.\n3",
        ])
        out = clean_pdftotext(raw)

        assert "7" in out  # mid-page, not an edge

    def test_one_word_lines_still_survive(self):
        """The #119 fix must keep working through the edge-only change."""
        raw = "\f".join([
            "Body one.\nCIVIL",
            "Body two.\nMIX",
            "Body three.\nVIVID",
        ])
        out = clean_pdftotext(raw)

        for word in ("CIVIL", "MIX", "VIVID"):
            assert word in out, word

    def test_roman_front_matter_numbers_still_stripped(self):
        raw = "\f".join([
            "Preface text one.\niv",
            "Preface text two.\nv",
            "Preface text three.\nvi",
        ])
        out = clean_pdftotext(raw)

        assert "Preface text one." in out
        assert [ln for ln in out.splitlines() if ln.strip() in ("iv", "v", "vi")] == []
