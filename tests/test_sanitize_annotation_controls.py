"""Deprecated / interlinear-annotation format controls are stripped too.

These are category Cf, Default_Ignorable code points that render as nothing —
the same invisible format-control shape as the zero-width set — but the original
blocklist missed them, so they passed straight through the extraction scrub (and,
because the scanner shares is_invisible_codepoint, went unflagged there too).
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill.sanitize import is_invisible_codepoint, sanitize_extracted_text

# U+206A-206F (deprecated format controls) + U+FFF9-FFFB (interlinear annotation).
ANNOTATION_CONTROLS = "".join(
    chr(cp) for cp in [*range(0x206A, 0x2070), 0xFFF9, 0xFFFA, 0xFFFB]
)


def test_all_annotation_controls_are_invisible():
    assert all(is_invisible_codepoint(ord(c)) for c in ANNOTATION_CONTROLS)


def test_annotation_controls_are_stripped_and_counted():
    text = f"study{ANNOTATION_CONTROLS}advice"
    cleaned, removed = sanitize_extracted_text(text)
    assert cleaned == "studyadvice"
    assert removed == len(ANNOTATION_CONTROLS)


def test_visible_lookalikes_are_kept():
    # Braille blank (U+2800) and a musical symbol are real So characters, not
    # invisible format controls — they must survive.
    text = "a⠀b\U0001D159c"
    cleaned, removed = sanitize_extracted_text(text)
    assert cleaned == text
    assert removed == 0
