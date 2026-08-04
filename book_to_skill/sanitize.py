from __future__ import annotations


# Invisible code points used to hide document-borne prompt injection. Grouped by
# attack shape so the reasoning behind each entry stays reviewable.
#
# 1. Zero-width and invisible spacers. Render as nothing, so text between them is
#    invisible to a human reading the page but plain to the model.
_ZERO_WIDTH_CODEPOINTS = frozenset({
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM outside position 0
    0x00AD,  # SOFT HYPHEN — invisible except at a line break
    0x034F,  # COMBINING GRAPHEME JOINER — no rendering effect at all
    0x180E,  # MONGOLIAN VOWEL SEPARATOR
    0x2061,  # FUNCTION APPLICATION
    0x2062,  # INVISIBLE TIMES
    0x2063,  # INVISIBLE SEPARATOR
    0x2064,  # INVISIBLE PLUS
})

# 2. Bidirectional formatting controls — the Trojan Source class
#    (CVE-2021-42574). These do not change the character sequence a model reads,
#    they change the order a human SEES. A crafted line can display as innocuous
#    study advice while the model consumes an injected instruction, so the
#    reviewer approving a generated skill and the agent loading it disagree.
#    Removing them makes rendered order match logical order.
#
#    Legitimate right-to-left books are unaffected: the Unicode Bidi Algorithm
#    derives direction from the characters themselves, so Arabic and Hebrew still
#    render right-to-left without these. Only explicit embeddings, overrides and
#    isolates are dropped, and running prose essentially never needs them.
_BIDI_CONTROL_CODEPOINTS = frozenset({
    0x200E,  # LEFT-TO-RIGHT MARK
    0x200F,  # RIGHT-TO-LEFT MARK
    0x061C,  # ARABIC LETTER MARK
    0x202A,  # LEFT-TO-RIGHT EMBEDDING
    0x202B,  # RIGHT-TO-LEFT EMBEDDING
    0x202C,  # POP DIRECTIONAL FORMATTING
    0x202D,  # LEFT-TO-RIGHT OVERRIDE
    0x202E,  # RIGHT-TO-LEFT OVERRIDE
    0x2066,  # LEFT-TO-RIGHT ISOLATE
    0x2067,  # RIGHT-TO-LEFT ISOLATE
    0x2068,  # FIRST STRONG ISOLATE
    0x2069,  # POP DIRECTIONAL ISOLATE
})

# 3. Characters that are not format controls (so a category-based filter misses
#    them) but still render as blank width. Unlike a space they are letters, so
#    they survive whitespace normalisation and can pad hidden text.
_INVISIBLE_LETTER_CODEPOINTS = frozenset({
    0x115F,  # HANGUL CHOSEONG FILLER
    0x1160,  # HANGUL JUNGSEONG FILLER
    0x3164,  # HANGUL FILLER
    0xFFA0,  # HALFWIDTH HANGUL FILLER
})

_INVISIBLE_CODEPOINTS = (
    _ZERO_WIDTH_CODEPOINTS
    | _BIDI_CONTROL_CODEPOINTS
    | _INVISIBLE_LETTER_CODEPOINTS
)

# 4. The Unicode tag block. Originally language tags, now used to smuggle an
#    entire ASCII payload as invisible "tag" characters.
_TAG_BLOCK_START = 0xE0000
_TAG_BLOCK_END = 0xE007F


def is_invisible_codepoint(codepoint: int) -> bool:
    """Return True if the code point renders as nothing and should be stripped.

    Exposed so the generated-skill scanner can flag exactly what extraction
    strips. When the two sets drift, the extractor lets a character through that
    the scanner then warns about — or worse, neither layer covers it.
    """
    return (
        codepoint in _INVISIBLE_CODEPOINTS
        or _TAG_BLOCK_START <= codepoint <= _TAG_BLOCK_END
    )


def sanitize_extracted_text(text: str) -> tuple[str, int]:
    """Remove invisible code points used for document-borne prompt injection."""
    kept: list[str] = []
    removed = 0

    for character in text:
        if is_invisible_codepoint(ord(character)):
            removed += 1
            continue
        kept.append(character)

    return "".join(kept), removed
