import html
import re
import sys
from book_to_skill.parsers.text import read_text_file
from book_to_skill.exceptions import ExtractionError


# RTF unicode escape: \uN (signed decimal) followed by its fallback char(s).
# Decode the code point and drop the standard single fallback — a \'XX hex byte
# or a literal "?". Assumes the default \uc1 (one fallback char); \ucN directives
# and multi-char/group fallbacks are not parsed (best-effort fallback only).
_RTF_UNICODE = re.compile(r"\\u(-?\d+)[ ]?(?:\\'[0-9a-fA-F]{2}|\?)?")


def _rtf_unicode_repl(match: re.Match) -> str:
    cp = int(match.group(1)) % 0x10000      # RTF uses signed 16-bit; wrap negatives
    if cp == 0 or 0xD800 <= cp <= 0xDFFF:   # NUL and lone surrogates: unwanted in text
        return ""
    return chr(cp)


# RTF groups whose contents are metadata or formatting tables rather than
# document text. Stripping only the control words inside them (what the cleanup
# below does) leaves the residue behind: font and style *names*, the generator
# string, and the \info title/author all end up in the extracted book text.
_SKIP_DESTINATIONS = frozenset({
    "fonttbl",            # {\fonttbl{\f0\fnil Calibri;}}   -> "Calibri;"
    "colortbl",           # {\colortbl;\red255...;}          -> ";;;"
    "stylesheet",         # {\stylesheet{\s0 Normal;}}       -> "Normal;"
    "info",               # {\info{\title X}{\author Y}}     -> "XY"
    "listtable", "listoverridetable", "revtbl", "rsidtbl",
    "latentstyles", "datastore", "themedata", "colorschememapping",
    "filetbl", "xmlnstbl", "pgptbl", "protusertbl", "userprops",
    "docvar",
    "pict", "objdata",    # binary image / OLE payloads as hex text
    "bkmkstart", "bkmkend",
})

# The first control word of a group, allowing the "\*" ignorable-destination
# prefix: "{\fonttbl", "{\*\generator", "{\*\bkmkstart".
_GROUP_DESTINATION = re.compile(r"\\\*?\\?([a-zA-Z]+)")


def _strip_destination_groups(raw: str) -> str:
    """Remove RTF groups that hold no document text.

    Tracks brace depth so a whole group is dropped, not just its control words.
    Per the RTF spec a reader that does not understand a ``\\*`` destination must
    skip the entire group, which also handles ``\\*\\generator`` and any vendor
    extension without naming it. Escaped ``\\{`` / ``\\}`` / ``\\\\`` are not
    treated as delimiters.

    A useful side effect: for a field, ``{\\field{\\*\\fldinst HYPERLINK ...}
    {\\fldrslt visible text}}`` keeps the result and drops the instruction.
    """
    out: list[str] = []
    index = 0
    depth = 0
    skip_at_depth = 0  # non-zero while inside a skipped group
    length = len(raw)

    while index < length:
        char = raw[index]

        # Escaped literal: "\{", "\}", "\\" are text, never group delimiters.
        if char == "\\" and index + 1 < length and raw[index + 1] in "{}\\":
            if not skip_at_depth:
                out.append(raw[index:index + 2])
            index += 2
            continue

        if char == "{":
            depth += 1
            if not skip_at_depth:
                match = _GROUP_DESTINATION.match(raw, index + 1)
                ignorable = raw.startswith("{\\*", index)
                if ignorable or (match and match.group(1) in _SKIP_DESTINATIONS):
                    skip_at_depth = depth
                else:
                    out.append(char)
            index += 1
            continue

        if char == "}":
            if skip_at_depth and depth == skip_at_depth:
                skip_at_depth = 0
            elif not skip_at_depth:
                out.append(char)
            depth -= 1
            index += 1
            continue

        if not skip_at_depth:
            out.append(char)
        index += 1

    if skip_at_depth:
        # Unterminated destination group: the file is malformed and everything
        # after the unclosed brace was just dropped, which could be the whole
        # book. Leaking some metadata residue is the lesser evil, so fall back
        # to the unscanned text rather than returning a truncated document.
        return raw

    return "".join(out)


def strip_rtf_fallback(raw: str) -> str:
    # Drop metadata/table groups wholesale first, so their contents never reach
    # the control-word cleanup that would otherwise strip the markup and leave
    # the names behind as if they were prose.
    raw = _strip_destination_groups(raw)
    raw = _RTF_UNICODE.sub(_rtf_unicode_repl, raw)   # decode \uN escapes first
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\par[d]?", "\n", raw)
    raw = re.sub(r"\\tab", "\t", raw)
    # Park the three escaped literals ("\\", "\{", "\}") on placeholders before
    # the sweeps below, which would otherwise strip the backslash as a control
    # symbol and then delete the brace along with the real group delimiters —
    # leaving a stray "\" where the book said "{a, b}". Longest escape first.
    raw = (
        raw.replace("\\\\", "\x01")
        .replace("\\{", "\x02")
        .replace("\\}", "\x03")
    )
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    raw = raw.replace("{", "").replace("}", "")
    raw = raw.replace("\x01", "\\").replace("\x02", "{").replace("\x03", "}")
    return html.unescape(raw)


def extract_rtf(rtf_path: str) -> tuple[str, str]:
    raw = read_text_file(rtf_path)
    if raw is None:
        raise ExtractionError(f"Could not read RTF file: {rtf_path}")

    try:
        from striprtf.striprtf import rtf_to_text
        text = rtf_to_text(raw)
        if text.strip():
            return text, "striprtf"
    except ImportError:
        pass
    except Exception as e:
        print(f"  [warn] extract_rtf/striprtf failed: {type(e).__name__}: {e}", file=sys.stderr)

    return strip_rtf_fallback(raw), "rtf-regex"
