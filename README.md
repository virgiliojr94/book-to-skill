<h1 align="center">📚 book-to-skill for Codex</h1>

<p align="center">
  <strong>Turn any technical book or document into a Codex skill — ready to study, reference, and use while you work.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Codex-Skill-black?style=for-the-badge" alt="Codex Skill">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="Supported formats: PDF, EPUB, DOCX, Markdown, HTML, RTF, MOBI">
  <img src="https://img.shields.io/badge/Codex%20effort-high-orange?style=for-the-badge" alt="Codex effort: high">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
</p>

<p align="center">
  <a href="#-why">Why</a> ·
  <a href="#-what-it-generates">What it generates</a> ·
  <a href="#-usage">Usage</a> ·
  <a href="#-requirements">Requirements</a> ·
  <a href="#-how-it-works">How it works</a> ·
  <a href="#-faq">FAQ</a> ·
  <a href="#-install">Install</a>
</p>

---

## 🤔 Why

You buy a great technical book. You read it once. Three months later you can't remember chapter 7 existed.

The usual workarounds don't help:
- 📄 "Let me just search the PDF" → you get a list of pages, not answers
- 🧠 "I'll ask Codex about this book" → it either hallucinates or says it doesn't have the content
- 📝 "I'll take notes as I read" → you end up with a 200-line doc you never open again

**book-to-skill solves this by turning the book into a structured skill Codex loads on demand.**

Once installed, ask Codex in plain language: "Use the `your-book-slug` skill to explain replication." Codex reads the right chapter and answers from the actual content. No hallucination. No digging through PDFs. The book becomes part of your workflow.

---

## 📦 What it generates

Running the `book-to-skill` skill on `your-book.pdf` (or `.epub`) creates a full Codex skill at `~/.codex/skills/<slug>/`:

| File | Purpose | Size |
|------|---------|------|
| `SKILL.md` | Core mental models + chapter index | ~4,000 tokens |
| `chapters/ch01-*.md` … | One file per chapter, loaded on-demand | ~1,000 tokens each |
| `glossary.md` | Every key term, alphabetically sorted with chapter refs | ~1,500 tokens |
| `patterns.md` | All techniques, algorithms, and design patterns | ~2,000 tokens |
| `cheatsheet.md` | Decision tables and quick-reference rules | ~1,000 tokens |

**Chapter files are loaded on-demand** — they don't count against the skill budget until you ask about that topic.

---

## 🚀 Usage

Ask Codex to use the skill in natural language.

Supported document formats: PDF, EPUB, DOCX, TXT, Markdown, reStructuredText, AsciiDoc, HTML, RTF, MOBI/AZW/AZW3.

**Examples:**

```text
Use the book-to-skill skill to convert ~/Downloads/designing-data-intensive-applications.pdf into a Codex skill.

Use the book-to-skill skill to convert ~/books/clean-code.epub into a Codex skill named clean-code.

Use the book-to-skill skill to convert /tmp/ddd-evans.pdf into a Codex skill named domain-driven-design.
```

After the skill is created, use it like any other Codex skill:

```text
Use the designing-data-intensive-apps skill to load the book's core mental models.
Use the designing-data-intensive-apps skill to explain replication.
Use the designing-data-intensive-apps skill to dive into chapter 5.
Use the designing-data-intensive-apps skill to list the available chapters.
```

Claude Code and Amp can use the same generated skill files through their compatible skill workflows. If you already have a `/book-to-skill` slash command wired up there, it can remain as a compatibility path; Codex usage is plain natural language by default.

---

## 🔧 Requirements

The extractor tries tools in order per format and uses the first available. If nothing is installed, it tells you which command to run. In a Codex session, dependency installation should happen only after Codex asks for your approval and you confirm the command. Plain text, Markdown, reStructuredText and AsciiDoc need no extra deps.

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
PDF or EPUB
     │
     ▼
Step 1.5 — "Technical or text-heavy book?"
     │
     ├── technical → Docling  (tables + code blocks as markdown, ~1.5s/page)
     └── text      → pdftotext → PyPDF2 → pdfminer  (instant)
     │
     ▼
scripts/extract.py --mode <technical|text>
  EPUB → ebooklib → stdlib zipfile
     │
     ├── /tmp/book_skill_work/full_text.txt
     └── /tmp/book_skill_work/metadata.json
               │
               ▼
          Codex analyzes structure
          (title, author, chapters, ToC)
               │
               ▼
          Generates per-chapter summaries  (800–1,200 tokens each)
          technical → includes Code Examples + Reference Tables sections
          Generates glossary, patterns, cheatsheet
          Generates master SKILL.md with core mental models
               │
               ▼
          ~/.codex/skills/<slug>/  ✅ written
          /tmp/book_skill_work/     🗑️  cleaned up
