from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any

_MIN_NATIVE_CONFIDENCE = 0.90
_INSPECTIONS: dict[str, dict[str, Any]] = {}


def _normalise_pdf_type(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    # Handles both Python binding strings ("text_based") and enum-ish values
    # such as "PdfType.TextBased" without depending on one library revision.
    text = text.split(".")[-1]
    out = []
    for index, char in enumerate(text):
        if index and char.isupper() and text[index - 1].islower():
            out.append("_")
        out.append(char.lower())
    return "".join(out).replace("-", "_")


def _package_version() -> str | None:
    try:
        return importlib.metadata.version("pdf-inspector")
    except importlib.metadata.PackageNotFoundError:
        return None


def _ocr_reasons(entries: Any) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for entry in entries or []:
        page = getattr(entry, "page", None)
        reasons = list(getattr(entry, "reasons", None) or [])
        normalised.append({"page": page, "reasons": reasons})
    return normalised


def inspect_pdf(path: str | Path) -> tuple[str | None, dict[str, Any] | None]:
    """Inspect a PDF with Firecrawl pdf-inspector when it is installed.

    The returned Markdown is intentionally conservative: it is only considered
    usable when pdf-inspector classifies the document as native text, reports no
    OCR-routed pages or encoding problems, and gives a high confidence score.
    All other cases return metadata only so the existing Book-to-Skill fallback
    chain remains authoritative.
    """
    try:
        import pdf_inspector
    except ImportError:
        return None, None

    try:
        result = pdf_inspector.process_pdf(str(path))
    except Exception as exc:
        print(
            f"  [warn] pdf-inspector preflight failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None, None

    pdf_type = _normalise_pdf_type(getattr(result, "pdf_type", None))
    confidence = float(getattr(result, "confidence", 0.0) or 0.0)
    pages_needing_ocr = list(getattr(result, "pages_needing_ocr", None) or [])
    has_encoding_issues = bool(getattr(result, "has_encoding_issues", False))
    markdown = getattr(result, "markdown", None)

    native_markdown_trusted = bool(
        isinstance(markdown, str)
        and markdown.strip()
        and pdf_type == "text_based"
        and confidence >= _MIN_NATIVE_CONFIDENCE
        and not pages_needing_ocr
        and not has_encoding_issues
    )

    metadata: dict[str, Any] = {
        "engine": "pdf-inspector",
        "version": _package_version(),
        "pdf_type": pdf_type,
        "confidence": round(confidence, 4),
        "native_markdown_trusted": native_markdown_trusted,
        "pages_needing_ocr": pages_needing_ocr,
        "ocr_reasons_by_page": _ocr_reasons(
            getattr(result, "ocr_reasons_by_page", None)
        ),
        "pages_with_tables": list(getattr(result, "pages_with_tables", None) or []),
        "pages_with_columns": list(getattr(result, "pages_with_columns", None) or []),
        "has_encoding_issues": has_encoding_issues,
        "is_complex_layout": bool(getattr(result, "is_complex_layout", False)),
        "page_count": int(getattr(result, "page_count", 0) or 0),
    }
    return (markdown if native_markdown_trusted else None), metadata


def _looks_like_pdf(path: Path) -> bool:
    if path.suffix.lower() == ".pdf":
        return True
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"%PDF"
    except OSError:
        return False


def _result_from_inspector(
    utils_module: Any,
    input_path: Path,
    markdown: str,
    inspection: dict[str, Any],
) -> dict[str, Any] | None:
    text, removed_invisible = utils_module.sanitize_extracted_text(markdown)
    if removed_invisible:
        print(
            f"  [security] removed {removed_invisible} invisible Unicode "
            f"code point(s) from {input_path.name}",
            file=sys.stderr,
        )
    if not text.strip():
        return None

    confidence = inspection.get("confidence", 0.0)
    print(
        f"Mode: text — using pdf-inspector "
        f"(native text, confidence {confidence:.2f})... OK"
    )

    structure = utils_module.detect_structure(text)
    print(
        f"  chapters: {structure['chapters_detected']} "
        f"({structure['chapters_method']})"
    )

    pages = inspection.get("page_count") or utils_module.count_pages(str(input_path))
    tokens = utils_module.estimate_tokens(text)
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

    return {
        "source_file": str(input_path.resolve()),
        "filename": input_path.name,
        "format": "pdf",
        "extraction_method": "pdf-inspector",
        "file_size_mb": round(file_size_mb, 2),
        "pages": pages,
        "pages_label": "pages",
        "chars": len(text),
        "words": len(text.split()),
        "estimated_tokens": tokens,
        "images_dropped": None,
        "text": text,
        **structure,
    }


def _fallback_reason(inspection: dict[str, Any]) -> str:
    if inspection.get("pdf_type") != "text_based":
        return f"classified as {inspection.get('pdf_type', 'unknown')}"
    if inspection.get("has_encoding_issues"):
        return "encoding issues detected"
    if inspection.get("pages_needing_ocr"):
        pages = ", ".join(str(p) for p in inspection["pages_needing_ocr"][:8])
        suffix = "..." if len(inspection["pages_needing_ocr"]) > 8 else ""
        return f"OCR recommended for page(s) {pages}{suffix}"
    if float(inspection.get("confidence", 0.0) or 0.0) < _MIN_NATIVE_CONFIDENCE:
        return f"confidence below {_MIN_NATIVE_CONFIDENCE:.2f}"
    return "native Markdown was not trustworthy"


def install_pdf_inspector_hook(utils_module: Any | None = None) -> None:
    """Wrap ``extract_single_file`` without changing the legacy extractor.

    Text-mode PDFs can take the fast native Markdown path when pdf-inspector says
    it is safe. Technical PDFs and uncertain documents continue through the
    existing Docling/pdftotext/pypdf/pdfminer implementation unchanged.
    """
    if utils_module is None:
        from book_to_skill import utils as utils_module

    original = utils_module.extract_single_file
    if getattr(original, "_book_to_skill_pdf_inspector_hook", False):
        return

    def wrapped(input_path: Path, extraction_mode: str, install_mode: str) -> dict[str, Any]:
        if not _looks_like_pdf(input_path):
            return original(input_path, extraction_mode, install_mode)

        markdown, inspection = inspect_pdf(input_path)
        if inspection is not None:
            _INSPECTIONS[str(input_path.resolve())] = inspection

        if extraction_mode == "text" and markdown and inspection:
            result = _result_from_inspector(utils_module, input_path, markdown, inspection)
            if result is not None:
                return result

        if inspection is not None:
            print(
                f"pdf-inspector: {_fallback_reason(inspection)}; "
                "using the existing extraction chain.",
                file=sys.stderr,
            )
        return original(input_path, extraction_mode, install_mode)

    wrapped._book_to_skill_pdf_inspector_hook = True  # type: ignore[attr-defined]
    wrapped._book_to_skill_original = original  # type: ignore[attr-defined]
    utils_module.extract_single_file = wrapped


def enrich_pdf_inspector_metadata(metadata_path: str | Path | None = None) -> None:
    """Persist inspection/provenance into the run's existing ``metadata.json``."""
    if not _INSPECTIONS:
        return

    if metadata_path is None:
        from book_to_skill.config import OUTPUT_META

        metadata_path = OUTPUT_META

    path = Path(metadata_path)
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  [warn] could not enrich PDF metadata: {exc}", file=sys.stderr)
        return

    matched = 0
    for source in payload.get("sources", []):
        source_file = source.get("source_file")
        if not source_file:
            continue
        inspection = _INSPECTIONS.get(str(Path(source_file).resolve()))
        if inspection is None:
            continue
        source["pdf_inspector"] = inspection
        matched += 1

    if matched == 1 and payload.get("total_sources") == 1:
        only_source = payload.get("sources", [{}])[0]
        if "pdf_inspector" in only_source:
            payload["pdf_inspector"] = only_source["pdf_inspector"]

    if not matched:
        return

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _reset_state_for_tests() -> None:
    _INSPECTIONS.clear()
