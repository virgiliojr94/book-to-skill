<h1 align="center">📚 book-to-skill</h1>

<p align="center">
  <strong>Turn any technical book, document folder, or collection of sources into a unified agent skill — ready to study, reference, and use while you work in GitHub Copilot CLI, Amp, or Claude Code.</strong>
</p>

<p align="center">
  <a href="https://github.com/virgiliojr94/book-to-skill/releases"><img src="https://img.shields.io/github/v/release/virgiliojr94/book-to-skill?style=for-the-badge&color=blueviolet" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/Agent_Skills-Open_Standard-blueviolet?style=for-the-badge" alt="Agent Skills standard">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="Formats supported">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
</p>

[![Trending Repos](https://trending-repos.com/badge/virgiliojr94/book-to-skill.svg)](https://trending-repos.com/repositories/virgiliojr94/book-to-skill)

<p align="center">
  <a href="#-why">Why</a> ·
  <a href="#-what-it-generates">What it generates</a> ·
  <a href="#-beyond-books">Beyond books</a> ·
  <a href="#-usage">Usage</a> ·
  <a href="#-requirements">Requirements</a> ·
  <a href="#-how-it-works">How it works</a> ·
  <a href="#-the-discovery-loop-tax">Discovery Loop Tax</a> ·
  <a href="#-faq">FAQ</a> ·
  <a href="#-install">Install</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="docs/PERFORMANCE.md">Performance</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a>
</p>

---

## 🤔 Why

You buy a great technical book. You read it once. Three months later you can't remember chapter 7 existed.

The usual workarounds don't help:
- 📄 "Let me just search the PDF" → you get a list of pages, not answers
- 🧠 "I'll ask the agent about this book" → it either hallucinates or says it doesn't have the content
- 📝 "I'll take notes as I read" → you end up with a 200-line doc you never open again

**book-to-skill solves this by turning the book into a structured skill your agent loads on demand.**

Once installed, you just type `/your-book-slug replication` and the agent reads the right chapter and answers from the actual content. No hallucination. No digging through PDFs. The book becomes part of your workflow.

Works with any host that supports the open [Agent Skills](https://github.com/agentskills/agentskills) standard — GitHub Copilot CLI, Amp, and Claude Code all read the same `SKILL.md` format.

---

## 📦 What it generates

Running `/book-to-skill your-book.pdf` (or a folder, glob, or list of files) creates a full skill in your agent's skills directory (`~/.copilot/skills/<slug>/` for Copilot CLI, `~/.agents/skills/<slug>/` for Amp or cross-agent, `~/.claude/skills/<slug>/` for Claude Code):

| File | Purpose | Size |
|------|---------|------|
| `SKILL.md` | Core mental models + chapter index | ~4,000 tokens |
| `chapters/ch01-*.md` … | One file per chapter, loaded on-demand | ~1,000 tokens each |
| `glossary.md` | Every key term, alphabetically sorted with chapter refs | ~1,500 tokens |
| `patterns.md` | All techniques, algorithms, and design patterns | ~2,000 tokens |
| `cheatsheet.md` | Decision tables and quick-reference rules | ~1,000 tokens |

**Chapter files are loaded on-demand** — they don't count against the skill budget until you ask about that topic.

---

## 🏢 Beyond books

The name says "book", but the input is any structured prose. The same extraction works on knowledge you own and re-read constantly:

- **Internal documentation** — architecture decision records, runbooks, onboarding guides. Fold a whole `docs/` folder into one skill and ask it while you code.
- **Brand & design systems** — voice guidelines, tone-of-voice docs, component principles. Turn a brand book into a skill your team queries instead of skimming a 60-page PDF.
- **Research clusters** — a stack of papers plus your own notes, merged into a single unified skill and updated as new material lands (see [Update / fold-in](#-usage)).
- **Specs & standards** — RFCs, API contracts, compliance docs you reference but never memorize.

If you re-open a document often enough to wish you'd memorized it, it's a candidate.

---

## 🚀 Usage

```
/book-to-skill <path-to-document-folder-or-glob>... [skill-name-slug]
```

Supported document formats: PDF, EPUB, DOCX, TXT, Markdown, reStructuredText, AsciiDoc, HTML, RTF, MOBI/AZW/AZW3.

**Examples:**

```bash
# Process several files together into a unified skill
/book-to-skill ~/papers/paper1.pdf ~/notes/export.txt unified-research

# Process all supported files in a folder together
/book-to-skill ~/workspace/project-docs/ project-knowledge

# Process files matching a glob pattern
/book-to-skill "~/books/*.epub" my-library

# Update/fold new material into an existing skill folder
/book-to-skill ~/articles/new-paper.pdf ~/.claude/skills/project-knowledge
```

After the skill is created, use it like any other agent skill:

```bash
/designing-data-intensive-apps                  # load core mental models
/designing-data-intensive-apps replication      # find and explain a topic
/designing-data-intensive-apps ch05             # dive into chapter 5
/designing-data-intensive-apps "what chapters do you have?"
```

In GitHub Copilot CLI you may need to run `/skills reload` after the file is written so the new skill appears in `/skills list`. Claude Code and Amp pick it up on the next session.

---

## 🔧 Requirements

The extractor tries tools in order per format and uses the first available. If nothing is installed, it tells you which command to run. Plain text, Markdown, reStructuredText and AsciiDoc need no extra deps.

> **Check your setup in one command:** `python3 scripts/extract.py --check` prints which extractors are installed for every format and the exact command to install anything missing — no file needed.

**PDF — choose by book type:**

| Book type | Tool | Install | Speed |
|-----------|------|---------|-------|
| Text-heavy (prose, few tables) | `pdftotext` (poppler) | `sudo apt install poppler-utils` | ⚡ instant |
| Text-heavy fallback | `PyPDF2` | `pip3 install PyPDF2` | ⚡ instant |
| Text-heavy fallback | `pdfminer.six` | `pip3 install pdfminer.six` | ⚡ instant |
| **Technical (code, tables, formulas)** | **`docling`** | `pip3 install docling` | ~1.5s/page |

> Before extraction begins, the skill asks you whether the book is **technical** or **text-heavy** and picks the right tool automatically. Docling preserves markdown tables and code blocks; pdftotext is faster for prose-only books.

**EPUB:**

| Tool | Install | Quality |
|------|---------|---------|
| `ebooklib` + `beautifulsoup4` | `pip3 install ebooklib beautifulsoup4` | ⭐⭐⭐ Best |
| stdlib `zipfile` | built-in — no install needed | ⭐⭐ Always available |

**Other formats:**

| Format | Tool | Install |
|--------|------|---------|
| DOCX | `python-docx` (fallback: stdlib ZIP/XML) | `pip3 install python-docx` |
| HTML | `beautifulsoup4` (fallback: stdlib `html.parser`) | `pip3 install beautifulsoup4` |
| RTF | `striprtf` (fallback: regex) | `pip3 install striprtf` |
| MOBI / AZW / AZW3 | Calibre `ebook-convert` (external app, not pip) | https://calibre-ebook.com/download |
| TXT / Markdown / reStructuredText / AsciiDoc | built-in | — |

---

## ⚙️ How it works

```
One file · a folder · a glob · a list of paths
     │
     ▼
Step 1.5 — "Technical or text-heavy book?"
     │
     ├── technical → Docling  (tables + code blocks as markdown, ~1.5s/page)
     └── text      → pdftotext → PyPDF2 → pdfminer  (instant)
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

## 🧾 The Discovery Loop Tax

A PDF-reading agent doesn't just read — it *navigates*. Ask it one question and it
fetches the table of contents, notices a term it can't define, pulls more pages,
backtracks. Every one of those hops lands in the conversation history and gets
**re-processed on every subsequent turn**. To stay inside its budget, a sub-agent
is then forced to compress what it read at brutal ratios, handing the main agent a
**degraded summary it can't fact-check** against the source.

book-to-skill pays the navigation cost **once, at compile time**. At runtime the
assistant loads a small resident core plus the one pre-compiled chapter it needs —
no discovery loop, no compress-to-fit, and the full extracted source stays on disk
for verification.

**Measured, not asserted.** Running [`tools/discovery_tax.py`](tools/discovery_tax.py)
on three real books — tokens entering context to answer a single targeted question
(book-to-skill = resident core + one compiled chapter ≈ 5,000 tokens):

| Book (size) | Context-dump | Discovery loop | book-to-skill | vs dump / loop |
|-------------|-------------:|---------------:|--------------:|:--------------:|
| Think Python 2 (119K, small chapters) | 119,264 | 12,152 | ~5,000 | 24× / **2.4×** |
| Working Backwards (175K, medium chapters) | 175,253 | 33,444 | ~5,000 | 35× / 6.7× |
| AI Engineering (256K, large chapters) | 256,287 | 77,866 | ~5,000 | 51× / **15.6×** |

The advantage **scales with chapter size**: against a context-dump it's consistently
24–51× (and that cost recurs *every turn*); against a one-time discovery loop it
ranges from a modest 2.4× on a book of small chapters to 15.6× on one of large
chapters. Reproduce on your own book:

```bash
python3 tools/discovery_tax.py --full-text /tmp/book_skill_work/full_text.txt --target-chapter 5
```

> **Honest caveats:** (1) the discovery figures are a one-time cost and a *model*
> using the book's real ToC/chapter sizes — a well-tuned agent lands nearer the best
> case; the context-dump cost, by contrast, recurs on **every** turn. (2) The tool
> needs explicit `Chapter N` / `Capítulo N` headings to segment a book; titles-only
> or roman-numeral books (and EPUBs extracted without `ebooklib`) won't segment
> cleanly. book-to-skill wins when you return to the knowledge repeatedly; for a
> single one-off read, a plain PDF agent is fine.

---

## ❓ FAQ

**"Can't I just dump the PDF/EPUB into my Claude project context?"**

You can — but every conversation will burn that token budget upfront. A 400-page book is ~200K tokens. With a skill, only the chapters relevant to your question load — typically a SKILL.md core (~4K) plus the one chapter you asked about (~1K). The rest stays on disk until you need it.

The economics are amortization, not size. Pasting the book pays the full token bill **on every turn of every session, forever**. book-to-skill pays the extraction cost **once** and every future conversation loads only the slice it needs. The bigger your context window, the more this matters — a large window makes the dump *possible*, not *cheap*.

More importantly: raw text injection is retrieval. A skill is reasoning. When you load a chapter file, Claude isn't searching for keyword matches — it's working with pre-extracted named frameworks, principles, and mental models structured for application, not for reading.

---

**"Claude has a 1M-token context window now — can't I just keep the whole book loaded?"**

A bigger window changes what *fits*, not what's *smart*. Three reasons it isn't a substitute:

- **You pay per token, per call.** A 1M window doesn't make those tokens free — it makes a large, recurring bill possible. The skill loads kilobytes, not megabytes.
- **Recall degrades with fill.** Models lose precision retrieving a specific fact buried in a near-full context ("lost in the middle"). A 1K curated chapter beats 200K of raw prose for answering one question.
- **Window ≠ structure.** A full book in context is still raw text the model must re-parse every turn. The skill ships pre-extracted frameworks — reasoning, not retrieval.

Use the big window for what it's good at: a one-off pass over material you'll never need again. Use a skill for knowledge you'll reach for repeatedly.

---

**"Isn't this just RAG?"**

RAG works at query time: chunk the book → embed everything → find similar vectors → inject into prompt. It's optimized for "find me the part that talks about X."

book-to-skill works at compile time: one deep analysis run extracts the author's actual frameworks, names them, describes when to use each, captures the anti-patterns. The output is structure the author spent years building — not a similarity search over their sentences.

RAG answers: *"here are chunks close to your query."*  
A skill answers: *"here are the 12 frameworks this author built, ready to reason with."*

Pick by shape of the job:

- **Wide and shallow** — a library of dozens of books, "find the part that mentions X" → a RAG tool (e.g. CandleKeep) wins.
- **Narrow and deep** — one book or a tight cluster of related sources, frameworks you apply while you work → book-to-skill wins.

They're complementary, not competing: RAG indexes a shelf, book-to-skill masters a spine.

---

**"Popular books are already in Claude's training data. Why bother?"**

For widely-known books (Clean Code, DDIA, Pragmatic Programmer), Claude has general knowledge — but it's compressed, averaged across the entire internet's discussion of the book, and may hallucinate specific quotes or chapter locations.

book-to-skill works from your actual copy. Every framework name, every anti-pattern list, every chapter number is grounded in the text you provided. No training data drift, no hallucinated chapter titles.

It also shines for books Claude doesn't know at all: niche technical references, internal company documentation, recent publications, translated works.

---

**"NotebookLM handles multiple books better."**

Absolutely true — if your workflow is "I have 80 separate books and I want to search across all of them," NotebookLM is the right tool.

book-to-skill is built for a different job: you want to go deep on a specific topic or library, having multiple related documents (papers, chapters, notes) folded into a single unified skill, and even updating it over time as new material arrives! This integrates your customized knowledge base right into your coding or writing workflow, rather than in a separate browser tab.

---

## 📥 Install

The skill follows the open [Agent Skills](https://github.com/agentskills/agentskills) standard, so a single install works for any compatible host.

**GitHub Copilot CLI** (personal skill):

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.copilot/skills/book-to-skill
# then, in a `copilot` session:
/skills reload
/skills info book-to-skill
```

Or the cross-agent path that Copilot CLI and Amp both discover:

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.agents/skills/book-to-skill
```

**Claude Code**:

Copy this into your Claude Code session:

```
Install book-to-skill: https://raw.githubusercontent.com/virgiliojr94/book-to-skill/master/SKILL.md
```

Or manually using standard `git clone` (ensures modular engine files are fetched correctly):

```bash
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
```

Then in any agent session:

```bash
/book-to-skill ~/path/to/your-book.pdf
# or
/book-to-skill ~/path/to/your-book.epub
```

---

## 📁 Repository structure

```
book-to-skill/
├── SKILL.md              # Skill definition + step-by-step instructions (the generator spec)
├── scripts/
│   ├── extract.py        # Thin entrypoint wrapper
│   └── extractor/        # Modular extraction package
│       ├── config.py     # Extensions, paths, dependency constants
│       ├── dependencies.py  # optional-dep probing + --check
│       ├── exceptions.py # ExtractionError (per-source failures, batch-safe)
│       ├── utils.py      # CLI parsing, multi-source resolution, chapter detection, runner
│       └── parsers/      # Format-specific parsers (pdf, epub, docx, html, rtf, calibre, text)
├── tools/
│   ├── discovery_tax.py  # measures token cost vs context-dump / discovery loop
│   └── validate_skill.py # checks a generated SKILL.md against host rules (--lens claude|copilot|amp)
├── tests/                # pytest suite (extraction, detection, discovery tax)
├── docs/
│   ├── PERFORMANCE.md    # measured benchmarks, discovery tax, cost
│   └── ARCHITECTURE.md   # pipeline + component map
├── CHANGELOG.md          # release history (semver)
├── CONTRIBUTING.md       # dev setup, PR conventions, release process
├── SECURITY.md           # vulnerability reporting
└── README.md             # This file
```

---

## ⚖️ Copyright & fair use

book-to-skill ships **no book content** — not a single page. It's a converter you point at files you already own.

- **Processing is local.** Extraction and analysis run on your machine. Your files are never uploaded by this tool. (If your agent's model runs in the cloud, the text you feed it follows that provider's normal data terms — same as any prompt.)
- **You use your own copy.** Bring a book you bought, docs your company owns, or papers you have the right to read.
- **The output is your notes.** A generated skill is a structured, synthesized derivative — framework names, definitions, takeaways — not a reproduction of the text. The skill explicitly never copies raw passages (see Quality Rule #7). Treat it like handwritten study notes: yours, for personal use.
- **Don't redistribute.** Publishing or sharing a generated skill of a copyrighted work can infringe the rights holder. Keep skills of third-party books private. Internal docs, your own writing, and openly-licensed material are fine to share within the bounds of their license.

When in doubt, follow the license or terms of the source document. This project is a tool; how you use it is on you.

---

## License

MIT — applies to the converter (code + skill definition) in this repository, **not** to any book or document you process with it.

## Star History

<a href="https://www.star-history.com/?repos=virgiliojr94%2Fbook-to-skill&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=virgiliojr94/book-to-skill&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=virgiliojr94/book-to-skill&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=virgiliojr94/book-to-skill&type=date&legend=top-left" />
 </picture>
</a>
