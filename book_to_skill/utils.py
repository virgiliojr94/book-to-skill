from __future__ import annotations

import glob
import json
import os
import re
import sys
import shutil
import zipfile
from pathlib import Path

from book_to_skill.exceptions import ExtractionError

from book_to_skill.config import (
    OUTPUT_DIR,
    OUTPUT_TEXT,
    OUTPUT_META,
    WORDS_PER_TOKEN,
    CJK_CHARS_PER_TOKEN,
    SUPPORTED_EXTENSIONS,
    TEXT_EXTENSIONS,
    HTML_EXTENSIONS,
    CALIBRE_EBOOK_EXTENSIONS,
    supported_formats_message,
)
from book_to_skill.dependencies import (
    normalize_install_mode,
    prepare_dependencies,
    run_dependency_check,
)
from book_to_skill.parsers.text import read_text_file
from book_to_skill.parsers.html import extract_html_file
from book_to_skill.parsers.docx import extract_docx
from book_to_skill.parsers.rtf import extract_rtf
from book_to_skill.parsers.calibre import extract_with_ebook_convert
from book_to_skill.parsers.pdf import (
    extract_with_docling,
    extract_with_pdftotext,
    extract_with_pypdf,
    extract_with_pdfminer,
    extract_with_ocr,
    looks_image_only,
    count_pages,
)
from book_to_skill.parsers.epub import (
    extract_with_ebooklib,
    extract_with_zipfile,
    count_epub_chapters,
)


# CJK codepoints: ideographs + extensions, kana, hangul, CJK punctuation, and
# fullwidth forms. These are not whitespace-delimited, so counting "words" on a
# Chinese/Japanese book collapses it to a handful of tokens; count them directly.
_CJK_RE = re.compile(
    r"[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff"
    r"\uac00-\ud7a3\uf900-\ufaff\uff00-\uffef]"
)


def estimate_tokens(text: str) -> int:
    """Estimate the token count of ``text`` with a deterministic heuristic.

    Latin / whitespace-delimited text is counted by words (``words /
    WORDS_PER_TOKEN`` — the project's long-standing ratio). CJK characters are
    counted directly against ``CJK_CHARS_PER_TOKEN`` because they carry little
    or no whitespace; without this a space-less Chinese/Japanese book estimates
    at a few tokens and the cost pre-flight under-reports by ~1000x. Kept
    dependency-free on purpose so the same book always yields the same number.
    """
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    if not cjk:
        return int(len(text.split()) / WORDS_PER_TOKEN)
    latin_words = len(_CJK_RE.sub(" ", text).split())
    return int(latin_words / WORDS_PER_TOKEN + cjk / CJK_CHARS_PER_TOKEN)


# Explicit chapter heading: "Chapter 5", "Capítulo 5: ...", "Chapter 1. Intro".
# Also French/German/Italian/Dutch chapter words (chapitre/kapitel/capitolo/
# hoofdstuk), matching the ToC languages added alongside. "ch.?" stays last so
# the longer words match in full. Captures the number (bounded to 1..99 — drops
# years like "2025.") and whatever follows it on the line, so we can reject prose.
_EXPLICIT_CHAPTER = re.compile(
    r"^\s*(?:chapter|chapitre|kapitel|cap[ií]tulo|capitolo|hoofdstuk|ch\.?)\s*(\d{1,2})\b(?P<rest>.*)$",
    re.IGNORECASE,
)
# A heading's number is followed by end-of-line, punctuation (“. : - —“), or a
# Capitalized title word. A lowercase continuation (“Chapter 6 explores...”,
# “Chapter 8 are relevant...”) is prose / a cross-reference, not a heading.
# The uppercase class is À-Þ so titles starting with Ü/Û (common in German, e.g. “Überblick”) are recognized.
_HEADING_TAIL = re.compile(r"^\s*$|^\s*[.:\-—–]|^\s+[A-ZÀ-Þ0-9\"“(]")

