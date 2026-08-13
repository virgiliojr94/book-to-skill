from __future__ import annotations

import glob
import json
import os
import re
import statistics
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
    looks_image_only,
    count_pages,
)
from book_to_skill.parsers.epub import (
    extract_with_ebooklib,
    extract_with_zipfile,
    count_epub_chapters,
)
from book_to_skill.sanitize import sanitize_extracted_text


# CJK codepoints: ideographs + extensions, kana, hangul, CJK punctuation, and
# fullwidth forms. These are not whitespace-delimited, so counting "words" on a
# Chinese/Japanese book collapses it to a handful of tokens; count them directly.
#
# The last range is Planes 2 and 3 (U+20000-U+3FFFF), the ideographic
# supplementary planes, taken end to end rather than enumerated block by block
# so a future extension does not silently fall through the way Extension H
# (U+31350-U+323AF) did. Nothing non-ideographic lives up here: emoji,
# mathematical alphanumerics and regional indicators are all in Plane 1, which
# this range does not touch. Classical Chinese, Cantonese, Hong Kong and
# Taiwan place/personal names, and Japanese 人名用漢字 all draw on it. Without it
# those characters fell through to the whitespace-word branch, where a
# space-less run of them counts as a single "word": the same ~1000x undercount
# #103 fixed for the BMP, one plane up.
_CJK_RE = re.compile(
    r"[　-〿぀-ヿ㐀-䶿一-鿿"
    r"가-힣豈-﫿＀-￯"
    r"\U00020000-\U0003FFFF]"
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
    r"^\s*(?:chapter|chapitre|kapitel|cap[ií]tulo|capitolo|hoofdstuk|ch\.?)\s*(?:(\d{1,2})|(?P<roman>[IVXLCDMivxlcdm]{1,7}))\b(?P<rest>.*)$",
    re.IGNORECASE,
)
# A heading's number is followed by end-of-line, punctuation (“. : - —“), or a
# Capitalized title word. A lowercase continuation (“Chapter 6 explores...”,
# “Chapter 8 are relevant...”) is prose / a cross-reference, not a heading.
# The uppercase class is À-Þ so titles starting with Ü/Û (common in German, e.g. “Überblick”) are recognized.
_HEADING_TAIL = re.compile(r"^\s*$|^\s*[.:\-—–]|^\s+[A-ZÀ-Þ0-9\"“(]")

# Roman-numeral chapter heading: "I: Loomings", "II. The Carpet-Bag".
# Uppercase alone at line start is safe — no common English word is a valid
# uppercase Roman numeral.  Lowercase ("i: Loomings") is only accepted inside
# a markdown heading ("## i. introduction") to avoid false positives from
# words that happen to be valid Roman numerals ("vi: the editor" → 6).
_ROMAN_HEAD = re.compile(r"^\s*([IVXLCDM]+)\s*[:.]\s+[A-ZÀ-Þ0-9\"“(]")
_LC_MD_ROMAN = re.compile(r"^\s*#{1,6}\s+([ivxlcdm]+)\s*[:.]\s+[A-Za-zÀ-Þ\"“(]")
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Optional Markdown / AsciiDoc heading prefix ("## Chapter 1", "== Section").
# Stripped in _chapter_number() as a second pass so the CJK/Thai/Korean
# matchers (which already tolerate the prefix inline) are untouched. (Issue #91)
_MD_HEADING_PREFIX = re.compile(r"^(#{1,6}|={1,6})\s+")

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

# Thai chapter headings: "บทที่ 3", "บทที่ ๑๒", "ตอนที่ ๘๗", "ภาคที่ 2".
# Thai digits (U+0E50-U+0E59) are positional like Arabic — unlike the Chinese
# numerals above they need no unit composition, only a digit remap. Optional
# Markdown "#" prefix so "## บทที่ ๑" is recognized in converted ebooks.
_TH_DIGITS = "๐-๙"
_TH_DIGIT_MAP = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_TH_CHAPTER = re.compile(
    rf"^\s*(?:#{{1,6}}\s+)?(?:บทที่|ตอนที่|ภาคที่|บท|ตอน|ภาค)\s*([0-9{_TH_DIGITS}]+)\b"
)

