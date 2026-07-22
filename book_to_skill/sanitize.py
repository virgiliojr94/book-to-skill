from __future__ import annotations


_ZERO_WIDTH_CODEPOINTS = frozenset({0x200B, 0x200C, 0x200D, 0xFEFF})
_TAG_BLOCK_START = 0xE0000
_TAG_BLOCK_END = 0xE007F


def sanitize_extracted_text(text: str) -> tuple[str, int]:
    """Remove invisible code points used for document-borne prompt injection."""
    kept: list[str] = []
    removed = 0

    for character in text:
        codepoint = ord(character)
        if (
            codepoint in _ZERO_WIDTH_CODEPOINTS
            or _TAG_BLOCK_START <= codepoint <= _TAG_BLOCK_END
        ):
            removed += 1
            continue
        kept.append(character)

    return "".join(kept), removed
