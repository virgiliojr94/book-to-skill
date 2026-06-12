import glob
import json
import os
import re
import sys
import shutil
import zipfile
from pathlib import Path

from extractor.exceptions import ExtractionError

from extractor.config import (
    OUTPUT_DIR,
    OUTPUT_TEXT,
    OUTPUT_META,
    WORDS_PER_TOKEN,
    SUPPORTED_EXTENSIONS,
    TEXT_EXTENSIONS,
    HTML_EXTENSIONS,
    CALIBRE_EBOOK_EXTENSIONS,
    supported_formats_message,
)
from extractor.dependencies import (
    normalize_install_mode,
    prepare_dependencies,
    run_dependency_check,
)
from extractor.parsers.text import read_text_file
from extractor.parsers.html import extract_html_file
from extractor.parsers.docx import extract_docx
from extractor.parsers.rtf import extract_rtf
from extractor.parsers.calibre import extract_with_ebook_convert
from extractor.parsers.pdf import (
    extract_with_docling,
    extract_with_pdftotext,
    extract_with_pypdf2,
    extract_with_pdfminer,
    count_pages,
)
from extractor.parsers.epub import (
    extract_with_ebooklib,
    extract_with_zipfile,
    count_epub_chapters,
)


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) / WORDS_PER_TOKEN)


# Explicit chapter heading: "Chapter 5", "Capítulo 5: ...", "Chapter 1. Intro".
# Captures the number (bounded to 1..99 — drops years like "2025.") and whatever
# follows it on the line, so we can reject prose.
_EXPLICIT_CHAPTER = re.compile(
    r"^\s*(?:chapter|cap[ií]tulo|ch\.?)\s*(\d{1,2})\b(?P<rest>.*)$", re.IGNORECASE
)
# A heading's number is followed by end-of-line, punctuation (". : - —"), or a
# Capitalized title word. A lowercase continuation ("Chapter 6 explores...",
# "Chapter 8 are relevant...") is prose / a cross-reference, not a heading.
_HEADING_TAIL = re.compile(r"^\s*$|^\s*[.:\-—–]|^\s+[A-ZÀ-Ú0-9\"“(]")

# Roman-numeral chapter heading: "I: Loomings", "II. The Carpet-Bag".
# Requires a separator (":" or ".") and a Capitalized title after it, so a bare
# "I" or "V." (a page divider / list marker) is not mistaken for a chapter.
_ROMAN_HEAD = re.compile(r"^\s*([IVXLCDM]+)\s*[:.]\s+[A-ZÀ-Ú\"“(]")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _int_to_roman(n: int) -> str:
    table = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
             (5, "V"), (4, "IV"), (1, "I")]
    out = []
    for val, sym in table:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def _roman_to_int(s: str) -> int | None:
    """Convert a Roman numeral to int, returning None if it isn't canonical."""
    s = s.upper()
    total = prev = 0
    for ch in reversed(s):
        v = _ROMAN_VALUES.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    if total == 0 or total > 200:
        return None
    # Reject non-canonical forms ("IIII", "VV") by round-tripping.
    return total if _int_to_roman(total) == s else None


def _chapter_number(line: str) -> int | None:
    """Return the chapter number if the line is a genuine chapter heading.

    Handles both Arabic ("Chapter 5", "Capítulo 5: ...") and Roman-numeral
    ("I: Loomings", "II. The Carpet-Bag") heading styles.
    """
    s = line.strip()
    if len(s) > 80:
        return None
    m = _EXPLICIT_CHAPTER.match(s)
    if m and _HEADING_TAIL.match(m.group("rest")):
        return int(m.group(1))
    rm = _ROMAN_HEAD.match(s)
    if rm:
        return _roman_to_int(rm.group(1))
    return None