# Korean chapter headings: "제1장 총칙", "## 제4장 근로시간과 휴식", "제6장의2 …".
# 제 + Arabic numeral + a classifier (장 chapter / 편 part / 절 section / 관
# subsection), with an optional "의N" branch suffix that Korean statutes use for
# inserted chapters (제6장의2). Modern Korean numbers chapters with Arabic digits,
# so unlike the Chinese branch no numeral composition is needed. Optional Markdown
# "#" prefix so "## 제1장" is recognized in converted ebooks.
#
# The trailing group is the Korean analogue of _HEADING_TAIL: Korean has no letter
# case, so the existing "capitalized title word" test does not transfer.
# Requiring end-of-line, punctuation, or whitespace-then-content is what separates
# a heading from a prose cross-reference, because Korean particles attach directly
# to the noun ("제5장에서", "제2장의") with no intervening space.
_KO_CHAPTER = re.compile(
    r"^\s*(?:#{1,6}\s+)?제\s*([0-9]+)\s*[장편절관](?:\s*의\s*[0-9]+)?(?:\s*$|[.:\-]|\s+\S)"
)

# Table-of-contents header lines across common languages. Anchored to a whole
# line (^\s*X\s*$) so an inline "the contents of this chapter" never matches.
_TOC_HEADERS = (
    "table of contents", "contents", "índice", "sumário",   # EN / ES / PT
    "sumario",                                              # PT (no accent — OCR / accent-stripped, like indice below)
    "table des matières",                                   # French
    "inhaltsverzeichnis",                                   # German
    "indice", "sommario",                                   # Italian (no accent — distinct from índice above)
    "inhoudsopgave",                                        # Dutch
)
_TOC_CJK_PATTERN = r"目[ \t\u3000]*(?:录|錄|次)"
_TOC_PATTERN = re.compile(
    r"^\s*(?:"
    + "|".join([*(re.escape(h) for h in _TOC_HEADERS), _TOC_CJK_PATTERN])
    + r")\s*$",
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


# Opening or closing line of a fenced code block: three or more backticks or
# tildes. The captured marker lets the closer be matched to its opener.
_CODE_FENCE = re.compile(r"^(`{3,}|~{3,})")


def _closed_fence_line_numbers(lines: list[str]) -> set[int]:
    """Line indices inside a fenced code block that is actually CLOSED.

    A fence that never closes is treated as ordinary text rather than swallowing
    everything after it. Extraction routinely loses a closing fence, and a book
    about Markdown can simply contain a stray one — and the old live-toggling
    scan then dropped every heading from that point to the end of the document.
    Counting a handful of code lines as prose is a far cheaper mistake than
    losing most of a book's structure.

    The closing fence must use the SAME character as its opener, per CommonMark,
    so a "```" block is no longer terminated by an unrelated "~~~" line.
    """
    inside: set[int] = set()
    opener: tuple[str, int] | None = None
    for index, line in enumerate(lines):
        match = _CODE_FENCE.match(line.strip())
        if not match:
            continue
        marker = match.group(1)
        if opener is None:
            opener = (marker[0], index)
        elif marker[0] == opener[0]:
            # Include both fence marker lines themselves.
            inside.update(range(opener[1], index + 1))
            opener = None
    return inside


# A numbered heading is a chapter when the numbering is systematic AND the
# sections carry a chapter's worth of text. Both are required, because neither
# separates the two shapes alone: a three-step tutorial is also systematic and
# also ascends from 1, while a single long section is not a numbering scheme.
# Measured medians of body text per section: tutorial steps ~20 chars, doc
# sections ~500, paper sections ~2,000, real book chapters ~5,000. The floor
# sits an order of magnitude below the smallest real chapter seen and an order
# above the largest tutorial step.
_MIN_NUMBERED_TITLES = 3
_MIN_NUMBERED_BODY_CHARS = 200


def _numbered_titles_are_structural(
    entries: list[tuple[str, int]], heading_lines: list[int], lines: list[str]
) -> bool:
    """Decide whether digit-led titles at one depth are chapters or list items.

    Deliberately not based on the numbers themselves. An ascending run starting
    at 1 describes "Step 1 / Step 2 / Step 3" as accurately as it describes a
    paper's sections, and requiring the run to be unbroken would throw away a
    whole book when extraction drops one heading, a chapter list that starts at
    0, or a multi-source corpus where the numbering restarts.
    """
    if len(entries) < _MIN_NUMBERED_TITLES:
        return False
    ordered = sorted(heading_lines)
    bodies = []
    for _, index in entries:
        after = [ln for ln in ordered if ln > index]
        end = after[0] if after else len(lines)
        bodies.append(sum(len(ln) for ln in lines[index + 1:end]))
    return statistics.median(bodies) >= _MIN_NUMBERED_BODY_CHARS


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
    lines = text.splitlines()
    levels: dict[int, set[str]] = {}
    # Digit-led titles are held back and judged per depth at the end (see
    # _numbered_titles_are_structural): "## 1. Introduction" and "## 5 Setup"
    # are the same string shape, so the line alone cannot decide.
    numbered: dict[int, list[tuple[str, int]]] = {}
    heading_lines: list[int] = []
    fenced = _closed_fence_line_numbers(lines)
    prev = ""  # previous non-fence line (stripped); a setext title candidate
    for index, line in enumerate(lines):
        if index in fenced:
            prev = ""
            continue
        s = line.strip()
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
            heading_lines.append(index)
            prev = ""
            continue
        # ATX heading ("# Title", "== Section").
        m = _ATX_HEADING.match(s)
        if m:
            title = m.group(2).strip().lower()
            depth = len(m.group(1))
            # Reject empty and all-punctuation ("=====" table-border) titles.
            if title and re.search(r"\w", title):
                heading_lines.append(index)
                if title[0].isdigit():
                    numbered.setdefault(depth, []).append((title, index))
                else:
                    levels.setdefault(depth, set()).add(title)
            # An ATX heading line is not a setext title for the next line.
            prev = ""
            continue
        prev = s
    for depth, entries in numbered.items():
        if _numbered_titles_are_structural(entries, heading_lines, lines):
            levels.setdefault(depth, set()).update(title for title, _ in entries)
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


def _match_chapter_number(line: str) -> int | None:
    """Return the chapter number if the line is a genuine chapter heading,
    with no Markdown/AsciiDoc heading prefix (the caller strips it first)."""
    s = line.strip()
    if len(s) > 80:
        return None
    m = _EXPLICIT_CHAPTER.match(s)
    if m and _HEADING_TAIL.match(m.group("rest")):
        if m.group(1):
            return int(m.group(1))
        return _roman_to_int(m.group("roman").upper())
    rm = _ROMAN_HEAD.match(s) or _LC_MD_ROMAN.match(s)
    if rm:
        return _roman_to_int(rm.group(1))
    cm = _CN_CHAPTER.match(s) or _MD_CN_HEADING.match(s)
    if cm:
        return _cn_numeral_to_int(cm.group(1))
    tm = _TH_CHAPTER.match(s)
    if tm:
        return int(tm.group(1).translate(_TH_DIGIT_MAP))
    km = _KO_CHAPTER.match(s)
    if km:
        return int(km.group(1))
    return None


def _chapter_number(line: str) -> int | None:
    """Return the chapter number if the line is a genuine chapter heading.

    Handles Arabic ("Chapter 5", "Capítulo 5: ..."), Roman-numeral
    ("I: Loomings", "## i. introduction", "II. The Carpet-Bag"),
    Chinese ("第三章 …", "## 一 · …", "## 第一讲"), Thai ("บทที่ 3",
    "## บทที่ ๑"), and Korean ("제1장 총칙", "## 제4장 근로시간과 휴식")
    heading styles — each optionally preceded by a Markdown/AsciiDoc heading
    marker ("## Chapter 1" is a chapter heading just like "Chapter 1").
    """
    match = _match_chapter_number(line)
    if match is not None:
        return match
    # Second pass: a Markdown/AsciiDoc heading prefix ("## Chapter 1",
    # "== Section") hides the heading from the matchers above — the CJK
    # matchers tolerate the prefix inline but the Latin/Thai/Korean ones anchor
    # on the line start. Strip the prefix and retry so --mode technical
    # (Docling emits headings as Markdown) detects the same chapters as
    # plain-text extraction. (Issue #91)
    s = line.strip()
    md = _MD_HEADING_PREFIX.match(s)
    if md:
        return _match_chapter_number(s[md.end():])
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
    numeric_count = len(numbers)
    # Fall back to structural (Markdown/AsciiDoc) headings only when no numeric
    # "Chapter N" headings were found, so books with real chapters are unaffected.
    #
    # Which branch answered is reported alongside the count. The two disagree
    # often, and a wrong count is not visible in the output it produces: it
    # becomes the plan in Step 3 and the chapter files of the generated skill.
    # Every parser in this project already announces which method it used
    # ("Trying python-docx... OK"); this decision had the same shape and was
    # the only silent one.
    if numeric_count > 0:
        chapters_detected = numeric_count
        chapters_method = "numeric"
    else:
        chapters_detected = _structural_chapter_count(text)
        chapters_method = "structural" if chapters_detected else "none"

    # Look for ToC indicators in the first ~30k chars (multilingual; see _TOC_PATTERN)
    has_toc = bool(_TOC_PATTERN.search(text[:30000]))

    return {
        "chapters_detected": chapters_detected,
        "chapters_method": chapters_method,
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
            print(f"WARNING: Unknown flag '{arg}' — ignoring it.", file=sys.stderr)
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

    A leading "~" is expanded here rather than relying on the shell: a glob has
    to be quoted to reach us unexpanded ("~/books/*.epub"), and quoting stops
    the shell expanding the tilde too. `glob.glob` and `Path` both treat "~" as
    a literal directory name, so without this the pattern silently matches
    nothing.
    """
    resolved = []
    for raw_path in paths:
        # Normalise "~" once, at the entry point, so both the glob branch and
        # the file/directory branch below see a real path.
        path_str = os.path.expanduser(raw_path)
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
    
    # Sniff magic bytes if suffix is not supported.
    #
    # Every failure in this function has to surface as ExtractionError: the
    # batch loop in main() catches only that, and anything else aborts the whole
    # run — including the sources that would have extracted fine. An unreadable
    # or unopenable file is a per-source problem, so translate it here. (The
    # ZipFile branch below already does this for OSError.)
    if ext not in SUPPORTED_EXTENSIONS:
        try:
            with open(input_str, "rb") as f:
                header = f.read(8)
        except OSError as exc:
            raise ExtractionError(
                f"Could not read {input_path.name}: {exc.strerror or exc}"
            ) from exc
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
        if looks_image_only(input_str):
            raise ExtractionError(
                f"{input_path.name} looks like a scanned (image-only) PDF: its first pages "
                "contain no extractable text, only images.\n"
                "Run OCR on it first, then retry:\n"
                "  ocrmypdf input.pdf output.pdf"
            )
        if extraction_mode == "technical":
            print("Mode: technical — using Docling (layout-aware)...", end=" ", flush=True)
            text = extract_with_docling(input_str)
            if text and text.strip():
                method = "docling"
                print("OK")
            else:
                print("not available, falling back to pdftotext")
                extraction_mode = "text"
                
        if extraction_mode == "text" or not text:
            print("Mode: text — using pdftotext...")
            print("Trying pdftotext...", end=" ", flush=True)
            text = extract_with_pdftotext(input_str)

            if text and text.strip():
                method = "pdftotext"
                print("OK")
            else:
                print("not available")
                print("Trying pypdf...", end=" ", flush=True)
                text = extract_with_pypdf(input_str)
                if text and text.strip():
                    method = "pypdf"
                    print("OK")
                else:
                    print("not available")
                    print("Trying pdfminer.six...", end=" ", flush=True)
                    text = extract_with_pdfminer(input_str)
                    if text and text.strip():
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

    text, removed_invisible = sanitize_extracted_text(text)
    if removed_invisible:
        print(
            f"  [security] removed {removed_invisible} invisible Unicode "
            f"code point(s) from {input_path.name}",
            file=sys.stderr,
        )
    if not text.strip():
        raise ExtractionError(
            f"Extracted text from {input_path.name} contained no visible content "
            "after Unicode sanitization."
        )

    tokens = estimate_tokens(text)
    structure = detect_structure(text)
    print(
        f"  chapters: {structure['chapters_detected']} "
        f"({structure['chapters_method']})"
    )
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


def prepare_output_dir(path: Path) -> None:
    """Create the work directory, guarding against two shared-tmp risks:
    a pre-planted symlink at a predictable path, and reusing a directory
    another user already owns (either could expose or tamper with the
    extracted document text, which may be sensitive).
    """
    if path.is_symlink():
        raise ExtractionError(
            f"Refusing to use {path}: it is a symbolic link, not a real "
            "directory. Remove it or set BOOK_SKILL_WORKDIR to a private path."
        )
    if path.exists():
        if not path.is_dir():
            raise ExtractionError(f"Refusing to use {path}: it exists and is not a directory.")
        if hasattr(os, "getuid"):
            owner_uid = path.stat().st_uid
            if owner_uid != os.getuid():
                raise ExtractionError(
                    f"Refusing to use {path}: it is owned by a different user "
                    f"(uid {owner_uid}). Set BOOK_SKILL_WORKDIR to a private directory."
                )
            os.chmod(path, 0o700)
    else:
        path.mkdir(parents=True, mode=0o700)


def print_intro() -> None:
    """Two lines of attribution at the start of every run.

    Printed here rather than only in SKILL.md so it shows however the agent
    invokes extraction. States who maintains the project without asking for
    anything — the ask belongs at the end, after the work is delivered.
    """
    sys.stderr.write(
        "book-to-skill · turns a document into a structured agent skill\n"
        "free and MIT-licensed · maintained in personal time · "
        "github.com/virgiliojr94/book-to-skill\n\n"
    )


def print_support_note() -> None:
    """One closing line about funding, printed only after a successful run.

    Deliberately at the end and deliberately conditional: the reader has just
    received something that worked, and the sentence says what the money is
    for rather than asking for it. Never printed when extraction failed —
    nobody should be asked to fund what just wasted their time.

    Written to stdout, with the rest of the closing report: stderr is
    unbuffered and stdout is not when the run is piped (which is how an agent
    captures it), so mixing the two puts the closing line at the top.
    """
    print(
        "\n   book-to-skill is free, and maintained in personal time."
        "\n   If it saves you work, you can fund its upkeep: "
        "github.com/sponsors/virgiliojr94"
    )


def print_usage() -> None:
    """Print standalone CLI usage."""
    print(
        "Usage: book-to-skill <path-to-document-folder-or-glob>... "
        "[--mode technical|text] [--install-missing ask|yes|no]",
        file=sys.stderr,
    )
    print(
        "       book-to-skill --check    # report which extractors are installed",
        file=sys.stderr,
    )
    print(f"Supported formats: {supported_formats_message()}", file=sys.stderr)


def main():
    print_intro()

    if any(arg in {"-h", "--help"} for arg in sys.argv[1:]):
        print_usage()
        sys.exit(0)

    if "--check" in sys.argv[1:]:
        sys.exit(run_dependency_check())

    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
        
    raw_input_paths, extraction_mode, install_mode = parse_arguments(sys.argv)
    
    if not raw_input_paths:
        print("ERROR: No input document, folder, or glob pattern specified.", file=sys.stderr)
        sys.exit(1)
        
    input_files = resolve_input_files(raw_input_paths)
    
    if not input_files:
        print(f"ERROR: No supported files found matching: {', '.join(raw_input_paths)}", file=sys.stderr)
        sys.exit(1)
        
    prepare_output_dir(OUTPUT_DIR)
    
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
    
    # Detect structure from source content only. The generated SOURCE banners in
    # full_text.txt use rows of "=", which can otherwise become phantom setext
    # headings and make the result depend on the source-path length.
    structure_text = "\n\n".join(src["text"] for src in extracted_sources)
    consolidated_structure = detect_structure(structure_text)
    # has_toc is a per-source property, so it has to be combined per source
    # rather than re-derived from the corpus. detect_structure only scans the
    # first ~30k chars, because a table of contents sits in a book's front
    # matter -- but on a consolidated corpus that window covers only the FIRST
    # source, so a ToC in any later book was invisible and the answer flipped on
    # input order alone. Each per-source result already scanned its own front
    # matter, so OR them.
    consolidated_structure["has_toc"] = any(
        src["has_toc"] for src in extracted_sources
    )
    
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
                "chapters_method": src["chapters_method"],
                "has_toc": src["has_toc"]
            }
            for src in extracted_sources
        ],
        **consolidated_structure,
    }
    
    # encoding="utf-8" is required, not cosmetic: the payload is dumped with
    # ensure_ascii=False, so any non-ASCII chapter heading, filename or path
    # reaches the encoder verbatim. Without it, write_text() falls back to the
    # locale encoding and raises UnicodeEncodeError on a Windows cp1252 host or
    # under LC_ALL=C — after every source has already been extracted.
    OUTPUT_META.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    
    page_line = f"   Total Pages: {total_pages}"
    print("\nExtraction complete:")
    print(f"   Sources : {len(extracted_sources)} processed")
    print(f"   Size    : {total_file_size_mb:.2f} MB")
    print(page_line)
    print(f"   Words   : {total_words:,}")
    print(f"   Tokens  : ~{total_tokens // 1000}K")
    print(
        f"   Chapters: {consolidated_structure['chapters_detected']} detected overall "
        f"({consolidated_structure['chapters_method']})"
    )
    if consolidated_structure["chapters_method"] == "structural" and (
        consolidated_structure["chapters_detected"] <= 1 and total_words > 5000
    ):
        # Numeric "Chapter N" headings found nothing and the structural fallback
        # came back with one section for a document of real length. That pairing
        # is a detection failure far more often than it is a one-chapter book,
        # and it is invisible in the output it produces.
        print(
            "   WARN    : only one section found in a document this long — chapter "
            "detection likely failed; check the headings before generating."
        )
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
    else:
        print_support_note()
