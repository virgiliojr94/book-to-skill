"""`pdftotext -layout` must not be used on multi-column documents.

`-layout` preserves horizontal position, which keeps table columns aligned on a
single-column page and destroys reading order on a multi-column one: every
emitted line spans all columns, so consecutive sentences from different columns
interleave.

Measured on IRS Publication 17 (142 pages, three columns per page), searching
both extractions for the same phrase:

    -layout        'standard deduction or if you    (QOF). Taxpayers who made a'
    reading order  'Standard deduction amount increased. For 2025, the standard
                    deduction amount has been increased for all filers'

The first is three columns welded together. A skill distilled from it can
contain sentences that never existed in the book.

The size difference on the same document — 25,266,249 chars at 96.8%
whitespace versus 957,757 — is the visible symptom, but it is the ordering
that makes the output wrong rather than merely large.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers import pdf as pdf_parser
from book_to_skill.parsers.pdf import extract_with_pdftotext, looks_multicolumn


def _single_column(lines: int = 60) -> str:
    body = ("The quick brown fox jumps over the lazy dog and keeps running "
            "until it reaches the far side of the field.")
    return "\n".join(body for _ in range(lines))


def _two_column(lines: int = 60) -> str:
    """What -layout emits for side-by-side text: one line spanning both."""
    left = "The quick brown fox jumps over the lazy dog and keeps"
    right = "Separately typeset material that belongs to another column"
    return "\n".join(f"{left}        {right}" for _ in range(lines))


# ── detection ────────────────────────────────────────────────────────────

def test_single_column_is_not_flagged():
    assert not looks_multicolumn(_single_column())


def test_two_column_is_flagged():
    assert looks_multicolumn(_two_column())


def test_empty_and_whitespace_only_input_are_safe():
    assert not looks_multicolumn("")
    assert not looks_multicolumn("\n\n   \n")


def test_short_lines_alone_do_not_trigger_detection():
    """Headings, page numbers and list stubs pick up wide gaps by accident.
    Only lines long enough to span a column count as evidence."""
    assert not looks_multicolumn("\n".join("Ch 1        7" for _ in range(50)))


def test_a_few_wide_gaps_do_not_flag_a_single_column_document():
    """A table or two inside an otherwise single-column book must not flip the
    whole document into reading-order mode."""
    text = _single_column(50) + "\n" + _two_column(5)
    assert not looks_multicolumn(text)


# ── extraction ───────────────────────────────────────────────────────────

class _FakeRun:
    def __init__(self, stdout, returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def _patch(monkeypatch, layout_out, plain_out, plain_rc=0):
    """Record which pdftotext invocations happen and with what flags."""
    calls = []

    def fake(pdf_path, *args):
        calls.append(args)
        if "-layout" in args:
            return _FakeRun(layout_out)
        return _FakeRun(plain_out, plain_rc)

    monkeypatch.setattr(pdf_parser, "_pdftotext", fake)
    monkeypatch.setattr(pdf_parser.shutil, "which", lambda _: "/usr/bin/pdftotext")
    return calls


def test_single_column_still_uses_layout_and_runs_once(monkeypatch, tmp_path):
    """The common case must not pay for a second subprocess, and must keep the
    -layout behaviour that aligns tables."""
    calls = _patch(monkeypatch, _single_column(), "READING ORDER")
    out = extract_with_pdftotext(str(tmp_path / "book.pdf"))
    assert calls == [("-layout",)]
    assert "quick brown fox" in out
    assert "READING ORDER" not in out


def test_multicolumn_reruns_without_layout(monkeypatch, tmp_path):
    calls = _patch(monkeypatch, _two_column(), "READING ORDER TEXT")
    out = extract_with_pdftotext(str(tmp_path / "book.pdf"))
    assert calls == [("-layout",), ()]
    assert "READING ORDER TEXT" in out


def test_failed_reading_order_pass_warns_and_keeps_layout(monkeypatch, tmp_path, capsys):
    """Interleaved text still beats no text — but it must not be silent."""
    _patch(monkeypatch, _two_column(), "", plain_rc=1)
    out = extract_with_pdftotext(str(tmp_path / "book.pdf"))
    assert out is not None and "quick brown fox" in out
    assert "may be interleaved" in capsys.readouterr().err


def test_missing_binary_still_returns_none(monkeypatch, tmp_path):
    """The fallback chain contract: return None so the next extractor runs."""
    monkeypatch.setattr(pdf_parser.shutil, "which", lambda _: None)
    assert extract_with_pdftotext(str(tmp_path / "book.pdf")) is None


def test_empty_layout_output_returns_none(monkeypatch, tmp_path):
    _patch(monkeypatch, "   \n", "READING ORDER")
    assert extract_with_pdftotext(str(tmp_path / "book.pdf")) is None


# ── the real thing, when poppler is present ──────────────────────────────

def test_gutter_regex_matches_a_real_layout_line():
    """Guards the constant: a genuine -layout line from Publication 17."""
    line = ("standard deduction or if you        (QOF). Taxpayers who made a")
    assert pdf_parser._PDF_GUTTER.search(line)
    assert not pdf_parser._PDF_GUTTER.search(
        "Standard deduction amount increased. For 2025, the amounts are:")
