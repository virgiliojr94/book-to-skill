<p align="center">
  <img src="docs/assets/banner.webp" alt="Booklin, the book-to-skill wizard, holding an open book whose pages scatter into sparkles that settle into an ordered grid" width="100%">
</p>

<h1 align="center">book-to-skill</h1>

<p align="center">
  <strong>Turn any technical book, document folder, or collection of sources into a unified agent skill — ready to study, reference, and use while you work in GitHub Copilot CLI, Amp, or Claude Code.</strong>
</p>

<p align="center">
  <a href="https://github.com/virgiliojr94/book-to-skill/releases"><img src="https://img.shields.io/github/v/release/virgiliojr94/book-to-skill?style=for-the-badge&color=blueviolet" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/Agent_Skills-Open_Standard-blueviolet?style=for-the-badge" alt="Agent Skills standard">
  <img src="https://img.shields.io/badge/PDF%20%E2%80%A2%20EPUB%20%E2%80%A2%20DOCX%20%E2%80%A2%20MD%20%E2%80%A2%20HTML%20%E2%80%A2%20RTF%20%E2%80%A2%20MOBI-supported-green?style=for-the-badge" alt="Formats supported">
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License">
  <a href="https://github.com/sponsors/virgiliojr94"><img src="https://img.shields.io/github/sponsors/virgiliojr94?style=for-the-badge&color=ea4aaa&logo=githubsponsors&logoColor=white" alt="Sponsor"></a>
</p>

<p align="center">
  <a href="https://trendshift.io/repositories/27038?utm_source=repository-badge&amp;utm_medium=badge&amp;utm_campaign=badge-repository-27038" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/repositories/27038" alt="virgiliojr94%2Fbook-to-skill | Trendshift" width="250" height="55"/></a>
  <a href="https://trendshift.io/repositories/27038?utm_source=trendshift-badge&amp;utm_medium=badge&amp;utm_campaign=badge-trendshift-27038" target="_blank" rel="noopener noreferrer"><img src="https://trendshift.io/api/badge/trendshift/repositories/27038/daily?language=Python" alt="virgiliojr94%2Fbook-to-skill | Trendshift (daily, Python)" width="250" height="55"/></a>
</p>

