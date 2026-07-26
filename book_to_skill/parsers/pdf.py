from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections import Counter

_PDF_PAGE_NUM = re.compile(r"^\s*(\d{1,4}|[ivxlcdm]{1,7})\s*$", re.IGNORECASE)
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
