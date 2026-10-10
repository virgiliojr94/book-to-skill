"""A DOCX table of contents inside a `<w:sdt>` must not be dropped silently.

`Document.iter_inner_content()` yields the body's direct `<w:p>` / `<w:tbl>`
children only, so a top-level `<w:sdt>` content control -- how Word stores a
generated TOC -- never reaches it. #268 reported a document whose *only* unit
structure lived in that control: extraction still returned non-empty text, so
the stdlib fallback never ran and the whole TOC vanished with exit code 0.
"""

import sys
import zipfile
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

docx = pytest.importorskip("docx")

from book_to_skill.parsers.docx import (  # noqa: E402
    extract_docx_with_python_docx,
    extract_docx_with_zipfile,
)

TOC_HEADING = "第二单元 角 的 度 量"
BODY_LINE = "1  填一填，说一说。"

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:sdt>
      <w:sdtPr/>
      <w:sdtContent>
        <w:p><w:r><w:t>{heading}</w:t></w:r></w:p>
      </w:sdtContent>
    </w:sdt>
    <w:p><w:r><w:t>{body}</w:t></w:r></w:p>
  </w:body>
</w:document>
""".format(heading=TOC_HEADING, body=BODY_LINE)


def _write_docx_with_toc_in_sdt(path: Path) -> Path:
    """Build a minimal DOCX whose TOC sits inside a `<w:sdt>` content control."""
    document = docx.Document()
    document.add_paragraph("placeholder")
    document.save(str(path))

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        blobs = {name: zf.read(name) for name in names}

    blobs["word/document.xml"] = DOCUMENT_XML.encode("utf-8")

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            zf.writestr(name, blobs[name])
    return path


def _write_docx_without_sdt(path: Path) -> Path:
    document = docx.Document()
    document.add_paragraph(TOC_HEADING)
    document.add_paragraph(BODY_LINE)
    document.save(str(path))
    return path


class TestSdtContentControlNotDropped:
    def test_python_docx_parser_defers_to_fallback_when_toc_is_in_sdt(self, tmp_path):
        path = _write_docx_with_toc_in_sdt(tmp_path / "sdt.docx")

        # The ordered block iterator cannot see inside the content control, so
        # the parser must decline rather than return the truncated text.
        assert extract_docx_with_python_docx(str(path)) is None

        # The stdlib fallback reads the raw XML and keeps the TOC heading.
        fallback = extract_docx_with_zipfile(str(path))
        assert fallback is not None
        assert TOC_HEADING in fallback
        assert BODY_LINE in fallback

    def test_document_without_sdt_still_uses_the_python_docx_parser(self, tmp_path):
        path = _write_docx_without_sdt(tmp_path / "plain.docx")

        text = extract_docx_with_python_docx(str(path))
        assert text is not None
        assert TOC_HEADING in text
        assert BODY_LINE in text

    def test_empty_content_control_does_not_trigger_the_fallback(self, tmp_path):
        # An empty <w:sdt> costs no text, so it must not push every document
        # that happens to contain one onto the slower stdlib path.
        path = tmp_path / "empty-sdt.docx"
        document = docx.Document()
        document.add_paragraph(BODY_LINE)
        document.save(str(path))

        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            blobs = {name: zf.read(name) for name in names}
        xml = blobs["word/document.xml"].decode("utf-8")
        xml = xml.replace(
            "<w:body>",
            "<w:body><w:sdt><w:sdtPr/><w:sdtContent><w:p/></w:sdtContent></w:sdt>",
            1,
        )
        blobs["word/document.xml"] = xml.encode("utf-8")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                zf.writestr(name, blobs[name])

        text = extract_docx_with_python_docx(str(path))
        assert text is not None
        assert BODY_LINE in text