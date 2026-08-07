---
description: "The full book-to-skill walkthrough, Steps 0-10: document extraction, chapter detection, framework mining, depth budgets, and how the agent skill gets assembled."
seo_title: "How book-to-skill Works - Book to Agent Skill, Step by Step"
---

<img align="right" width="180" src="assets/booklin-casting.png" alt="Booklin casting book-to-skill magic">

## ⚙️ How it works

```
One file · a folder · a glob · a list of paths
     │
     ▼
Step 1.5 — "Technical or text-heavy book?"
     │
     ├── technical → Docling  (tables + code blocks as markdown, ~1.5s/page)
     └── text      → pdftotext → pypdf → pdfminer  (instant)
     │
     ▼
scripts/extract.py <paths…> --mode <technical|text>
  per source: PDF → pdftotext/Docling · EPUB → ebooklib → stdlib zipfile · DOCX/HTML/RTF/…
  (one bad source is skipped with a warning; the rest still process)
     │
     ├── /tmp/book_skill_work/full_text.txt   (all sources merged, with source markers)
     └── /tmp/book_skill_work/metadata.json   (aggregated stats + per-source array)
               │
               ▼
          Claude analyzes structure
          (title, author, chapters, ToC — spanning all sources)
          ── or, if targeting an existing skill: folds new content in (Mode 4)
               │
               ▼
          Generates per-chapter summaries  (800–1,200 tokens each)
          technical → includes Code Examples + Reference Tables sections
          Generates glossary, patterns, cheatsheet
          Generates master SKILL.md with core mental models
               │
               ▼
          Skill written to one of:
            ~/.copilot/skills/<slug>/   (GitHub Copilot CLI)
            ~/.agents/skills/<slug>/    (Copilot CLI or Amp, cross-agent)
            ~/.claude/skills/<slug>/    (Claude Code)
          /tmp/book_skill_work/         🗑️  cleaned up
```

**Extraction benchmark** (103-page technical book, CPU only):

| Method | Time | Tokens | Tables | Code blocks |
|--------|------|--------|--------|-------------|
| pdftotext | 0.1s | 27K | 0 | 0 |
| Docling | 164s | 27K (+1.2%) | 48 | 36 |

**Real conversions** (measured: pages, extracted tokens, chapters auto-detected,
estimated one-pass cost on Claude Sonnet 4.5 at \$3/\$15 per MTok):

| Book | Format | Pages | Tokens | Chapters | ~Cost |
|------|--------|------:|-------:|---------:|------:|
| Think Python 2 | PDF | 244 | 119K | 19 | \$0.88 |
| Working Backwards | PDF | 371 | 175K | 10 | \$0.96 |
| Pro Git | PDF | 501 | 229K | — † | \$1.23 |
| Moby-Dick | EPUB | — | 301K | — † | \$1.42 |

† Chapter auto-detection needs explicit `Chapter N` / `Capítulo N` headings. Pro Git
uses section titles and Moby-Dick uses chapter *titles* / roman numerals, so neither
auto-segments — extraction and conversion still work, but you point at sections
manually. A full skill costs roughly **\$1 per book**; far less than re-reading the
PDF every session.

<details>
<summary>Design principles (click to expand)</summary>

1. **Density over completeness** — a 1,000-token summary beats a 10,000-token excerpt
2. **Practitioner voice** — "Use X when Y", not "The book explains X"
3. **Front-loaded SKILL.md** — compaction keeps the first ~5,000 tokens; the most important content comes first
4. **On-demand chapters** — the topic index tells Claude which file to read; chapters load only when needed
5. **Never raw text** — always synthesize, summarize, extract signal from the source

</details>

---


---

[← Back to the README](../README.md)
