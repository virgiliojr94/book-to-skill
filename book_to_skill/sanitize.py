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

# 5. Deprecated / annotation format controls. All category Cf,
#    Default_Ignorable, and render as nothing — the same invisible
#    format-control shape as group 1, just blocks the original list missed.
#    None has any use in extracted book prose.
_ANNOTATION_FORMAT_CODEPOINTS = frozenset({
    0x206A,  # INHIBIT SYMMETRIC SWAPPING
    0x206B,  # ACTIVATE SYMMETRIC SWAPPING
    0x206C,  # INHIBIT ARABIC FORM SHAPING
    0x206D,  # ACTIVATE ARABIC FORM SHAPING
    0x206E,  # NATIONAL DIGIT SHAPES
    0x206F,  # NOMINAL DIGIT SHAPES
    0xFFF9,  # INTERLINEAR ANNOTATION ANCHOR
    0xFFFA,  # INTERLINEAR ANNOTATION SEPARATOR
    0xFFFB,  # INTERLINEAR ANNOTATION TERMINATOR
})

_INVISIBLE_CODEPOINTS = (
    _ZERO_WIDTH_CODEPOINTS
    | _BIDI_CONTROL_CODEPOINTS
    | _INVISIBLE_LETTER_CODEPOINTS
    | _ANNOTATION_FORMAT_CODEPOINTS
)

# 4. The Unicode tag block. Originally language tags, now used to smuggle an
#    entire ASCII payload as invisible "tag" characters.
_TAG_BLOCK_START = 0xE0000
_TAG_BLOCK_END = 0xE007F

# 5. Variation selectors. The same smuggling trick as the tag block, moved to a
#    block that survives more pipelines: each selector carries one of 256
#    values, so a run of them after any base character encodes an arbitrary
#    payload while rendering as nothing at all. They are combining marks rather
#    than format controls, so a category-based filter that catches Cf misses
#    them entirely.
#
#    Dropping them costs only the emoji/text presentation hint on a character
#    that already renders, which is a smaller loss than U+200D above already
#    accepts by splitting emoji ZWJ sequences.
_VARIATION_SELECTOR_RANGES = (
    (0xFE00, 0xFE0F),    # VARIATION SELECTOR-1 .. -16
    (0xE0100, 0xE01EF),  # VARIATION SELECTOR-17 .. -256 (supplement)
)

# 7. Interlinear annotation controls. A conforming renderer hides the annotation
#    between the anchor and the terminator, so text a human never sees is still
#    read in full by the model — the same split this module exists to close.
# 6. Deprecated format controls. Category Cf and Default_Ignorable, with no
#    legitimate use in extracted book prose; contributed by #182.
_DEPRECATED_FORMAT_RANGE = (0x206A, 0x206F)

_ANNOTATION_CODEPOINTS = frozenset({
    0xFFF9,  # INTERLINEAR ANNOTATION ANCHOR
    0xFFFA,  # INTERLINEAR ANNOTATION SEPARATOR
    0xFFFB,  # INTERLINEAR ANNOTATION TERMINATOR
})

# 8. Musical beaming and phrasing controls: zero-width format characters that
#    can pad hidden text anywhere, not only in musical notation.
_MUSICAL_FORMAT_RANGE = (0x1D173, 0x1D17A)


def is_invisible_codepoint(codepoint: int) -> bool:
    """Return True if the code point renders as nothing and should be stripped.

    Exposed so the generated-skill scanner can flag exactly what extraction
    strips. When the two sets drift, the extractor lets a character through that
    the scanner then warns about — or worse, neither layer covers it.
    """
    if codepoint in _INVISIBLE_CODEPOINTS or codepoint in _ANNOTATION_CODEPOINTS:
        return True
    if _DEPRECATED_FORMAT_RANGE[0] <= codepoint <= _DEPRECATED_FORMAT_RANGE[1]:
        return True
    if _TAG_BLOCK_START <= codepoint <= _TAG_BLOCK_END:
        return True
    if _MUSICAL_FORMAT_RANGE[0] <= codepoint <= _MUSICAL_FORMAT_RANGE[1]:
        return True
    return any(low <= codepoint <= high for low, high in _VARIATION_SELECTOR_RANGES)


def sanitize_extracted_text(text: str) -> tuple[str, int]:
    """Remove invisible code points used for document-borne prompt injection."""
    # Fast-path: pure ASCII (<0x80) cannot contain any invisible codepoint in our sets
    # (lowest is 0xAD, but ASCII path is >90% of Latin books — saves is_invisible checks).
    # Minimal perf fix per DEBT D3 — deterministic, no prompt lengthening.
    if text.isascii():
        return text, 0
    kept: list[str] = []
    removed = 0

    for character in text:
        cp = ord(character)
        if cp < 0x80:
            kept.append(character)
            continue
        if is_invisible_codepoint(cp):
            removed += 1
            continue
        kept.append(character)

    return "".join(kept), removed