def detect_structure(text: str) -> dict:
    """Detect chapter count and table of contents presence.

    Scans the whole text (not just the head) and counts DISTINCT chapter numbers
    from explicit "Chapter N"/"Capítulo N" headings, rejecting prose
    cross-references and numbered list items. Counting distinct numbers means a
    ToC entry and its body heading are not double-counted.
    """
    lines = text.splitlines()

    headings = []
    numbers = set()
    for line in lines:
        num = _chapter_number(line)
        if num is not None:
            numbers.add(num)
            headings.append(line.strip())
    chapters_detected = len(numbers)

    # Look for ToC indicators in the first ~30k chars
    toc_pattern = re.compile(
        r"^\s*(?:table of contents|contents|índice|sumário)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    has_toc = bool(toc_pattern.search(text[:30000]))

    return {
        "chapters_detected": chapters_detected,
        "chapter_headings_sample": headings[:10],
        "has_toc": has_toc,
    }


def parse_arguments(argv: list[str]) -> tuple[list[str], str, str]:
    """Parse argv into (input_paths, extraction_mode, install_mode)."""
    input_paths = []
    extraction_mode = "text"
    
    args = argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--mode":
            if i + 1 < len(args):
                extraction_mode = args[i+1].lower()
                i += 2
            else:
                i += 1
        elif arg == "--install-missing":
            if i + 1 < len(args) and not args[i+1].startswith("--"):
                i += 2
            else:
                i += 1
        elif arg == "--no-install-missing":
            i += 1
        elif arg.startswith("-"):
            i += 1
        else:
            input_paths.append(arg)
            i += 1
            
    install_mode = normalize_install_mode(argv)
    if extraction_mode not in ("technical", "text"):
        extraction_mode = "text"
        
    return input_paths, extraction_mode, install_mode


def resolve_input_files(paths: list[str]) -> list[Path]:
    """Resolve paths including files, directories, and glob patterns to Path objects.

    User-given order is preserved for explicit file arguments.  Expanded
    results (directories, globs) are sorted deterministically so repeated
    runs produce the same output.
    """
    resolved = []
    for path_str in paths:
        # Check if it has glob wildcards
        if any(char in path_str for char in ("*", "?", "[")):
            glob_matches = glob.glob(path_str, recursive=True)
            # Sort expanded glob results deterministically
            expanded = []
            for match in glob_matches:
                p = Path(match)
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    expanded.append(p.resolve())
            expanded.sort(key=lambda x: str(x).lower())
            resolved.extend(expanded)
        else:
            p = Path(path_str)
            if p.is_dir():
                # Sort expanded directory results deterministically
                dir_files = []
                for root, _, files in os.walk(p):
                    for file in files:
                        file_path = Path(root) / file
                        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                            dir_files.append(file_path.resolve())
                dir_files.sort(key=lambda x: str(x).lower())
                resolved.extend(dir_files)
            else:
                # Keep even if it doesn't exist so the error check can report it
                resolved.append(p.resolve())

    # Deduplicate while preserving insertion order (user order for explicit files)
    seen = set()
    unique_paths = []
    for path in resolved:
        resolved_path = path.resolve() if path.exists() else path
        if resolved_path not in seen:
            seen.add(resolved_path)
            unique_paths.append(resolved_path)

    return unique_paths


def extract_single_file(input_path: Path, extraction_mode: str, install_mode: str) -> dict:
    """Extract text and metadata from a single file path."""
    input_str = str(input_path)
    
    if not input_path.exists():
        raise ExtractionError(f"File not found: {input_str}")
        
    ext = input_path.suffix.lower()
    document_format = ext.lstrip(".")
    
    # Sniff magic bytes if suffix is not supported
    if ext not in SUPPORTED_EXTENSIONS:
        with open(input_str, "rb") as f:
            header = f.read(8)
        if header[:4] == b"%PDF":
            ext = ".pdf"
            document_format = "pdf"
        elif header[:2] == b"PK":
            try:
                with zipfile.ZipFile(input_str) as zf:
                    names = set(zf.namelist())
                    if "mimetype" in names and zf.read("mimetype").startswith(b"application/epub"):
                        ext = ".epub"
                        document_format = "epub"
                    elif "word/document.xml" in names:
                        ext = ".docx"
                        document_format = "docx"
                    else:
                        raise ExtractionError(
                            f"Unsupported ZIP-based format '{input_path.name}'. Supported: {supported_formats_message()}"
                        )
            except (zipfile.BadZipFile, KeyError, OSError):
                raise ExtractionError(
                    f"Unsupported ZIP-based format '{input_path.name}'. Supported: {supported_formats_message()}"
                )
        else:
            raise ExtractionError(
                f"Unsupported format '{ext or '<none>'}'. Supported: {supported_formats_message()}"
            )
            
    prepare_dependencies(ext, extraction_mode, install_mode)
    
    if ext in CALIBRE_EBOOK_EXTENSIONS and not shutil.which("ebook-convert"):
        raise ExtractionError(
            "MOBI/AZW/AZW3 extraction requires Calibre's ebook-convert command. "
            "Install Calibre and ensure ebook-convert is on PATH, then rerun this command."
        )
        
    text = ""
    method = ""
    pages = 0
    pages_label = "sections"
    
    if ext == ".epub":
        print(f"Extracting EPUB: {input_str}")
        text = extract_with_ebooklib(input_str)
        if text and text.strip():
            method = "ebooklib"
        else:
            print("ebooklib not available")
            print("Trying stdlib zipfile parser...", end=" ", flush=True)
            text = extract_with_zipfile(input_str)
            if text and text.strip():
                print("OK")
                method = "zipfile"
            else:
                print("FAILED")
                raise ExtractionError(
                    "Could not extract text from EPUB.\n"
                    "Install ebooklib + beautifulsoup4 for best results:\n"
                    "  pip3 install ebooklib beautifulsoup4"
                )
        pages = count_epub_chapters(input_str)
        pages_label = "spine_items"
    elif ext == ".pdf":
        print(f"Extracting PDF: {input_str}")
        if extraction_mode == "technical":
            print("Mode: technical — using Docling (layout-aware)...", end=" ", flush=True)
            text = extract_with_docling(input_str)
            if text:
                method = "docling"
                print("OK")
            else:
                print("not available, falling back to pdftotext")
                extraction_mode = "text"
                
        if extraction_mode == "text" or not text:
            print("Mode: text — using pdftotext...")
            print("Trying pdftotext...", end=" ", flush=True)
            text = extract_with_pdftotext(input_str)
            
            if text:
                method = "pdftotext"
                print("OK")
            else:
                print("not available")
                print("Trying PyPDF2...", end=" ", flush=True)
                text = extract_with_pypdf2(input_str)
                if text:
                    method = "PyPDF2"
                    print("OK")
                else:
                    print("not available")
                    print("Trying pdfminer.six...", end=" ", flush=True)
                    text = extract_with_pdfminer(input_str)
                    if text:
                        method = "pdfminer"
                        print("OK")
                    else:
                        print("FAILED")
                        raise ExtractionError(
                            "Could not extract text from PDF.\n"
                            "Install one of: poppler-utils (pdftotext), PyPDF2, or pdfminer.six\n"
                            "  sudo apt install poppler-utils\n"
                            "  pip3 install PyPDF2\n"
                            "  pip3 install pdfminer.six"
                        )
                        
        pages = count_pages(input_str)
        pages_label = "pages"
    elif ext in TEXT_EXTENSIONS:
        print(f"Extracting text document: {input_str}")
        text = read_text_file(input_str)
        if text is None or not text.strip():
            raise ExtractionError(f"Could not read text document: {input_path.name}")
        method = "plain-text"
        pages = 0
        pages_label = "sections"
    elif ext in HTML_EXTENSIONS:
        print(f"Extracting HTML: {input_str}")
        text = extract_html_file(input_str)
        if text is None or not text.strip():
            raise ExtractionError(f"Could not extract text from HTML: {input_path.name}")
        method = "html-parser"
        pages = 0
        pages_label = "sections"
    elif ext == ".docx":
        print(f"Extracting DOCX: {input_str}")
        text, method = extract_docx(input_str)
        pages = 0
        pages_label = "sections"
    elif ext == ".rtf":
        print(f"Extracting RTF: {input_str}")
        text, method = extract_rtf(input_str)
        pages = 0
        pages_label = "sections"
    elif ext in CALIBRE_EBOOK_EXTENSIONS:
        print(f"Extracting ebook with Calibre: {input_str}")
        text = extract_with_ebook_convert(input_str)
        if text is None or not text.strip():
            raise ExtractionError(
                f"Could not extract text from {ext}. Install Calibre and ensure ebook-convert is on PATH."
            )
        method = "ebook-convert"
        pages = 0
        pages_label = "sections"
        
    tokens = estimate_tokens(text)
    structure = detect_structure(text)
    file_size_mb = os.path.getsize(input_str) / (1024 * 1024)
    
    return {
        "source_file": str(input_path.resolve()),
        "filename": input_path.name,
        "format": document_format,
        "extraction_method": method,
        "file_size_mb": round(file_size_mb, 2),
        pages_label: pages,
        "pages_label": pages_label,
        "pages": pages,
        "chars": len(text),
        "words": len(text.split()),
        "estimated_tokens": tokens,
        "text": text,
        **structure,
    }


def print_banner() -> None:
    """Print the attribution banner. Done here (not only in SKILL.md) so it
    shows on every run regardless of how the agent invokes extraction."""
    banner = Path(__file__).resolve().parent.parent / "banner.txt"
    try:
        sys.stderr.write(banner.read_text(encoding="utf-8") + "\n")
    except Exception:
        pass  # best-effort: never block extraction on the banner


def main():
    print_banner()

    if "--check" in sys.argv[1:]:
        sys.exit(run_dependency_check())

    if len(sys.argv) < 2:
        print("Usage: extract.py <path-to-document-folder-or-glob>... [--mode technical|text] [--install-missing ask|yes|no]", file=sys.stderr)
        print("       extract.py --check    # report which extractors are installed", file=sys.stderr)
        print(f"Supported formats: {supported_formats_message()}", file=sys.stderr)
        sys.exit(1)
        
    raw_input_paths, extraction_mode, install_mode = parse_arguments(sys.argv)
    
    if not raw_input_paths:
        print("ERROR: No input document, folder, or glob pattern specified.", file=sys.stderr)
        sys.exit(1)
        
    input_files = resolve_input_files(raw_input_paths)
    
    if not input_files:
        print(f"ERROR: No supported files found matching: {', '.join(raw_input_paths)}", file=sys.stderr)
        sys.exit(1)
        
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    extracted_sources = []
    combined_texts = []
    errors = []
    
    for file_path in input_files:
        try:
            res = extract_single_file(file_path, extraction_mode, install_mode)
        except ExtractionError as exc:
            print(f"WARNING: Skipping {file_path.name}: {exc}", file=sys.stderr)
            errors.append((file_path, str(exc)))
            continue
        extracted_sources.append(res)
        
        # Format the text with a clear boundary
        separator = f"\n\n{'=' * 80}\nSOURCE: {res['filename']} (Path: {res['source_file']})\n{'=' * 80}\n\n"
        combined_texts.append(separator + res["text"])
    
    if not extracted_sources:
        print(f"\nERROR: All {len(errors)} source(s) failed extraction:", file=sys.stderr)
        for path, err in errors:
            print(f"  - {path.name}: {err}", file=sys.stderr)
        sys.exit(1)
        
    # Combine texts
    consolidated_text = "".join(combined_texts).strip()
    
    # Write combined text
    OUTPUT_TEXT.write_text(consolidated_text, encoding="utf-8")
    
    # Consolidate metadata
    total_file_size_mb = sum(src["file_size_mb"] for src in extracted_sources)
    total_pages = sum(src["pages"] for src in extracted_sources)
    total_chars = len(consolidated_text)
    total_words = len(consolidated_text.split())
    total_tokens = estimate_tokens(consolidated_text)
    
    # Detect structure on consolidated text
    consolidated_structure = detect_structure(consolidated_text)
    
    metadata = {
        "source_file": "Consolidated from multiple sources" if len(extracted_sources) > 1 else extracted_sources[0]["source_file"],
        "filename": "multi-source" if len(extracted_sources) > 1 else extracted_sources[0]["filename"],
        "format": "mixed" if len(extracted_sources) > 1 else extracted_sources[0]["format"],
        "extraction_method": "multi-method" if len(extracted_sources) > 1 else extracted_sources[0]["extraction_method"],
        "extraction_mode": extraction_mode,
        "file_size_mb": round(total_file_size_mb, 2),
        "pages": total_pages,
        "chars": total_chars,
        "words": total_words,
        "estimated_tokens": total_tokens,
        "estimated_tokens_human": f"~{total_tokens // 1000}K",
        "output_text": str(OUTPUT_TEXT),
        "total_sources": len(extracted_sources),
        "sources": [
            {
                "source_file": src["source_file"],
                "filename": src["filename"],
                "format": src["format"],
                "extraction_method": src["extraction_method"],
                "file_size_mb": src["file_size_mb"],
                "pages": src["pages"],
                "pages_label": src["pages_label"],
                "chars": src["chars"],
                "words": src["words"],
                "estimated_tokens": src["estimated_tokens"],
                "chapters_detected": src["chapters_detected"],
                "has_toc": src["has_toc"]
            }
            for src in extracted_sources
        ],
        **consolidated_structure,
    }
    
    OUTPUT_META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    page_line = f"   Total Pages: {total_pages}"
    print("\nExtraction complete:")
    print(f"   Sources : {len(extracted_sources)} processed")
    print(f"   Size    : {total_file_size_mb:.2f} MB")
    print(page_line)
    print(f"   Words   : {total_words:,}")
    print(f"   Tokens  : ~{total_tokens // 1000}K")
    print(f"   Chapters: {consolidated_structure['chapters_detected']} detected overall")
    print(f"   ToC     : {'yes' if consolidated_structure['has_toc'] else 'not detected'}")
    if not consolidated_structure["has_toc"]:
        print(
            "   WARN    : No table of contents detected — chapter mapping in Step 3 "
            "will rely on heading scan only, which may miss or duplicate sections."
        )
    print(f"\n   Text -> {OUTPUT_TEXT}")
    print(f"   Meta -> {OUTPUT_META}")
    if errors:
        print(f"\n   WARNING: {len(errors)} source(s) skipped due to errors:")
        for path, err in errors:
            print(f"     - {path.name}: {err}")
