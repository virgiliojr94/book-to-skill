"""A DOCX table of contents inside a `<w:sdt>` must not be dropped silently.

`Document.iter_inner_content()` yields the body's direct `<w:p>` / `<w:tbl>`
children only, so a top-level `<w:sdt>` content control -- how Word stores a
generated TOC -- never reaches it. #268 reported a document whose *only* unit
structure lived in that control: extraction still returned non-empty text, so
the stdlib fallback never ran and the whole TOC vanished with exit code 0.

The detection decision is pinned against raw `word/document.xml` so the matrix
CI (pytest only, no python-docx) actually runs these regressions.
"""

import sys
import zipfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.parsers.docx import (  # noqa: E402
    extract_docx_with_python_docx,
    extract_docx_with_zipfile,
    top_level_sdt_holds_text,
)

TOC_HEADING = "第二单元 角 的 度 量"
BODY_LINE = "1  填一填，说一说。"

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

DOCUMENT_XML_WITH_TOC_IN_SDT = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{_W_NS}">
  <w:body>
    <w:sdt>
      <w:sdtPr/>
      <w:sdtContent>
        <w:p><w:r><w:t>{TOC_HEADING}</w:t></w:r></w:p>
      </w:sdtContent>
    </w:sdt>
    <w:p><w:r><w:t>{BODY_LINE}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

DOCUMENT_XML_PLAIN = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{_W_NS}">
  <w:body>
    <w:p><w:r><w:t>{TOC_HEADING}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{BODY_LINE}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

DOCUMENT_XML_EMPTY_SDT = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{_W_NS}">
  <w:body>
    <w:sdt>
      <w:sdtPr/>
      <w:sdtContent>
        <w:p/>
      </w:sdtContent>
    </w:sdt>
    <w:p><w:r><w:t>{BODY_LINE}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""

_CONTENT_TYPES = (
    '<?xml version="1.0"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
)


def _write_minimal_docx(path: Path, document_xml: str) -> Path:
    """Build a DOCX with only the stdlib — no python-docx required."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
    return path


class TestSdtDetectionIsDependencyFree:
    def test_top_level_sdt_with_text_is_detected(self):
        assert top_level_sdt_holds_text(DOCUMENT_XML_WITH_TOC_IN_SDT.encode("utf-8"))

    def test_plain_body_is_not_flagged(self):
        assert not top_level_sdt_holds_text(DOCUMENT_XML_PLAIN.encode("utf-8"))

    def test_empty_content_control_is_not_flagged(self):
        assert not top_level_sdt_holds_text(DOCUMENT_XML_EMPTY_SDT.encode("utf-8"))


class TestSdtContentControlNotDropped:
    def test_python_docx_parser_defers_to_fallback_when_toc_is_in_sdt(self, tmp_path):
        path = _write_minimal_docx(tmp_path / "sdt.docx", DOCUMENT_XML_WITH_TOC_IN_SDT)

        # Detection runs on the raw XML, so this declines even when
        # python-docx is not installed (ImportError path also returns None,
        # but the explicit deferral is what we pin).
        assert extract_docx_with_python_docx(str(path)) is None

        fallback = extract_docx_with_zipfile(str(path))
        assert fallback is not None
        assert TOC_HEADING in fallback
        assert BODY_LINE in fallback

    def test_stdlib_fallback_keeps_toc_inside_sdt(self, tmp_path):
        path = _write_minimal_docx(tmp_path / "sdt.docx", DOCUMENT_XML_WITH_TOC_IN_SDT)
        text = extract_docx_with_zipfile(str(path))
        assert text is not None
        assert TOC_HEADING in text
        assert BODY_LINE in text

    def test_empty_content_control_does_not_trigger_the_fallback_decision(self, tmp_path):
        path = _write_minimal_docx(tmp_path / "empty-sdt.docx", DOCUMENT_XML_EMPTY_SDT)
        assert not top_level_sdt_holds_text(
            zipfile.ZipFile(path).read("word/document.xml")
        )
