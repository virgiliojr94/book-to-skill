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