<p align="center">
  <a href="#-why">Why</a> ·
  <a href="#-what-it-generates">What it generates</a> ·
  <a href="#-beyond-books">Beyond books</a> ·
  <a href="docs/how-it-works.md">How it works</a> ·
  <a href="docs/usage.md">Usage</a> ·
  <a href="docs/install.md">Install</a> ·
  <a href="docs/faq.md">FAQ</a> ·
  <a href="docs/performance.md">Performance</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  <strong>24×–51× fewer tokens than dumping the book into context</strong> to answer one question, measured on real books (<a href="docs/performance.md#the-discovery-loop-tax">how it's measured</a>).
</p>

**How it works, in 3 steps:**

1. **Point** it at a file, folder, or glob — `/book-to-skill ./my-book.pdf`
2. **It distills** the book into a skill — frameworks, decision rules, anti-patterns, and per-chapter files. Structure, not a summary.
3. **Your agent loads it on demand** — ask `/my-book replication` and it reads the right chapter and answers from the real content, no hallucination.

---

## 🤔 Why

<img align="right" width="200" src="docs/assets/booklin.png" alt="Booklin — the book-to-skill mascot, a purple wizard holding a book">

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


## 🧾 The Discovery Loop Tax

A PDF-reading agent doesn't just read — it *navigates*: it re-fetches the ToC, backtracks, and re-processes all of it on every turn. book-to-skill pays that structuring cost **once**, at conversion, so queries stay proportional to the answer — **24×–51× fewer tokens** than dumping the book into context, measured on real books.

📊 **Full methodology, numbers, and per-book tables → [docs/performance.md](docs/performance.md#the-discovery-loop-tax)**

---

## ⚙️ How it works

Two halves: a deterministic Python **extractor** (document → clean text + metadata) and a spec-driven **generator** (your agent follows `SKILL.md` to turn that into a structured skill). On-demand chapter files keep the loaded skill small.

🔧 **Full walkthrough (Steps 0–10, extraction modes, token budgets) → [docs/how-it-works.md](docs/how-it-works.md)**

---

## 🚀 Usage

`/book-to-skill <path|folder|glob> [skill-name]` — plus analyze-only, generate-from-analysis, and update/fold-in modes.

▶️ **All modes and examples → [docs/usage.md](docs/usage.md)**

---

## 📥 Install

```bash
# Agent skill (registers /book-to-skill) — clone into your skills folder:
git clone https://github.com/virgiliojr94/book-to-skill.git ~/.claude/skills/book-to-skill
# (Copilot CLI: ~/.copilot/skills/ · Amp/cross-agent: ~/.agents/skills/)
```

📥 **All hosts, optional extractors, and the standalone CLI → [docs/install.md](docs/install.md)**

---

## ❓ FAQ

Common questions — "why not just dump the PDF?", cost, privacy, non-book inputs, multi-file books.

❓ **Answers → [docs/faq.md](docs/faq.md)**

---

<details>
<summary>🔧 <strong>Requirements</strong></summary>


The extractor tries tools in order per format and uses the first available. If nothing is installed, it tells you which command to run. Plain text, Markdown, reStructuredText and AsciiDoc need no extra deps.

> **Check your setup in one command:** `python3 scripts/extract.py --check` prints which extractors are installed for every format and the exact command to install anything missing — no file needed.

**PDF — choose by book type:**

| Book type | Tool | Install | Speed |
|-----------|------|---------|-------|
| Text-heavy (prose, few tables) | `pdftotext` (poppler) | `sudo apt install poppler-utils` | ⚡ instant |
| Text-heavy fallback | `pypdf` | `pip3 install pypdf` | ⚡ instant |
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


</details>

<details>
<summary>📁 <strong>Repository structure</strong></summary>


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
│   ├── performance.md    # measured benchmarks, discovery tax, cost
│   └── architecture.md   # pipeline + component map
├── CHANGELOG.md          # release history (semver)
├── CONTRIBUTING.md       # dev setup, PR conventions, release process
├── SECURITY.md           # vulnerability reporting
└── README.md             # This file
```

---


</details>

---
## ⚖️ Copyright & fair use

book-to-skill ships **no book content** — not a single page. It's a converter you point at files you already own.

- **Processing is local.** Extraction and analysis run on your machine. Your files are never uploaded by this tool. (If your agent's model runs in the cloud, the text you feed it follows that provider's normal data terms — same as any prompt.)
- **You use your own copy.** Bring a book you bought, docs your company owns, or papers you have the right to read.
- **The output is your notes.** A generated skill is a structured, synthesized derivative — framework names, definitions, takeaways — not a reproduction of the text. The skill explicitly never copies raw passages (see Quality Rule #7). Treat it like handwritten study notes: yours, for personal use.
- **Don't redistribute.** Publishing or sharing a generated skill of a copyrighted work can infringe the rights holder. Keep skills of third-party books private. Internal docs, your own writing, and openly-licensed material are fine to share within the bounds of their license.

When in doubt, follow the license or terms of the source document. This project is a tool; how you use it is on you.

---

## 💖 Sponsors

<img align="right" width="150" src="docs/assets/booklin-celebrating.png" alt="Booklin celebrating">

book-to-skill is free and MIT-licensed, maintained on personal time. If it saves you tokens or study hours, consider sponsoring its upkeep: PR reviews, multilingual fixes, releases, and docs.

**[Become a sponsor → github.com/sponsors/virgiliojr94](https://github.com/sponsors/virgiliojr94)**

Every sponsor is listed in [BACKERS.md](BACKERS.md). Thank you for keeping open, privacy-first tooling alive. ✨

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