```

**Extraction benchmark** (103-page technical book, CPU only):

| Method | Time | Tokens | Tables | Code blocks |
|--------|------|--------|--------|-------------|
| pdftotext | 0.1s | 27K | 0 | 0 |
| Docling | 164s | 27K (+1.2%) | 48 | 36 |

<details>
<summary>Design principles (click to expand)</summary>

1. **Density over completeness** — a 1,000-token summary beats a 10,000-token excerpt
2. **Practitioner voice** — "Use X when Y", not "The book explains X"
3. **Front-loaded SKILL.md** — compaction keeps the first ~5,000 tokens; the most important content comes first
4. **On-demand chapters** — the topic index tells Codex which file to read; chapters load only when needed
5. **Never raw text** — always synthesize, summarize, extract signal from the source

</details>

---

## ❓ FAQ

**"Can't I just dump the PDF/EPUB into a Codex conversation?"**

You can — but every conversation will burn that token budget upfront. A 400-page book is ~200K tokens. With a skill, only the chapters relevant to your question load. The rest stays on disk until you need it.

More importantly: raw text injection is retrieval. A skill is reasoning. When you load a chapter file, Codex isn't searching for keyword matches — it's working with pre-extracted named frameworks, principles, and mental models structured for application, not for reading.

---

**"Isn't this just RAG?"**

RAG works at query time: chunk the book → embed everything → find similar vectors → inject into prompt. It's optimized for "find me the part that talks about X."

book-to-skill works at compile time: one deep analysis run extracts the author's actual frameworks, names them, describes when to use each, captures the anti-patterns. The output is structure the author spent years building — not a similarity search over their sentences.

RAG answers: *"here are chunks close to your query."*  
A skill answers: *"here are the 12 frameworks this author built, ready to reason with."*

For searching across 50+ books, RAG wins. For going deep on one book and using its frameworks while you work, a skill wins.

---

**"Popular books are already in model training data. Why bother?"**

For widely-known books (Clean Code, DDIA, Pragmatic Programmer), Codex may have general knowledge — but it's compressed, averaged across the entire internet's discussion of the book, and may hallucinate specific quotes or chapter locations.

book-to-skill works from your actual copy. Every framework name, every anti-pattern list, every chapter number is grounded in the text you provided. No training data drift, no hallucinated chapter titles.

It also shines for books Codex doesn't know at all: niche technical references, internal company documentation, recent publications, translated works.

---

**"NotebookLM handles multiple books better."**

Absolutely true — if your workflow is "I have 80 books and I want to search across all of them," NotebookLM is the right tool.

book-to-skill is built for a different job: you want to go deep on one book and have its frameworks embedded in your coding or writing workflow, not in a separate browser tab. It's less "library search" and more "the author is sitting next to you while you work."

---

## 📥 Install

Ask Codex to install the skill from this fork:

```text
Install the book-to-skill skill from https://raw.githubusercontent.com/JasonHe/book-to-skill/master/SKILL.md
```

Or manually:

```bash
mkdir -p ~/.codex/skills/book-to-skill/scripts

curl -L -o ~/.codex/skills/book-to-skill/SKILL.md \
  https://raw.githubusercontent.com/JasonHe/book-to-skill/master/SKILL.md

curl -L -o ~/.codex/skills/book-to-skill/scripts/extract.py \
  https://raw.githubusercontent.com/JasonHe/book-to-skill/master/scripts/extract.py
```

Then in any Codex session:

```text
Use the book-to-skill skill to convert ~/path/to/your-book.pdf into a Codex skill named my-book.

Use the book-to-skill skill to convert ~/path/to/your-book.epub into a Codex skill.
```

For Claude Code or Amp, keep using their compatible skill installation location and invocation style. The generated `SKILL.md`, `chapters/`, `glossary.md`, `patterns.md`, and `cheatsheet.md` files are portable.

---

## 📁 Repository structure

```
book-to-skill/
├── SKILL.md              # Codex skill definition + step-by-step instructions
├── scripts/
│   └── extract.py        # PDF + EPUB extraction (pdftotext / PyPDF2 / pdfminer / ebooklib / zipfile)
└── README.md             # This file
```

---

## License

MIT

## Star History

<a href="https://www.star-history.com/?repos=JasonHe%2Fbook-to-skill&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=JasonHe/book-to-skill&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=JasonHe/book-to-skill&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=JasonHe/book-to-skill&type=date&legend=top-left" />
 </picture>
</a>
