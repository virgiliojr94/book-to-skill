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
            capture_output=True, text=True, timeout=120
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


def looks_image_only(text: str, pages: int) -> bool:
    """Heuristic: a multi-page PDF that yields almost no extractable text is
    probably scanned / image-only and needs OCR.

    Conservative on purpose (>=2 pages and < ~25 real characters per page) so a
    genuinely text-light PDF is not misflagged. A scanned book yields ~0
    extractable characters, so this catches the silent-failure case without
    tripping on legitimate sparse layouts.
    """
    if pages and pages >= 2:
        return len((text or "").strip()) < 25 * pages
    return False


def extract_with_ocr(pdf_path: str) -> str | None:
    """OCR an image-only / scanned PDF.

    Tries ocrmypdf first (fast, produces a searchable PDF that pdftotext can
    then read), then falls back to Docling with OCR enabled. Both are optional;
    if neither is available this returns None and the caller reports a clear
    "install an OCR tool" error. OCR is opt-in (``--ocr`` / ``BOOK_SKILL_OCR=1``)
    because it is slow and heavy.
    """
    # 1) ocrmypdf -> searchable PDF -> pdftotext
    if shutil.which("ocrmypdf") and shutil.which("pdftotext"):
        import tempfile
        out_pdf = None
        try:
            pdf_path = os.path.abspath(pdf_path)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                out_pdf = tmp.name
            result = subprocess.run(
                ["ocrmypdf", "--force-ocr", "--quiet", pdf_path, out_pdf],
                capture_output=True, text=True, timeout=1800,
            )
            if result.returncode == 0:
                text = extract_with_pdftotext(out_pdf)
                if text and text.strip():
                    return text
        except Exception as e:
            print(f"  [warn] extract_with_ocr (ocrmypdf) failed: {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            if out_pdf:
                try:
                    os.unlink(out_pdf)
                except OSError:
                    pass

    # 2) Docling with OCR enabled
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        result = converter.convert(pdf_path)
        text = result.document.export_to_markdown()
        return text or None
    except ImportError:
        return None
    except Exception as e:
        print(f"  [warn] extract_with_ocr (docling) failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None
