from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections import Counter

_PDF_PAGE_NUM = re.compile(r"^\s*(\d{1,4}|[ivxlcdm]{1,7})\s*$", re.IGNORECASE)
_PDF_HYPHEN_WRAP = re.compile(r"(\w)-\n(\w)")

# A wide run of spaces *inside* a line of text is the gutter between columns.
# Four is above the widest inter-word justification pdftotext emits and below
# the narrowest real gutter.
_PDF_GUTTER = re.compile(r"\S {4,}\S")

# Fraction of substantive lines that must show a gutter before the document is
# treated as multi-column. A single-column PDF scores near zero; a
# three-column government publication scores ~0.85.
_MULTICOLUMN_THRESHOLD = 0.35

# Short lines are headings, page furniture and list stubs; they pick up wide
# gaps by accident. Only lines long enough to span a column are evidence.
_MIN_GUTTER_LINE = 40
_GUTTER_SAMPLE = 4000


def looks_multicolumn(layout_text: str) -> bool:
    """Does ``pdftotext -layout`` output come from a multi-column document?

    ``-layout`` preserves horizontal position, which is what keeps table
    columns aligned — and is exactly what makes a multi-column page unusable:
    every emitted line spans all columns, so consecutive sentences from
    different columns interleave.

    This is a structural signal, not layout analysis: two runs of real text
    separated by a wide space run means two blocks sat side by side.
    """
    lines = [ln for ln in layout_text.splitlines()
             if len(ln.strip()) > _MIN_GUTTER_LINE]
    if not lines:
        return False
    sample = lines[:_GUTTER_SAMPLE]
    hits = sum(1 for ln in sample if _PDF_GUTTER.search(ln))
    return hits / len(sample) >= _MULTICOLUMN_THRESHOLD


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
                edge[nb[-1]] += 1
        boiler = {ln for ln, c in edge.items() if c > len(pages) / 2}
        kept = []
        for p in pages:
            lines = p.splitlines()
            nb_idx = [i for i, ln in enumerate(lines) if ln.strip()]
            first = nb_idx[0] if nb_idx else None
            last = nb_idx[-1] if nb_idx else None
            for i, ln in enumerate(lines):
                s = ln.strip()
                if s in boiler:
                    continue
                # Drop a bare page number only at a page edge (varies per page).
                if i in (first, last) and _PDF_PAGE_NUM.match(s):
                    continue
                kept.append(ln)
        text = "\n".join(kept)
    else:
        text = text.replace("\f", "\n")
    # ponytail: naive dehyphenation; may join a genuinely-hyphenated wrapped
    # compound ("well-\nknown" -> "wellknown"). Dictionary-aware split if it bites.
    return _PDF_HYPHEN_WRAP.sub(r"\1\2", text)


def _pdftotext(pdf_path: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["pdftotext", *args, pdf_path, "-"],
        capture_output=True, text=True, timeout=120,
        encoding="utf-8", errors="replace",
    )


def extract_with_pdftotext(pdf_path: str) -> str | None:
    """Extract a PDF, choosing ``-layout`` only when it will not scramble text.

    ``-layout`` is the right default for a single-column document: it keeps
    table columns aligned. On a multi-column document it destroys reading
    order, because each emitted line spans every column. Measured on IRS
    Publication 17 (142 pages, three columns), searching both outputs for the
    same phrase:

        -layout        'standard deduction or if you    (QOF). Taxpayers who made a'
        reading order  'Standard deduction amount increased. For 2025, the
                        standard deduction amount has been increased for all filers'

    The first is three columns welded together, and it is what every later
    step reads. ``-layout`` also pads each line to preserve position, which on
    that document produced 25,266,249 characters at 96.8% whitespace against
    957,757 in reading order — 26x larger for text that is also wrong.

    So: run ``-layout`` first (unchanged for the single-column majority), and
    only re-run without it when the output looks multi-column. The second
    subprocess is paid solely by documents that need it.
    """
    if not shutil.which("pdftotext"):
        return None
    try:
        pdf_path = os.path.abspath(pdf_path)
        result = _pdftotext(pdf_path, "-layout")
        if result.returncode != 0 or not result.stdout.strip():
            return None

        if looks_multicolumn(result.stdout):
            reading_order = _pdftotext(pdf_path)
            if reading_order.returncode == 0 and reading_order.stdout.strip():
                # ASCII only: this goes to stderr from the parser, which does
                # not get cli.py's UTF-8 reconfigure on a legacy Windows console.
                print("  [info] multi-column layout detected - using reading "
                      "order instead of -layout", file=sys.stderr)
                return clean_pdftotext(reading_order.stdout)
            # Falling back to -layout output is still better than nothing;
            # say so rather than silently returning scrambled text.
            print("  [warn] multi-column layout detected but the reading-order "
                  "pass failed; text may be interleaved", file=sys.stderr)

        return clean_pdftotext(result.stdout)
    except Exception as e:
        print(f"  [warn] extract_with_pdftotext failed: {type(e).__name__}: {e}", file=sys.stderr)
    return None


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
        return "\n".join(text_parts)
    except ImportError:
        return None
    except Exception as e:
        print(f"  [warn] extract_with_pypdf failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def extract_with_pdfminer(pdf_path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
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
