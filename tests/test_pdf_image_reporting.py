"""PDF extraction reports how many embedded images it could not read.

pdftotext, pypdf and pdfminer read only the text layer, so a PDF page that is a
full-page image (a scanned cheat sheet, an embedded figure) contributes nothing
but its running header and footer. EPUB already reports this as
``images_dropped``; PDFs reported ``null``, so the Step 2.5 / Step 9 warning in
SKILL.md never fired for them (#349).
"""

import json
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import book_to_skill.pdf_inspector_integration as integration
from book_to_skill.parsers.pdf import count_pdf_images
from book_to_skill.utils import extract_single_file, main

needs_poppler = pytest.mark.skipif(
    not (shutil.which("pdftotext") and shutil.which("pdfimages")),
    reason="pdftotext and pdfimages (poppler-utils) are required",
)


def _make_pdf(path, pages):
    """Write a tiny PDF. Each page is (text, image) where image is None,
    "own" (a new image object for this page) or "shared" (one image object
    reused by every page that asks for it, like a logo)."""
    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    def image_object():
        return add(
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
            b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
            b"stream\n\x80\nendstream"
        )

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    shared = image_object()
    parent = add(b"")
    kids = []
    for text, image in pages:
        content = b""
        resources = b"<< /Font << /F1 %d 0 R >>" % font
        if image is not None:
            ref = shared if image == "shared" else image_object()
            resources += b" /XObject << /Im0 %d 0 R >>" % ref
            content += b"q 200 0 0 200 50 50 cm /Im0 Do Q\n"
        resources += b" >>"
        if text:
            content += b"BT /F1 12 Tf 30 270 Td (" + text.encode() + b") Tj ET\n"
        stream = add(b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream")
        kids.append(add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 300 300] "
            b"/Resources %s /Contents %d 0 R >>" % (parent, resources, stream)
        ))
    objects[parent - 1] = (
        b"<< /Type /Pages /Kids ["
        + b" ".join(b"%d 0 R" % kid for kid in kids)
        + b"] /Count %d >>" % len(kids)
    )
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % parent)

    data = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    data += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    data += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, catalog, xref,
    )
    path.write_bytes(data)
    return path


def _book_with_image_pages(path, image_pages):
    # Text pages first so the scanned-PDF preflight (first 5 pages) passes.
    pages = [(f"Chapter {n} prose", None) for n in range(1, 7)]
    pages += [(f"{n} | P a g e", "own") for n in range(7, 7 + image_pages)]
    return _make_pdf(path, pages)


@needs_poppler
def test_count_pdf_images_counts_a_repeated_logo_once(tmp_path):
    pdf = _make_pdf(tmp_path / "logo.pdf", [(f"Page {n}", "shared") for n in range(10)])

    assert count_pdf_images(str(pdf)) == 1


@needs_poppler
def test_count_pdf_images_is_zero_for_a_text_only_pdf(tmp_path):
    pdf = _make_pdf(tmp_path / "text.pdf", [("Only text", None)] * 3)

    assert count_pdf_images(str(pdf)) == 0


def test_count_pdf_images_is_unknown_without_pdfimages(tmp_path):
    with mock.patch("book_to_skill.parsers.pdf.shutil.which", return_value=None):
        assert count_pdf_images(str(tmp_path / "book.pdf")) is None


def test_count_pdf_images_is_unknown_when_pdfimages_fails(tmp_path):
    failed = subprocess.CompletedProcess([], 1, stdout="", stderr="Syntax Error")
    with mock.patch("book_to_skill.parsers.pdf.shutil.which", return_value="/usr/bin/pdfimages"), \
            mock.patch("book_to_skill.parsers.pdf.subprocess.run", return_value=failed):
        assert count_pdf_images(str(tmp_path / "book.pdf")) is None


def test_count_pdf_images_is_unknown_when_pdfimages_times_out(tmp_path, capsys):
    timeout = subprocess.TimeoutExpired(["pdfimages"], 30)
    with mock.patch("book_to_skill.parsers.pdf.shutil.which", return_value="/usr/bin/pdfimages"), \
            mock.patch("book_to_skill.parsers.pdf.subprocess.run", side_effect=timeout):
        assert count_pdf_images(str(tmp_path / "book.pdf")) is None
    assert "TimeoutExpired" in capsys.readouterr().err


