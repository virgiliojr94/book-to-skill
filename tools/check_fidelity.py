#!/usr/bin/env python3
"""Advisory fidelity check: compare a generated skill against its source book.

Closes the gap left by scan_generated_skill.py (security) and validate_skill.py
(host format): neither verifies that the generated prose is actually faithful
to the source material. Real-world failure classes seen in post-generation
audits:

  1. passage-level copying of the source (copyright / "extraction not
     extraction" claim breaks),
  2. fabricated or cross-book-contaminated quotes presented as the author's
     words (quoted strings that do not appear in the source),
  3. subtle drift that only a human can judge (character attribution, numbers,
     degree words) — surfaced here as a fixed manual checklist.

The tool is advisory: it never modifies files. Exit code 1 only when
passage-level copying is suspected (longest common substring >= --max-longest
normalized characters); unverified quotes are reported as a checklist but do
not fail the run, because distilled skills legitimately coin labels.

Usage:
  python3 tools/check_fidelity.py <source.txt> <skill_dir> [--min-n 12]
      [--max-longest 50] [--json PATH]

The source text may contain ``<<<PAGE n>>>`` markers; matches are then
reported with page numbers for easy lookup in the original book.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Sequence

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_SKILL_FILES = 1_000

_QUOTE_PATTERNS = (
    re.compile(r"“([^“”\n]{2,120})”"),
    re.compile(r"「([^「」\n]{2,120})」"),
    re.compile(r"\"([^\"\n]{2,120})\""),
)
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_PAGE_MARK = re.compile(r"<<<PAGE (\d+)>>>")

MANUAL_CHECKLIST = (
    "Manual verification checklist (an automated diff cannot judge these):",
    "  1. Character attribution — first-person anecdotes in the source must not",
    "     be re-attributed to recurring third-person characters (and vice versa).",
    "  2. Numbers and names — every figure, date and proper noun added or kept",
    "     by distillation should be spot-checked against the source.",
    "  3. Cross-book contamination — named frameworks that sound plausible may",
    "     belong to a sibling book by the same author; grep the source.",
    "  4. Quote fidelity — every quoted string below marked VERIFY either gets a",
    "     verbatim source match or loses its quotation marks (paraphrase).",
)


def normalize(text: str) -> str:
    """Keep CJK ideographs and alphanumerics; drop whitespace/punctuation."""
    out = []
    for ch in text:
        if ch.isspace():
            continue
        if "\u4e00" <= ch <= "\u9fff":
            out.append(ch)
        elif ch.isascii() and ch.isalnum():
            out.append(ch.lower())
    return "".join(out)


def _page_of(page_starts: Sequence[tuple[int, int]], offset: int) -> int:
    page = -1
    for number, start in page_starts:
        if start <= offset:
            page = number
        else:
            break
    return page


def _skill_files(skill_dir: Path) -> list[Path]:
    root = skill_dir.expanduser()
    if root.name.lower() == "skill.md" and root.is_file():
        root = root.parent
    if not root.is_dir():
        raise SystemExit(f"ERROR skill directory not found: {root}")
    master = root / "SKILL.md"
    if not master.is_file():
        raise SystemExit(f"ERROR SKILL.md missing under: {root}")
    files = {master}
    for name in ("glossary.md", "patterns.md", "cheatsheet.md"):
        candidate = root / name
        if candidate.is_file():
            files.add(candidate)
    chapters = root / "chapters"
    if chapters.is_dir():
        files.update(chapters.glob("*.md"))
    examples = root / "examples"
    if examples.is_dir():
        files.update(examples.glob("*.md"))
    ordered = sorted(files, key=lambda p: p.relative_to(root).as_posix().lower())
    if len(ordered) > MAX_SKILL_FILES:
        raise SystemExit(f"ERROR too many markdown files: {len(ordered)}")
    for path in ordered:
        if path.stat().st_size > MAX_FILE_BYTES:
            raise SystemExit(f"ERROR file too large: {path.name}")
    total = sum(p.stat().st_size for p in ordered)
    if total > MAX_TOTAL_BYTES:
        raise SystemExit("ERROR combined markdown exceeds scan limit")
    return ordered


def _skill_texts(files: Iterable[Path], root: Path) -> list[tuple[str, str]]:
    texts = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        texts.append((relative, path.read_text(encoding="utf-8-sig")))
    return texts


def longest_common_passages(
    book_norm: str,
    page_starts: Sequence[tuple[int, int]],
    skill_texts: Sequence[tuple[str, str]],
    min_n: int,
    limit: int,
) -> list[dict]:
    """Maximal common substrings (>= min_n normalized chars), deduped."""
    from collections import defaultdict

    index: dict[str, list[int]] = defaultdict(list)
    for pos in range(len(book_norm) - min_n + 1):
        index[book_norm[pos : pos + min_n]].append(pos)

    spans: list[dict] = []
    for relative, text in skill_texts:
        skill_norm = normalize(text)
        i = 0
        while i <= len(skill_norm) - min_n:
            gram = skill_norm[i : i + min_n]
            positions = index.get(gram)
            if not positions:
                i += 1
                continue
            best = min_n
            for bpos in positions[:5]:
                length = min_n
                while (
                    i + length < len(skill_norm)
                    and bpos + length < len(book_norm)
                    and skill_norm[i + length] == book_norm[bpos + length]
                ):
                    length += 1
                if length > best:
                    best = length
            if spans and spans[-1]["file"] == relative and spans[-1]["_end"] >= i:
                # extend the previous span instead of reporting an overlap
                prev = spans[-1]
                prev["_end"] = max(prev["_end"], i + best)
                prev["length"] = max(prev["length"], prev["_end"] - prev["_start"])
            else:
                spans.append(
                    {
                        "file": relative,
                        "length": best,
                        "text": skill_norm[i : i + best],
                        "page": _page_of(page_starts, positions[0]),
                        "_start": i,
                        "_end": i + best,
                    }
                )
            i += best
    spans.sort(key=lambda s: -s["length"])
    trimmed = []
    for span in spans[:limit]:
        span.pop("_start", None)
        span.pop("_end", None)
        trimmed.append(span)
    return trimmed


def quoted_claims(
    skill_texts: Sequence[tuple[str, str]], book_norm: str
) -> tuple[list[dict], list[dict]]:
    """Split quoted strings into source-verified vs needing manual verification."""
    verified: list[dict] = []
    unverified: list[dict] = []
    for relative, text in skill_texts:
        body = _FENCE.sub(" ", text)
        for line_number, line in enumerate(body.splitlines(), start=1):
            for pattern in _QUOTE_PATTERNS:
                for quote in pattern.findall(line):
                    entry = {
                        "file": relative,
                        "line": line_number,
                        "quote": quote.strip(),
                    }
                    if normalize(quote) and normalize(quote) in book_norm:
                        verified.append(entry)
                    else:
                        unverified.append(entry)
    # drop verified entries that also appear in unverified (mixed quote styles)
    seen = {v["quote"] for v in verified}
    unverified = [u for u in unverified if u["quote"] not in seen]
    return verified, unverified


def check_fidelity(source_path: Path, skill_dir: Path, min_n: int, max_longest: int,
                   limit: int) -> dict:
    raw = source_path.expanduser().read_text(encoding="utf-8-sig")
    page_starts = [(int(m.group(1)), m.start()) for m in _PAGE_MARK.finditer(raw)]
    book_norm = normalize(raw)
    if len(book_norm) < min_n:
        raise SystemExit("ERROR source text too short to scan")

    root = skill_dir.expanduser()
    if root.name.lower() == "skill.md" and root.is_file():
        root = root.parent
    files = _skill_files(root)
    texts = _skill_texts(files, root)

    passages = longest_common_passages(book_norm, page_starts, texts, min_n, limit)
    verified, unverified = quoted_claims(texts, book_norm)
    longest = passages[0]["length"] if passages else 0
    return {
        "longest": longest,
        "passage_count": len(passages),
        "passages": passages,
        "verified_quotes": len(verified),
        "unverified_quotes": unverified,
        "threshold": max_longest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="Source book plain text (<<<PAGE n>>> markers optional)")
    parser.add_argument("skill_dir", help="Generated skill directory or its SKILL.md")
    parser.add_argument("--min-n", type=int, default=12,
                        help="minimum normalized chars for a common substring (default 12)")
    parser.add_argument("--max-longest", type=int, default=50,
                        help="longest tolerated common substring before WARN (default 50)")
    parser.add_argument("--limit", type=int, default=25,
                        help="how many longest passages to report (default 25)")
    parser.add_argument("--json", dest="json_path", default=None,
                        help="optional path to write the full report as JSON")
    args = parser.parse_args(argv)

    report = check_fidelity(
        Path(args.source), Path(args.skill_dir), args.min_n, args.max_longest, args.limit
    )

    print(f"Fidelity check: {report['passage_count']} common passage(s), "
          f"longest {report['longest']} normalized chars (threshold {report['threshold']})")
    for span in report["passages"][:10]:
        page = f"p{span['page']}" if span["page"] > 0 else "source"
        print(f"  [{span['length']:4d}] {page:>5} {span['file']}: {span['text'][:48]}")
    if report["longest"] >= report["threshold"]:
        print("WARN longest common substring at or above threshold — review for "
              "passage-level copying of the source.")
    else:
        print("PASS no passage-level copying detected (single-sentence overlaps only).")

    print(f"\nQuoted strings: {report['verified_quotes']} verified verbatim in source, "
          f"{len(report['unverified_quotes'])} need manual verification:")
    for entry in report["unverified_quotes"][:20]:
        print(f"  VERIFY {entry['file']}:{entry['line']} “{entry['quote'][:56]}”")
    if len(report["unverified_quotes"]) > 20:
        print(f"  ... and {len(report['unverified_quotes']) - 20} more")
    print()
    print("\n".join(MANUAL_CHECKLIST))

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"\nFull report written to {args.json_path}")

    return 1 if report["longest"] >= report["threshold"] else 0


if __name__ == "__main__":
    sys.exit(main())
