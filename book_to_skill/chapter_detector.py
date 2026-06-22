from __future__ import annotations

import re

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


def _detect_all_headers(text: str) -> list[dict]:
    """Scan lines of text to build an ordered list of detected headers with levels and char indices."""
    lines = text.splitlines(keepends=True)
    headers = []
    
    current_pos = 0
    in_fence = False
    
    prev_line = ""
    prev_pos = 0
    
    for line in lines:
        line_len = len(line)
        s = line.strip()
        
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            prev_line = ""
            prev_pos = current_pos + line_len
            current_pos += line_len
            continue
            
        if in_fence:
            prev_line = ""
            prev_pos = current_pos + line_len
            current_pos += line_len
            continue
            
        # 1. Setext/RST underline detection
        if (
            _SETEXT_UNDERLINE.match(s)
            and prev_line
            and not _SETEXT_UNDERLINE.match(prev_line)
            and len(s) >= len(prev_line)
        ):
            depth = 1 if s[0] == "=" else 2
            
            # Prevent double-registering if prev_line was already matched as numeric/explicit
            already_registered = False
            if headers and headers[-1]["start_char"] == prev_pos:
                already_registered = True
                
            if not already_registered:
                headers.append({
                    "title": prev_line,
                    "level": depth,
                    "start_char": prev_pos,
                })
            
            prev_line = ""
            prev_pos = current_pos + line_len
            current_pos += line_len
            continue
            
        # 2. Explicit chapter numeric heading
        num = _chapter_number(line)
        if num is not None:
            headers.append({
                "title": s,
                "level": 1,
                "start_char": current_pos,
            })
            prev_line = ""
            prev_pos = current_pos + line_len
            current_pos += line_len
            continue
            
        # 3. ATX style Markdown/AsciiDoc heading
        m = _ATX_HEADING.match(s)
        if m:
            title = m.group(2).strip()
            if title and not title[0].isdigit() and re.search(r"\w", title):
                headers.append({
                    "title": title,
                    "level": len(m.group(1)),
                    "start_char": current_pos,
                })
            prev_line = ""
            prev_pos = current_pos + line_len
            current_pos += line_len
            continue
            
        prev_line = s
        prev_pos = current_pos
        current_pos += line_len
        
    # Calculate end_char for each header in a subsequent pass
    total_len = len(text)
    for idx, h in enumerate(headers):
        end_char = total_len
        for next_h in headers[idx + 1:]:
            if next_h["level"] <= h["level"]:
                end_char = next_h["start_char"]
                break
        h["end_char"] = end_char
        
    return headers


def _build_hierarchical_ast(text: str) -> list[dict]:
    """Parse text and build a nested Hierarchical AST list of headers."""
    headers = _detect_all_headers(text)
    total_len = len(text)
    
    # Handle documents with no detected headers
    if not headers:
        if text.strip():
            return [{
                "title": "Documento Completo",
                "level": 1,
                "start_char": 0,
                "end_char": total_len,
                "children": [],
            }]
        return []
        
    root_nodes = []
    
    # Handle Front Matter/Preface before the first real heading
    first_header_start = headers[0]["start_char"]
    if first_header_start > 0 and text[:first_header_start].strip():
        root_nodes.append({
            "title": "Prefácio / Introdução",
            "level": 1,
            "start_char": 0,
            "end_char": first_header_start,
            "children": [],
        })
        
    stack = []
    
    for h in headers:
        node = {
            "title": h["title"],
            "level": h["level"],
            "start_char": h["start_char"],
            "end_char": h["end_char"],
            "children": [],
        }
        
        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()
            
        if stack:
            stack[-1]["children"].append(node)
        else:
            root_nodes.append(node)
            
        stack.append(node)
        
    return root_nodes


def detect_structure(text: str) -> dict:
    """Detect chapter count, table of contents presence, and hierarchical AST.

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
    chapters_detected = (
        numeric_count if numeric_count > 0 else _structural_chapter_count(text)
    )

    # Look for ToC indicators in the first ~30k chars (multilingual; see _TOC_PATTERN)
    has_toc = bool(_TOC_PATTERN.search(text[:30000]))
    
    # Build the Hierarchical AST
    ast = _build_hierarchical_ast(text)

    return {
        "chapters_detected": chapters_detected,
        "chapter_headings_sample": headings[:10],
        "has_toc": has_toc,
        "ast": ast,
    }

