#!/usr/bin/env python3
"""
discovery_tax.py — measure the "Discovery Loop Tax".

Quantifies, on a *real* extracted book, how many tokens three strategies put
into an agent's context to answer one targeted question:

  1. context-dump   — the whole book stays resident, re-billed every turn
  2. discovery-loop — a live PDF-reading agent navigates: reads the ToC, then
                      pulls raw chapters until it locates the answer (and, per
                      Kyle Parratt's critique, backtracks for missing
                      definitions). These fetched pages land in history.
  3. book-to-skill  — a small resident SKILL.md core + one pre-compiled chapter
                      loaded on demand.

Honesty notes:
  * Token counts use tiktoken (cl100k_base) when installed, else a
    words/0.75 heuristic (the same constant the extractor uses). The method
    used is printed in the report.
  * The discovery-loop figure is a *model* with stated assumptions, not a
    measurement of a specific agent. It uses the REAL token sizes of the
    book's ToC and chapters, so it is a defensible estimate, not a guess.
  * It reports a best case (ToC + target chapter only) and a loop case
    (ToC + target chapter + one prior chapter for a missing definition).

Usage:
  python3 tools/discovery_tax.py --full-text <full_text.txt> \
      [--skill-dir <skill_folder>] [--target-chapter N] [--core-tokens 4000]
"""

import argparse
import re
import sys
from pathlib import Path

CHAPTER_RE = re.compile(r"^\s*(?:cap[ií]tulo|chapter)\s+\d+\s*$", re.IGNORECASE)
TOC_RE = re.compile(r"^\s*(?:sum[áa]rio|table of contents|contents|[íi]ndice)\s*$",
                    re.IGNORECASE | re.MULTILINE)


def count_tokens(text: str) -> int:
    """Real BPE count via tiktoken if available; else words/0.75 heuristic."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return int(len(text.split()) / 0.75)


def token_method() -> str:
    try:
        import tiktoken  # noqa: F401
        return "tiktoken cl100k_base (real BPE)"
    except Exception:
        return "words/0.75 heuristic (tiktoken not installed)"


def split_chapters(text: str) -> list[tuple[str, str]]:
    """Return [(heading, body)] using the same chapter-heading shape the
    extractor's detect_structure looks for. The text before the first heading
    is returned as the leading 'front matter / ToC' segment."""
    lines = text.splitlines()
    segments: list[tuple[str, list[str]]] = [("__front__", [])]
    for line in lines:
        if CHAPTER_RE.match(line):
            segments.append((line.strip(), []))
        segments[-1][1].append(line)
    return [(h, "\n".join(b)) for h, b in segments]


def extract_toc(front_matter: str) -> str:
    """Best-effort slice of the ToC block from the front matter."""
    m = TOC_RE.search(front_matter)
    if not m:
        # No explicit ToC: assume the agent skims the whole front matter.
        return front_matter
    # ToC runs from its heading to the end of the front matter.
    return front_matter[m.start():]


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure the Discovery Loop Tax on a real book.")
    ap.add_argument("--full-text", required=True, help="extractor full_text.txt")
    ap.add_argument("--skill-dir", help="generated skill folder (for SKILL.md + chapter sizes)")
    ap.add_argument("--target-chapter", type=int, default=5,
                    help="1-based chapter index the question is about")
    ap.add_argument("--core-tokens", type=int, default=4000,
                    help="resident SKILL.md core size if --skill-dir not given (design cap)")
    args = ap.parse_args()

    full_text = Path(args.full_text).read_text(encoding="utf-8", errors="ignore")
    total = count_tokens(full_text)

    segs = split_chapters(full_text)
    front = segs[0][1]
    chapters = segs[1:]  # [(heading, body)]
    if not chapters:
        print("No chapters detected — cannot model discovery.", file=sys.stderr)
        return 1

    toc = extract_toc(front)
    toc_tok = count_tokens(toc)

    n = max(1, min(args.target_chapter, len(chapters)))
    target_body = chapters[n - 1][1]
    target_raw = count_tokens(target_body)
    prior_raw = count_tokens(chapters[n - 2][1]) if n >= 2 else 0

    # book-to-skill resident cost
    if args.skill_dir:
        sd = Path(args.skill_dir)
        skill_md = sd / "SKILL.md"
        core = count_tokens(skill_md.read_text(encoding="utf-8")) if skill_md.exists() else args.core_tokens
        chs = sorted((sd / "chapters").glob("*.md")) if (sd / "chapters").is_dir() else []
        # use the target chapter file if present, else the average of generated chapters
        comp_chapter = None
        for c in chs:
            if re.search(rf"ch0*{n}\b", c.name):
                comp_chapter = count_tokens(c.read_text(encoding="utf-8"))
                break
        if comp_chapter is None and chs:
            comp_chapter = sum(count_tokens(c.read_text(encoding="utf-8")) for c in chs) // len(chs)
        comp_chapter = comp_chapter or 1000
        core_label = "measured SKILL.md" if skill_md.exists() else "design cap"
    else:
        core = args.core_tokens
        comp_chapter = 1000
        core_label = "design cap (no --skill-dir)"

    dump = total
    skill = core + comp_chapter
    disc_best = toc_tok + target_raw
    disc_loop = toc_tok + target_raw + prior_raw

    def ratio(a: int, b: int) -> str:
        return f"{a / b:.1f}x" if b else "n/a"

    print("Discovery Loop Tax — measured on a real book\n")
    print(f"  token method : {token_method()}")
    print(f"  source       : {Path(args.full_text).name}")
    print(f"  chapters      : {len(chapters)} detected")
    print(f"  target        : chapter {n}  ({chapters[n-1][0][:60]})")
    print(f"  book total    : {total:,} tokens\n")

    print("  Cost to answer ONE targeted question (tokens entering context):\n")
    print(f"    context-dump      : {dump:>9,}   (resident, re-billed EVERY turn)")
    print(f"    discovery (best)  : {disc_best:>9,}   ToC ({toc_tok:,}) + raw target chapter ({target_raw:,})")
    print(f"    discovery (loop)  : {disc_loop:>9,}   + 1 prior chapter for a missing definition ({prior_raw:,})")
    print(f"    book-to-skill     : {skill:>9,}   core [{core_label}] ({core:,}) + compiled chapter ({comp_chapter:,})\n")

    print("  book-to-skill advantage:")
    print(f"    vs context-dump   : {ratio(dump, skill)} fewer tokens")
    print(f"    vs discovery best : {ratio(disc_best, skill)} fewer tokens")
    print(f"    vs discovery loop : {ratio(disc_loop, skill)} fewer tokens")
    print("\n  Note: the discovery figures are a model using the book's real ToC/chapter")
    print("  sizes; a single read, not a recurring cost. context-dump recurs every turn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