# Roman-numeral chapter heading: "I: Loomings", "II. The Carpet-Bag".
# Requires a separator (":" or ".") and a Capitalized title after it, so a bare
# "I" or "V." (a page divider / list marker) is not mistaken for a chapter.
_ROMAN_HEAD = re.compile(r"^\s*([IVXLCDM]+)\s*[:.]\s+[A-ZÀ-Þ\"“(]")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Chinese chapter headings. Two common styles:
#   1. explicit "第N章" / "第 3 回" / "第十二节" / "第一讲" — 第 + numeral + a
#      chapter classifier (章回卷节篇讲);
#   2. a Markdown heading led by a CJK ordinal and a separator, e.g.
#      "## 一 · 缘起" or "## 第一讲" — common in CJK ebooks and lecture notes.
# Scoped to CJK numerals, so Latin/Roman detection above is completely unaffected
# (e.g. "## 5 Setup" is still not treated as a heading here). detect_structure()
# dedupes by number, so a "##" heading and a repeated "###" sub-ordinal collapse
# to a single chapter.
_CN_NUM_VALUES = {
    "〇": 0, "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_CN_NUM_UNITS = {"十": 10, "百": 100, "千": 1000}
_CN_NUM_CLASS = "〇零一二两三四五六七八九十百千"
# Full-width Arabic digits (U+FF10–U+FF19) are common in Japanese typesetting,
# e.g. "第１章". int() already parses them (str.isdigit() is True), so only the
# regex character classes need to accept them.
_FW_DIGITS = "０-９"
_CN_CHAPTER = re.compile(rf"^\s*第\s*([0-9{_FW_DIGITS}{_CN_NUM_CLASS}]+)\s*[章回卷节篇讲]")
_MD_CN_HEADING = re.compile(rf"^#{{1,6}}\s+第?\s*([{_FW_DIGITS}{_CN_NUM_CLASS}]+)\s*[·、.:：章回卷节篇讲]")

# Table-of-contents header lines across common languages. Anchored to a whole
# line (^\s*X\s*$) so an inline "the contents of this chapter" never matches.
_TOC_HEADERS = (
    "table of contents", "contents", "índice", "sumário",   # EN / ES / PT
    "目录", "目錄", "目次",                                   # Chinese / Japanese
    "table des matières",                                   # French
    "inhaltsverzeichnis",                                   # German
    "indice", "sommario",                                   # Italian (no accent — distinct from índice above)
    "inhoudsopgave",                                        # Dutch
)
_TOC_PATTERN = re.compile(
    r"^\s*(?:" + "|".join(re.escape(h) for h in _TOC_HEADERS) + r")\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# ATX-style heading: "# Title", "## Section", AsciiDoc "= Title", "== Section".
# The required space after the marker distinguishes an AsciiDoc "== X" from a
# reStructuredText underline "=====" (no space) — the latter is intentionally
# ignored (RST underline headings are out of scope).
_ATX_HEADING = re.compile(r"^(#{1,6}|={1,6})\s+(.+?)\s*#*$")
# Setext/RST underline: a full line of "=" (level 1) or "-" (level 2), length
# >= 2. Marks the line directly above it as a heading title.
_SETEXT_UNDERLINE = re.compile(r"^(={2,}|-{2,})$")


def _structural_chapter_count(text: str) -> int:
    """Count chapter-like structural headings in Markdown/AsciiDoc/RST sources.

    Recognizes ATX headings ("# Title", "== Section") and setext/RST underline
    headings (a title line directly above a row of "=" or "-"). Groups distinct
    (case-normalized) titles by depth and returns the count at the shallowest
    depth with >= 2 distinct titles — this selects the real chapter level in the
    common "# Book Title / ## Chapter" layout where the top level appears once.

    Guards against false positives: headings inside fenced code blocks are
    skipped; an ATX title starting with a bare digit ("## 5 Setup") or made only
    of punctuation ("=====" table borders) is rejected; a setext underline counts
    only when it sits directly under a non-blank title line at least as long as
    the underline (so thematic breaks, table borders, and front-matter "---" do
    not match).
    """
    levels: dict[int, set[str]] = {}
    in_fence = False
    prev = ""  # previous non-fence line (stripped); a setext title candidate
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            prev = ""
            continue
        if in_fence:
            prev = ""
            continue
        # Setext/RST underline: "=" (level 1) or "-" (level 2) directly under a
        # title line at least as long as the underline.
        if (
            _SETEXT_UNDERLINE.match(s)
            and prev
            and not _SETEXT_UNDERLINE.match(prev)
            and len(s) >= len(prev)
        ):
            depth = 1 if s[0] == "=" else 2
            levels.setdefault(depth, set()).add(prev.lower())
            prev = ""
            continue
        # ATX heading ("# Title", "== Section").
        m = _ATX_HEADING.match(s)
        if m:
            title = m.group(2).strip().lower()
            # Reject empty, bare-digit-led ("## 5 Setup"), and all-punctuation
            # ("=====" table-border) titles — none are real chapter headings.
            if title and not title[0].isdigit() and re.search(r"\w", title):
                levels.setdefault(len(m.group(1)), set()).add(title)
            # An ATX heading line is not a setext title for the next line.
            prev = ""
            continue
        prev = s
    if not levels:
        return 0
    for depth in sorted(levels):
        if len(levels[depth]) >= 2:
            return len(levels[depth])
    # No level has >= 2 distinct headings: a thin doc (e.g. one heading per
    # level). Count them all — this path runs only as a fallback when numeric
    # chapter detection already found zero, so it cannot inflate real books.
    return sum(len(titles) for titles in levels.values())


def _cn_numeral_to_int(s: str) -> int | None:
    """Parse a Chinese (or ASCII-digit) chapter numeral into an int (1..999)."""
    if s.isdigit():
        n = int(s)
        return n if 1 <= n <= 999 else None
    section = current = 0
    for ch in s:
        if ch in _CN_NUM_VALUES:
            current = _CN_NUM_VALUES[ch]
        elif ch in _CN_NUM_UNITS:
            section += (current or 1) * _CN_NUM_UNITS[ch]
            current = 0
        else:
            return None
    total = section + current
    return total if 1 <= total <= 999 else None


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

    Handles Arabic ("Chapter 5", "Capítulo 5: ..."), Roman-numeral
    ("I: Loomings", "II. The Carpet-Bag") and Chinese ("第三章 …", "## 一 · …",
    "## 第一讲") heading styles.
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
    cm = _CN_CHAPTER.match(s) or _MD_CN_HEADING.match(s)
    if cm:
        return _cn_numeral_to_int(cm.group(1))
    return None


def detect_structure(text: str) -> dict:
    """Detect chapter count, table-of-contents presence, and chapter spans.

    Scans the whole text (not just the head) and counts DISTINCT chapter numbers
    from explicit "Chapter N"/"Capítulo N" headings, rejecting prose
    cross-references and numbered list items. Counting distinct numbers means a
    ToC entry and its body heading are not double-counted.

    Additionally emits ``chapters``: an ordered list of
    ``{number, title, line_start, line_end, char_start, char_end}`` spans for the
    *body* heading of each detected chapter, so the generation step can slice
    each chapter deterministically from ``full_text.txt`` (via a bounded Read or
    byte slice) instead of re-deriving offsets by hand. When a chapter number
    appears more than once — typically once in the table of contents and again
    as the body heading — the LAST occurrence wins, because the body heading
    almost always follows the ToC.
    """
    headings = []
    numbers = set()
    # number -> (title, char_start, line_start); last occurrence wins.
    last_by_number: dict[int, tuple[str, int, int]] = {}

    offset = 0
    for line_no, line in enumerate(text.splitlines(keepends=True), start=1):
        stripped = line.rstrip("\r\n")
        num = _chapter_number(stripped)
        if num is not None:
            title = stripped.strip()
            numbers.add(num)
            headings.append(title)
            last_by_number[num] = (title, offset, line_no)
        offset += len(line)

    numeric_count = len(numbers)
    # Fall back to structural (Markdown/AsciiDoc) headings only when no numeric
    # "Chapter N" headings were found, so books with real chapters are unaffected.
    chapters_detected = (
        numeric_count if numeric_count > 0 else _structural_chapter_count(text)
    )

    # Build ordered body-heading spans; fill each end from the next span's start.
    spans = [
        {"number": n, "title": t, "line_start": ln, "char_start": cs}
        for n, (t, cs, ln) in last_by_number.items()
    ]
    spans.sort(key=lambda s: s["char_start"])
    total_chars = len(text)
    total_lines = text.count("\n") + 1 if text else 0
    for i, span in enumerate(spans):
        if i + 1 < len(spans):
            span["char_end"] = spans[i + 1]["char_start"]
            span["line_end"] = spans[i + 1]["line_start"] - 1
        else:
            span["char_end"] = total_chars
            span["line_end"] = total_lines

    # Look for ToC indicators in the first ~30k chars (multilingual; see _TOC_PATTERN)
    has_toc = bool(_TOC_PATTERN.search(text[:30000]))

    return {
        "chapters_detected": chapters_detected,
        "chapter_headings_sample": headings[:10],
        "chapters": spans,
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


def extract_single_file(input_path: Path, extraction_mode: str, install_mode: str, ocr_enabled: bool = False) -> dict:
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
                print("Trying pypdf...", end=" ", flush=True)
                text = extract_with_pypdf(input_str)
                if text:
                    method = "pypdf"
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
                            "Install one of: poppler-utils (pdftotext), pypdf, or pdfminer.six\n"
                            "  sudo apt install poppler-utils\n"
                            "  pip3 install pypdf\n"
                            "  pip3 install pdfminer.six"
                        )

                        
        pages = count_pages(input_str)
        pages_label = "pages"
        # Image-only / scanned-PDF guard. Some extractors return only whitespace
        # for a scanned page, so the chain above "succeeds" with no real text and
        # the failure is silent. Detect that and either OCR (opt-in) or fail with
        # an actionable message instead of emitting an empty skill.
        if (not text or not text.strip()) or looks_image_only(text, pages):
            if ocr_enabled:
                print("PDF text layer is empty/sparse — running OCR (this can take a while)...", flush=True)
                ocr_text = extract_with_ocr(input_str)
                if ocr_text and ocr_text.strip():
                    text = ocr_text
                    method = "ocr"
                else:
                    raise ExtractionError(
                        f"OCR produced no text for '{input_path.name}'. Install an OCR tool "
                        "(ocrmypdf + poppler-utils, or docling) and retry."
                    )
            else:
                raise ExtractionError(
                    f"'{input_path.name}' looks image-only/scanned: {pages} page(s) but only "
                    f"~{len((text or '').strip())} extractable characters. Re-run with --ocr "
                    "to OCR it (needs ocrmypdf + poppler-utils, or docling)."
                )
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


def _banner_enabled() -> bool:
    """Whether to print the decorative attribution banner.

    The banner is written to stderr, which a calling agent captures into its
    context — so for non-interactive (agent / pipeline) runs it is pure noise,
    ironic for a tool whose whole pitch is token frugality. Show it only when
    stderr is an interactive TTY, or when explicitly forced with ``--banner`` /
    ``BOOK_SKILL_BANNER=1``. Suppress with ``--no-banner`` / ``BOOK_SKILL_BANNER=0``.
    """
    argv = sys.argv[1:]
    env = os.environ.get("BOOK_SKILL_BANNER", "").strip().lower()
    if "--no-banner" in argv or env in {"0", "false", "no", "off"}:
        return False
    if "--banner" in argv or env in {"1", "true", "yes", "on"}:
        return True
    try:
        return sys.stderr.isatty()
    except Exception:
        return False


def print_banner() -> None:
    """Print the attribution banner (gated by _banner_enabled)."""
    banner = Path(__file__).resolve().parent.parent / "scripts" / "banner.txt"
    try:
        sys.stderr.write(banner.read_text(encoding="utf-8") + "\n")
    except Exception:
        pass  # best-effort: never block extraction on the banner


def main():
    if _banner_enabled():
        print_banner()

    if "--check" in sys.argv[1:]:
        sys.exit(run_dependency_check())

    if len(sys.argv) < 2:
        print("Usage: extract.py <path-to-document-folder-or-glob>... [--mode technical|text] [--install-missing ask|yes|no]", file=sys.stderr)
        print("       extract.py --check    # report which extractors are installed", file=sys.stderr)
        print(f"Supported formats: {supported_formats_message()}", file=sys.stderr)
        sys.exit(1)
        
    raw_input_paths, extraction_mode, install_mode = parse_arguments(sys.argv)

    ocr_enabled = ("--ocr" in sys.argv[1:]) or os.environ.get(
        "BOOK_SKILL_OCR", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    
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
            res = extract_single_file(file_path, extraction_mode, install_mode, ocr_enabled)
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
