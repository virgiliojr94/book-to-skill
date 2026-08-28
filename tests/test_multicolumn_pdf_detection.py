"""Multi-column PDFs must be extracted in reading order, not `-layout`.

`-layout` welds every column's physical lines together, interleaving
consecutive sentences from different columns and padding the output ~26x
with spaces (#128). The extractor detects multi-column documents with a
gutter heuristic and falls back to reading order (plain `pdftotext`); this
file tests the detector and the mode selection.
"""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.pdf import extract_with_pdftotext, looks_multicolumn


class TestLooksMulticolumn:
    def test_flagged_when_most_substantive_lines_have_a_gutter(self):
        # Three columns welded together: each line carries two 4+ space runs.
        layout = "\n".join(
            "column one text     column two text     column three text"
            for _ in range(10)
        )
        assert looks_multicolumn(layout)

    def test_single_column_reading_order_is_not_multicolumn(self):
        lines = [
            "The standard deduction amount has been increased for all filers.",
            "This sentence continues on the same physical line with no gutter.",
            "Taxpayers who made a qualifying investment may also be eligible.",
        ]
        assert not looks_multicolumn("\n".join(lines) * 5)

    def test_short_lines_are_ignored(self):
        # A table where every line is short has no long gutter lines to flag.
        text = "\n".join(["a b" for _ in range(20)])
        assert not looks_multicolumn(text)

    def test_empty_text_is_not_multicolumn(self):
        assert not looks_multicolumn("")

    def test_threshold_is_respected(self):
        gutter = "left column prose here     right column prose over there"
        plain = (
            "A single line of ordinary prose without any wide internal gutter at all."
        )
        # 50% gutter lines vs default 0.35 threshold -> flagged.
        text = "\n".join([gutter, plain, gutter, plain])
        assert looks_multicolumn(text)
        # Same mix with a stricter threshold -> not flagged.
        assert not looks_multicolumn(text, threshold=0.9)


class TestExtractWithPdftotextModeSelection:
    """The extractor must run plain pdftotext (reading order) for
    multi-column documents and keep `-layout` for single-column ones."""

    def test_multicolumn_document_uses_reading_order(self, monkeypatch):
        multi = "\n".join(
            "left column text     right column text     third column" for _ in range(20)
        )
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(
                cmd, 0, multi if "-layout" not in cmd else multi, ""
            )

        monkeypatch.setattr(
            "book_to_skill.parsers.pdf.shutil.which", lambda _: "/bin/pdftotext"
        )
        monkeypatch.setattr("book_to_skill.parsers.pdf.subprocess.run", fake_run)

        out = extract_with_pdftotext("book.pdf")
        assert out is not None
        assert len(calls) == 2
        assert "-layout" in calls[0]  # probe with layout first
        assert "-layout" not in calls[1]  # then reading order
        assert "left column text" in out

    def test_single_column_document_keeps_layout(self, monkeypatch):
        single = "\n".join(
            "A normal prose line that has no column gutter at all." for _ in range(20)
        )
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, single, "")

        monkeypatch.setattr(
            "book_to_skill.parsers.pdf.shutil.which", lambda _: "/bin/pdftotext"
        )
        monkeypatch.setattr("book_to_skill.parsers.pdf.subprocess.run", fake_run)

        out = extract_with_pdftotext("book.pdf")
        assert out is not None
        assert len(calls) == 1
        assert "-layout" in calls[0]

    def test_failed_layout_probe_returns_none(self, monkeypatch):
        calls: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 1, "", "boom")

        monkeypatch.setattr(
            "book_to_skill.parsers.pdf.shutil.which", lambda _: "/bin/pdftotext"
        )
        monkeypatch.setattr("book_to_skill.parsers.pdf.subprocess.run", fake_run)

        assert extract_with_pdftotext("book.pdf") is None
        assert len(calls) == 1

    def test_missing_pdftotext_returns_none_without_calling(self, monkeypatch):
        called = False

        def fake_run(cmd, **kwargs):
            nonlocal called
            called = True
            raise AssertionError("must not run")

        monkeypatch.setattr("book_to_skill.parsers.pdf.shutil.which", lambda _: None)
        monkeypatch.setattr("book_to_skill.parsers.pdf.subprocess.run", fake_run)

        assert extract_with_pdftotext("book.pdf") is None
        assert not called
