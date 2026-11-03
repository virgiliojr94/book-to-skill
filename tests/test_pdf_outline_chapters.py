"""PDF chapters come from the embedded outline when the PDF has one.

Numbered layout lines ("1  Introduction", listing captions, ToC rows) made the
text heuristics report hundreds of chapters for a technical book whose outline
lists 14. The outline is preferred; the heuristics remain the fallback.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pypdf = pytest.importorskip("pypdf")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import book_to_skill.utils as utils  # noqa: E402

# Body text the heuristic scan counts as 5 chapters.
_LINES = [f"Chapter {n}" for n in range(1, 6)]


def _text_pdf(path: Path, lines: list[str]) -> None:
    """Write a one-page PDF with real, extractable text (no extra deps)."""
    ops = "".join(
        f"BT /F1 12 Tf 72 {720 - 20 * i} Td ({line}) Tj ET\n" for i, line in enumerate(lines)
    ).encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(ops) + ops + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))


def _add_outline(path: Path) -> None:
    writer = pypdf.PdfWriter(clone_from=str(path))
    writer.add_outline_item("Cover", 0)
    writer.add_outline_item("Preface", 0)
    for part, chapters in (("Part I. Storage", ["Chapter 1", "Chapter 2"]),
                           ("Part II. Distribution", ["Chapter 3"])):
        parent = writer.add_outline_item(part, 0)
        for title in chapters:
            writer.add_outline_item(title, 0, parent=parent)
    writer.add_outline_item("Index", 0)
    with open(path, "wb") as f:
        writer.write(f)


def test_outline_wins_over_numbered_lines(tmp_path):
    pdf = tmp_path / "book.pdf"
    _text_pdf(pdf, _LINES)
    _add_outline(pdf)
    result = utils.extract_single_file(pdf, "text", "never")
    assert result["chapters_method"] == "outline"
    assert result["chapter_headings_sample"] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert result["chapter_titles"] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert result["chapters_detected"] == 3


def test_no_outline_falls_back_to_heuristics(tmp_path):
    pdf = tmp_path / "book.pdf"
    _text_pdf(pdf, _LINES)
    result = utils.extract_single_file(pdf, "text", "never")
    assert result["chapters_method"] == "numeric"
    assert result["chapters_detected"] == 5


def test_outline_chapter_ranges_in_extracted_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "book_to_skill.pdf_inspector_integration.inspect_pdf",
        lambda _path: (None, None),
    )
    pdf = tmp_path / "book.pdf"
    body = [
        "CHAPTER 1",
        "Alpha",
        "body-one",
        "CHAPTER 2",
        "Beta",
        "body-two",
        "Part I Conclusion",
        "part-tail",
    ]
    _text_pdf(pdf, body)
    writer = pypdf.PdfWriter(clone_from=str(pdf))
    writer.add_outline_item("Chapter 1. Alpha", 0)
    writer.add_outline_item("Chapter 2. Beta", 0)
    writer.add_outline_item("Part I Conclusion", 0)
    with open(pdf, "wb") as handle:
        writer.write(handle)

    workdir = tmp_path / "out"
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(workdir))
    import book_to_skill.config as config
    monkeypatch.setattr(config, "OUTPUT_DIR", workdir)
    monkeypatch.setattr(config, "OUTPUT_TEXT", workdir / "full_text.txt")
    monkeypatch.setattr(config, "OUTPUT_META", workdir / "metadata.json")
    monkeypatch.setattr(utils, "OUTPUT_DIR", workdir)
    monkeypatch.setattr(utils, "OUTPUT_TEXT", workdir / "full_text.txt")
    monkeypatch.setattr(utils, "OUTPUT_META", workdir / "metadata.json")

    from book_to_skill.pdf_inspector_integration import install_pdf_inspector_hook

    install_pdf_inspector_hook()

    monkeypatch.setattr(
        sys,
        "argv",
        ["extract", str(pdf), "--mode", "text", "--install-missing", "no"],
    )
    utils.main()
    metadata = json.loads((workdir / "metadata.json").read_text(encoding="utf-8"))
    ranges = metadata["chapter_ranges"]
    assert len(ranges) == 2
    assert ranges[0]["title"] == "Chapter 1. Alpha"
    full_text = (workdir / "full_text.txt").read_text(encoding="utf-8").splitlines()
    assert full_text[ranges[0]["end_line"]].startswith("CHAPTER 2")
    assert full_text[ranges[1]["end_line"]].startswith("Part I Conclusion")
    assert "body-one" in "\n".join(full_text[ranges[0]["start_line"] - 1 : ranges[0]["end_line"]])
