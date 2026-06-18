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


def strip_rtf_fallback(raw: str) -> str:
    raw = _RTF_UNICODE.sub(_rtf_unicode_repl, raw)   # decode \uN escapes first
    raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    raw = re.sub(r"\\par[d]?", "\n", raw)
    raw = re.sub(r"\\tab", "\t", raw)
    raw = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", raw)
    raw = raw.replace("{", "").replace("}", "")
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