def test_count_pdf_images_parses_inline_images_stencils_and_skips_masks(tmp_path):
    listing = (
        "page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio\n"
        "--------------------------------------------------------------------------------------------\n"
        "   1     0 image     100   100  rgb     3   8  jpeg   no        12  0   300   300 2000B 6.7%\n"
        "   1     1 smask     100   100  gray    1   8  image  no        13  0   300   300  100B 1.0%\n"
        "   2     2 image     100   100  rgb     3   8  jpeg   no        12  0   300   300 2000B 6.7%\n"
        "   3     3 image       1     1  gray    1   8  image  no   [inline]   0.720 0.720    0B 0.0%\n"
        "   4     4 image       1     1  gray    1   8  image  no   [inline]   0.720 0.720    0B 0.0%\n"
        "   5     5 stencil  2480  3508  -       1   1  ccitt  no        20  0   300   300 40.0K 3.7%\n"
        "   5     6 mask     2480  3508  -       1   1  ccitt  no        21  0   300   300 40.0K 3.7%\n"
    )
    done = subprocess.CompletedProcess([], 0, stdout=listing, stderr="")
    with mock.patch("book_to_skill.parsers.pdf.shutil.which", return_value="/usr/bin/pdfimages"), \
            mock.patch("book_to_skill.parsers.pdf.subprocess.run", return_value=done):
        # Object 12 drawn twice counts once; each inline image counts; the
        # stencil (a bilevel scan) counts; the smask and mask rows belong to
        # other images and are not separate images.
        assert count_pdf_images(str(tmp_path / "book.pdf")) == 4


@needs_poppler
def test_pdf_extraction_reports_dropped_image_pages(tmp_path, capsys):
    pdf = _book_with_image_pages(tmp_path / "book.pdf", image_pages=7)

    with mock.patch("book_to_skill.utils.prepare_dependencies"):
        result = extract_single_file(pdf, "text", "no")

    assert result["extraction_method"] == "pdftotext"
    assert result["images_dropped"] == 7
    stderr = capsys.readouterr().err
    assert "7 image(s)" in stderr
    assert "content is not extracted" in stderr


@needs_poppler
def test_pdf_extraction_keeps_a_few_figures_quiet(tmp_path, capsys):
    pdf = _book_with_image_pages(tmp_path / "book.pdf", image_pages=2)

    with mock.patch("book_to_skill.utils.prepare_dependencies"):
        result = extract_single_file(pdf, "text", "no")

    assert result["images_dropped"] == 2
    assert "content is not extracted" not in capsys.readouterr().err


@needs_poppler
def test_main_persists_pdf_image_loss_in_source_and_total_metadata(tmp_path, monkeypatch):
    pdf = _book_with_image_pages(tmp_path / "book.pdf", image_pages=7)
    output_dir = tmp_path / "output"
    output_meta = output_dir / "metadata.json"

    monkeypatch.setattr(sys, "argv", ["extract.py", str(pdf), "--install-missing", "no"])
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", output_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", output_dir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", output_meta)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *args: None)

    main()

    metadata = json.loads(output_meta.read_text(encoding="utf-8"))
    assert metadata["images_dropped"] == 7
    assert metadata["sources"][0]["images_dropped"] == 7


def test_pdf_inspector_path_reports_dropped_images(tmp_path, monkeypatch, capsys):
    integration._reset_state_for_tests()
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7\nfixture")

    from book_to_skill import utils

    fake_utils = SimpleNamespace(
        extract_single_file=lambda *args: {"extraction_method": "legacy"},
        sanitize_extracted_text=lambda text: (text, 0),
        detect_structure=lambda _text: {
            "chapters_detected": 1,
            "chapters_method": "numeric",
            "chapter_headings_sample": ["Chapter 1"],
            "has_toc": False,
        },
        count_pages=lambda _path: 12,
        estimate_tokens=lambda _text: 42,
        count_pdf_images=lambda _path: 9,
        report_dropped_images=utils.report_dropped_images,
    )
    inspection = {
        "confidence": 0.99,
        "page_count": 12,
        "pdf_type": "text_based",
        "native_markdown_trusted": True,
        "pages_needing_ocr": [],
        "has_encoding_issues": False,
    }
    monkeypatch.setattr(integration, "inspect_pdf", lambda _path: ("Chapter 1\nBody", inspection))

    integration.install_pdf_inspector_hook(fake_utils)
    result = fake_utils.extract_single_file(pdf, "text", "no")

    assert result["extraction_method"] == "pdf-inspector"
    assert result["images_dropped"] == 9
    assert "9 image(s)" in capsys.readouterr().err
