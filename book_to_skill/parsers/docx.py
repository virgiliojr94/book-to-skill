from __future__ import annotations

import zipfile
import sys
from book_to_skill.exceptions import ExtractionError


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
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any(cells):
                    parts.append("\t".join(cells))
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
        try:
            import defusedxml.ElementTree as ET  # hardened B314
        except ImportError:
            import xml.etree.ElementTree as ET  # nosec B314 - DTD pre-scan validates

        with zipfile.ZipFile(docx_path) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)  # nosec B314 - ET is defusedxml when available, else DTD pre-scan validates
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        parts: list[str] = []

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
                    texts = [t.text for t in child.iter(f"{ns}t") if t.text]
                    if texts:
                        parts.append("".join(texts))
                elif tag == f"{ns}tbl":
                    for row in child.iter(f"{ns}tr"):
                        cells = []
                        for cell in row.iter(f"{ns}tc"):
                            cell_texts = [t.text for t in cell.iter(f"{ns}t") if t.text]
                            cells.append("".join(cell_texts).strip())
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
            # Zip-bomb guard — deterministic, lightweight (IP-001) — must run before any read()
            names = zf.namelist()
            if len(names) > 10000:
                raise ExtractionError(f"Security validation failed: DOCX archive has too many entries ({len(names)} > 10000) — possible zip-bomb.")
            # file_size is decompressed size; sum >100MB or ratio >100 signals bomb
            try:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > 100 * 1024 * 1024:
                    raise ExtractionError(f"Security validation failed: DOCX uncompressed size {total_uncompressed} > 100MB — possible zip-bomb.")
                for info in zf.infolist():
                    if info.file_size > 0 and info.compress_size > 0 and info.file_size / max(1, info.compress_size) > 200:
                        # Single file with extreme ratio (e.g. 1KB -> 10MB) — classic bomb shape
                        if info.file_size > 1024 * 1024:
                            raise ExtractionError(f"Security validation failed: entry '{info.filename}' has suspicious compression ratio — possible zip-bomb.")
            except ExtractionError:
                raise
            except Exception:
                pass  # info stats unavailable — fall through to DTD scan
            for name in names:
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
