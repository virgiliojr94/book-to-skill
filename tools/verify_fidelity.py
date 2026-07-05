#!/usr/bin/env python3
"""verify_fidelity.py — a cheap faithfulness check for a generated skill.

book-to-skill promises "answers from the actual book, not hallucination", but
nothing verified that. This script does a fast, deterministic sanity pass: it
pulls every **bolded term** the skill asserts (framework / concept names in
SKILL.md, glossary.md, patterns.md, cheatsheet.md and chapters/*.md) and checks
whether each one actually occurs in the source text (full_text.txt). Terms that
do not appear are flagged as *possible* confabulations for a human to review.

It cannot judge meaning — a term can appear in the source yet be mis-explained —
so this is a smell test, not a proof of correctness. But a bolded framework name
that is nowhere in the book is a strong signal, and this is a useful gate to run
right after generation (before the working text is cleaned up).

Usage:
  python3 tools/verify_fidelity.py --skill-dir <dir> --full-text <full_text.txt>
      [--min-coverage 0.85] [--quiet]

Exit code: 0 if coverage >= threshold (or there was nothing to check), else 1.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_WORD = re.compile(r"\w+", re.UNICODE)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s).lower()).strip()


def _terms_from_markdown(text: str) -> list[str]:
    terms = []
    for m in _BOLD.finditer(text):
        term = m.group(1).strip().strip(":—-").strip()
        # If the bold accidentally spans "Term — definition", keep only the term.
        term = re.split(r"\s[—-]\s", term)[0].strip()
        if term and len(term) <= 80:
            terms.append(term)
    return terms


def _appears(term: str, source_norm: str, source_tokens: set[str]) -> bool:
    tn = _normalize(term)
    if not tn:
        return True
    if tn in source_norm:
        return True
    # Token-overlap fallback: a multi-word framework name counts as present if
    # most of its significant words occur in the source. Handles reordering and
    # minor formatting differences (hyphenation, punctuation) without matching
    # on trivial stopword-length fragments.
    words = [w for w in _WORD.findall(tn) if len(w) > 2]
    if not words:
        return tn in source_norm
    hits = sum(1 for w in words if w in source_tokens)
    return hits / len(words) >= 0.7


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skill-dir", required=True, help="Generated skill directory")
    ap.add_argument("--full-text", required=True, help="Path to full_text.txt (the source)")
    ap.add_argument("--min-coverage", type=float, default=0.85)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    skill_dir = Path(args.skill_dir)
    source = Path(args.full_text).read_text(encoding="utf-8", errors="ignore")
    source_norm = _normalize(source)
    source_tokens = {w for w in _WORD.findall(source_norm) if len(w) > 2}

    md_files = sorted(skill_dir.rglob("*.md"))
    if not md_files:
        print(f"No .md files under {skill_dir}", file=sys.stderr)
        return 0

    seen: set[str] = set()
    checked = 0
    missing: list[tuple[str, Path]] = []
    for f in md_files:
        for term in _terms_from_markdown(f.read_text(encoding="utf-8", errors="ignore")):
            key = _normalize(term)
            if key in seen:
                continue
            seen.add(key)
            checked += 1
            if not _appears(term, source_norm, source_tokens):
                missing.append((term, f.relative_to(skill_dir)))

    if checked == 0:
        print("No bolded terms found to verify.")
        return 0

    coverage = 1 - len(missing) / checked
    if not args.quiet:
        print(
            f"Fidelity check: {checked} unique bolded terms, "
            f"{checked - len(missing)} found in source ({coverage:.0%} coverage)."
        )
        if missing:
            print(
                "\nTerms NOT found in source "
                "(review — possible confabulation or heavy paraphrase):"
            )
            for term, rel in missing[:60]:
                print(f"  \u2717 {term}   [{rel}]")
            if len(missing) > 60:
                print(f"  \u2026 and {len(missing) - 60} more")

    if coverage < args.min_coverage:
        print(
            f"\nFAIL: coverage {coverage:.0%} < threshold {args.min_coverage:.0%}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
