from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections import Counter

# A bare page number sitting alone on a line: Arabic, or a Roman numeral of the
# kind used to number front matter.
#
# The Roman branch spells out the SHAPE of a canonical numeral instead of
# listing the letters one may contain. `[ivxlcdm]{1,7}` matched any short word
# built from those letters, so "MIX", "CIVIL", "DIM", "MILD" and "VIVID" were
# all silently deleted whenever they landed on a page's first or last non-blank
# line — a one-word line is exactly what a part title or a display heading looks
# like. Deleting real text is a worse failure than leaving a stray numeral, so
# the pattern is now exact.
#
# The range is 1-99, which is what front matter uses; "c"/"d"/"m" therefore no
# longer match on their own, so a lone "C" or "M" line is now kept as text.
# `(?=[ivxl])` is the non-empty guard: both groups are individually optional, so
# without it the pattern would match a blank line.
_ROMAN_1_99 = r"(?=[ivxl])(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_PDF_PAGE_NUM = re.compile(rf"^\s*(?:\d{{1,4}}|{_ROMAN_1_99})\s*$", re.IGNORECASE)
_PDF_HYPHEN_WRAP = re.compile(r"(\w)-\n(\w)")


def clean_pdftotext(text: str) -> str:
    """Clean pdftotext '-layout' output (pages are form-feed delimited): drop
    repeated running headers/footers and edge page numbers, and join words split
    across a line by a hyphen."""
    pages = text.split("\f")
    if len(pages) >= 3:
        # A top/bottom line repeated on > half the pages is boilerplate.
        edge = Counter()
        for p in pages:
            nb = [ln.strip() for ln in p.splitlines() if ln.strip()]
            if nb:
                edge[nb[0]] += 1
                # On a single-line page the first and last line are the same
                # line. Counting it twice would let one page cast two votes
                # toward the "more than half the pages" threshold below, so a
                # part-divider page occurring twice in four pages would reach 4
                # votes instead of 2 and be stripped as boilerplate.
                if len(nb) > 1:
                    edge[nb[-1]] += 1
        boiler = {ln for ln, c in edge.items() if c > len(pages) / 2}
        kept = []
        for p in pages:
            lines = p.splitlines()
            nb_idx = [i for i, ln in enumerate(lines) if ln.strip()]
            first = nb_idx[0] if nb_idx else None
            last = nb_idx[-1] if nb_idx else None
            for i, ln in enumerate(lines):
                # Running headers/footers and page numbers only ever occur at a
                # page edge -- which is also the only place `boiler` is
                # collected from. Removing a boilerplate string from every line
                # meant that when a running header repeated the section title
                # (common typesetting), the genuine mid-page heading was deleted
                # along with the headers.
                if i in (first, last):
                    s = ln.strip()
                    if s in boiler or _PDF_PAGE_NUM.match(s):
                        continue
                kept.append(ln)
        text = "\n".join(kept)
    else:
        text = text.replace("\f", "\n")
    # ponytail: naive dehyphenation; may join a genuinely-hyphenated wrapped
    # compound ("well-\nknown" -> "wellknown"). Dictionary-aware split if it bites.
    return _PDF_HYPHEN_WRAP.sub(r"\1\2", text)


def extract_with_pdftotext(pdf_path: str) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        pdf_path = os.path.abspath(pdf_path)
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0 and result.stdout.strip():
            return clean_pdftotext(result.stdout)
    except Exception as e:
        print(f"  [warn] extract_with_pdftotext failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None


def looks_image_only(pdf_path: str, pages: int = 5) -> bool:
    """True when the first `pages` pages yield no extractable text — the signature
    of a scanned/image-only PDF. Cheap pre-flight so a scan fails in a second
    instead of after the whole extraction chain has run. Best-effort: without
    pdftotext it reports False and the normal chain (plus the final empty-text
    guard) still applies."""
    if not shutil.which("pdftotext"):
        return False
    try:
        result = subprocess.run(
            ["pdftotext", "-f", "1", "-l", str(pages), os.path.abspath(pdf_path), "-"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        return result.returncode == 0 and not result.stdout.strip()
    except Exception:
        return False


def extract_with_pypdf(pdf_path: str) -> str | None:
    try:
        import pypdf
        text_parts = []
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    text_parts.append("")
        # Join pages with a form feed so clean_pdftotext can strip repeated
        # per-page headers/footers, not just dehyphenate.
        return clean_pdftotext("\f".join(text_parts))
    except ImportError:
        return None
    except Exception as e:
        print(f"  [warn] extract_with_pypdf failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def extract_with_pdfminer(pdf_path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(pdf_path)  # already form-feed delimited per page
        return clean_pdftotext(text) if text else text
    except ImportError:
        return None
    except Exception as e:
        print(f"  [warn] extract_with_pdfminer failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def extract_with_docling(pdf_path: str) -> str | None:
    """Layout-aware extraction using Docling. Best for technical books with tables and code."""
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        result = converter.convert(pdf_path)
        return result.document.export_to_markdown()
    except ImportError:
        return None
    except Exception as e:
        print(f"  [warn] extract_with_docling failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def count_pages(pdf_path: str) -> int:
    # Try pdfinfo first
    if shutil.which("pdfinfo"):
        try:
            pdf_path = os.path.abspath(pdf_path)
            result = subprocess.run(
                ["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15
            )
            for line in result.stdout.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split(":")[1].strip())
        except Exception:
            pass
    # Fallback: count pages with pypdf
    try:
        import pypdf
        with open(pdf_path, "rb") as f:
            return len(pypdf.PdfReader(f).pages)
    except Exception:
        return 0
