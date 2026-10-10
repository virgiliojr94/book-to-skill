from __future__ import annotations

import zipfile
import sys
from book_to_skill.exceptions import ExtractionError

# WordprocessingML namespace, used to recognize <w:sdt> content controls.
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _body_skips_sdt_text(document) -> bool:
    """True when a top-level `<w:sdt>` holds text the block iterator drops.

    `Document.iter_inner_content()` yields only the body's direct `<w:p>` and
    `<w:tbl>` children. A content control (`<w:sdt>`) is neither, so its
    paragraphs never reach the caller -- which matters most for a Word TOC,
    often the document's only unit structure as text. An empty control costs
    nothing, so only a control with non-whitespace text counts as a loss.
    """
    body = getattr(getattr(document, "element", None), "body", None)
    if body is None or not hasattr(body, "iterchildren"):
        # No enumerable body (a stub document, say): nothing observed was lost.
        return False
    try:
        children = list(body.iterchildren())
    except TypeError:
        return False
    for child in children:
        if child.tag == _W_NS + "sdt" and "".join(child.itertext()).strip():
            return True
    return False


def extract_docx_with_python_docx(docx_path: str) -> str | None:
    # Called unconditionally (not just via extract_docx()) so this function is
    # self-defending when invoked directly WITH python-docx installed:
    # raises ExtractionError on DOCTYPE/ENTITY declarations before
    # python-docx ever opens the archive. If python-docx is NOT installed,
    # this returns None without validating at all -- a parser that isn't
    # installed parses nothing, so skipping the scan gives up no safety
    # (nothing gets extracted, malicious or not), and it avoids paying the
    # full archive scan on every extract_docx() call in the (default,
    # stdlib-only) case where this parser never even runs. A caller that
    # invokes this function directly and needs a validation guarantee
    # regardless of python-docx's availability should use
    # extract_docx_with_zipfile() or call validate_docx_xml_safety() itself.
    try:
        import docx
        validate_docx_xml_safety(docx_path)
        document = docx.Document(docx_path)
        iter_inner_content = getattr(document, "iter_inner_content", None)
        if not callable(iter_inner_content):
            # Older python-docx releases lack the ordered block iterator. Let
            # extract_docx() use its order-preserving stdlib fallback instead.
            return None
        if _body_skips_sdt_text(document):
            # iter_inner_content() walks the body's direct <w:p>/<w:tbl>
            # children, so a top-level <w:sdt> content control -- how Word
            # stores a generated TOC -- is silently skipped even when it
            # holds the document's only chapter structure. Returning None
            # hands the file to the order-preserving stdlib fallback, which
            # reads the raw XML and keeps that text, rather than reporting a
            # clean run that quietly dropped it.
            return None
        parts = []
        for block in iter_inner_content():
            if hasattr(block, "rows"):
                for row in block.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    if any(cells):
                        parts.append("\t".join(cells))
            elif hasattr(block, "text") and block.text:
                parts.append(block.text)
        return "\n".join(parts)
    except ImportError:
        return None
    except ExtractionError:
        # Without this, the broad `except Exception` below would catch an
        # XXE rejection from validate_docx_xml_safety() too, turning a
        # security refusal into a swallowed [warn] + None.
        raise
    except Exception as e:
        print(f"  [warn] extract_docx_with_python_docx failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def extract_docx_with_zipfile(docx_path: str) -> str | None:
    # Called unconditionally (not just via extract_docx()) so this function is
    # self-defending even when invoked directly: raises ExtractionError on
    # DOCTYPE/ENTITY declarations before the XML ever reaches the parser.
    validate_docx_xml_safety(docx_path)
    try:
        import xml.etree.ElementTree as ET

        with zipfile.ZipFile(docx_path) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        parts: list[str] = []

        def inline_text(elem) -> str:
            """Rebuild text runs without dropping explicit DOCX separators."""
            text_parts: list[str] = []
            for node in elem.iter():
                if node.tag == f"{ns}t" and node.text:
                    text_parts.append(node.text)
                elif node.tag == f"{ns}tab":
                    text_parts.append("\t")
                elif node.tag in {f"{ns}br", f"{ns}cr"}:
                    text_parts.append("\n")
            return "".join(text_parts)

        def emit_block(elem) -> None:
            # Walk block content in document order. Paragraphs join their runs;
            # tables emit one tab-joined line per row (same row format as the
            # python-docx path, but order-preserving — python-docx appends all
            # tables last). Unknown wrappers (e.g. <w:sdt> content controls) are
            # recursed into so their paragraphs/tables are not lost; <w:p> and
            # <w:tbl> are NOT recursed into, so table-cell paragraphs are not
            # double-counted. Cell text concatenates the cell's runs; nested
            # tables fold into the parent cell and are also emitted standalone
            # (rare; best-effort).
            for child in elem:
                tag = child.tag
                if tag == f"{ns}p":
                    paragraph = inline_text(child)
                    if paragraph:
                        parts.append(paragraph)
                elif tag == f"{ns}tbl":
                    for row in child.iter(f"{ns}tr"):
                        cells = []
                        for cell in row.iter(f"{ns}tc"):
                            cells.append(inline_text(cell).strip())
                        if any(cells):
                            parts.append("\t".join(cells))
                else:
                    emit_block(child)

        body = root.find(f"{ns}body")
        emit_block(body if body is not None else root)
        return "\n".join(parts) if parts else None
    except Exception as e:
        print(f"  [warn] extract_docx_with_zipfile failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def validate_docx_xml_safety(docx_path: str) -> None:
    """Scan all XML files in the DOCX zip archive to prevent XML Entity Expansion (Billion Laughs) and XXE injections."""
    try:
        with zipfile.ZipFile(docx_path) as zf:
            for name in zf.namelist():
                if name.endswith(".xml") or name.endswith(".rels"):
                    xml_bytes = zf.read(name)
                    for encoding in ("utf-8", "utf-16", "utf-16le", "utf-16be", "utf-32"):
                        try:
                            content = xml_bytes.decode(encoding, errors="ignore").upper()
                        except LookupError:
                            continue
                        if "<!DOCTYPE" in content or "<!ENTITY" in content:
                            raise ExtractionError(
                                f"Security validation failed: XML file '{name}' in DOCX archive contains forbidden DTD or entity declarations."
                            )
    except zipfile.BadZipFile as e:
        raise ExtractionError(f"Invalid DOCX file: {e}")
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Error during security validation of DOCX archive: {e}")


def extract_docx(docx_path: str) -> tuple[str, str]:
    # Validation lives in each leaf parser (extract_docx_with_python_docx,
    # extract_docx_with_zipfile) so it runs exactly once regardless of which
    # parser actually handles the file, instead of once here plus again in
    # whichever parser this falls through to.
    print("Trying python-docx...", end=" ", flush=True)
    text = extract_docx_with_python_docx(docx_path)
    if text and text.strip():
        print("OK")
        return text, "python-docx"

    print("not available")
    print("Trying stdlib DOCX parser...", end=" ", flush=True)
    text = extract_docx_with_zipfile(docx_path)
    if text and text.strip():
        print("OK")
        return text, "zipfile-docx"

    print("FAILED")
    raise ExtractionError(
        "Could not extract text from DOCX.\n"
        "Install python-docx for best results:\n"
        "  pip3 install python-docx"
    )
