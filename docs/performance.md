---
description: "Measured token cost of book-to-skill: 24x-51x fewer tokens than dumping a book into context, the Discovery Loop Tax, and per-book tables you can reproduce."
seo_title: "Performance & Token Cost - book-to-skill Benchmarks"
---

# Performance & Cost

All numbers below are **measured**, not estimated, using `tiktoken` (cl100k_base)
for token counts and `tools/discovery_tax.py` for the discovery model. Reproduce
any of them with the commands shown.

## Extraction (real conversions)

Measured with `pdftotext` (PDF) and `ebooklib` (EPUB):

| Book | Format | Pages | Tokens | Chapters auto-detected |
|------|--------|------:|-------:|-----------------------:|
| Think Python 2 | PDF | 244 | 119K | 19 |
| Working Backwards | PDF | 371 | 175K | 10 |
| Pro Git | PDF | 501 | 229K | — † |
| Moby-Dick | EPUB | — | 301K | 133 |

† Pro Git heads chapters with section titles (no `Chapter N`), so it does not
auto-segment. Moby-Dick's bodies use bare titles, but its Roman-numeral table of
contents is detected (133) — see *Known limitations* in the README.

**Extraction method matters for technical books.** On a 103-page technical PDF:

| Method | Time | Tables | Code blocks |
|--------|-----:|-------:|------------:|
| pdftotext | 0.1s | 0 | 0 |
| Docling (technical mode) | 164s | 48 | 36 |

pdftotext is instant but flattens structure; Docling is ~1.5s/page but preserves
tables and code as markdown. Pick text mode for prose, technical mode for code/tables.

## The Discovery Loop Tax

Tokens entering context to answer **one** targeted question. book-to-skill loads a
resident core (~4K) plus one compiled chapter (~1K) ≈ **5,000 tokens**.

| Book (chapter size) | Context-dump | Discovery loop | book-to-skill | vs dump / loop |
|---------------------|-------------:|---------------:|--------------:|:--------------:|
| Think Python 2 (small) | 119,264 | 12,152 | ~5,000 | 24× / 2.4× |
| Working Backwards (medium) | 175,253 | 33,444 | ~5,000 | 35× / 6.7× |
| AI Engineering (large) | 256,287 | 77,866 | ~5,000 | 51× / 15.6× |

```bash
python3 tools/discovery_tax.py --full-text /tmp/book_skill_work/full_text.txt --target-chapter 5
```

- The **context-dump** advantage (24–51×) is the strongest claim: that cost recurs on
  *every conversation turn*.
- The **discovery-loop** advantage (2.4–15.6×) is a one-time cost and a model using
  the book's real ToC/chapter sizes; it scales with chapter size.

## Generation cost

One-pass full conversion, estimated from measured tokens (Claude Sonnet 4.5,
\$3 / \$15 per MTok input/output):

| Book | Input | Output | ~Cost |
|------|------:|-------:|------:|
| Think Python 2 | 155K | 28K | \$0.88 |
| Working Backwards | 228K | 19K | \$0.96 |
| Pro Git | 298K | 23K | \$1.23 |
| Moby-Dick | 391K | 17K | \$1.42 |

Roughly **\$1 per book** for a full skill — paid once. Re-reading the same PDF into
context every session costs far more over time (see the Discovery Loop Tax above).

## Generated-skill output quality

A before/after of the adaptive-depth change (`v1.0.0`, #20) on one chapter:

| Artifact | Old spec | New spec |
|----------|---------:|---------:|
| Chapter file (tokens) | 473 | 1,219 |
| Worked example present | no | yes |
| Cheatsheet decision rules | 0 | 32 |
| Cheatsheet keyword/definition lines | 9 | 0 |

The new spec turns the cheatsheet from a glossary into a decision layer and gives
study-depth chapters a reproduced worked example.
