from __future__ import annotations

import os
import shutil
import subprocess
import sys


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
            return result.stdout
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


def extract_with_pdfplumber(pdf_path: str) -> str | None:
    """pdfplumber decodes many subsetted / non-Latin (e.g. Cyrillic) fonts that
    pdftotext and pypdf silently drop to punctuation. Slower, but correct."""
    try:
        import pdfplumber
        parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    parts.append("")
        return "\n".join(parts)
    except ImportError:
        return None
    except Exception as e:
        print(f"  [warn] extract_with_pdfplumber failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def alpha_ratio(text: str) -> float:
    """Fraction of alphabetic chars among non-whitespace chars. Real prose is
    letter-dominated (~0.5-0.95); a font-drop failure leaves mostly punctuation
    (~0.0-0.15)."""
    nonspace = [c for c in text if not c.isspace()]
    if not nonspace:
        return 0.0
    return sum(c.isalpha() for c in nonspace) / len(nonspace)


def looks_corrupt(text: str, threshold: float = 0.35) -> bool:
    """True when an extractor returned non-empty text that is punctuation-
    dominated — the classic pdftotext glyph-drop on subsetted fonts (a Cyrillic
    PDF reads as ', . , ,'). Calibrated on real garbage (~0.02-0.11) vs clean
    text (~0.51-0.96)."""
    return bool(text) and len(text.strip()) > 200 and alpha_ratio(text) < threshold


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
