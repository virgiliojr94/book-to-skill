---
description: "How book-to-skill is built: a deterministic Python extractor plus a spec-driven agent generator. Pipeline, component map, and the design tradeoffs behind both."
seo_title: "Architecture - How book-to-skill Extracts and Generates"
---

# Architecture

book-to-skill has two halves: a **deterministic extractor** (Python) and a
**spec-driven generator** (the agent following `SKILL.md`). The extractor turns any
document into clean text + metadata; the agent turns that into a structured skill.

```
            ┌─────────────────────────── EXTRACTOR (Python, deterministic) ──┐
 documents  │  scripts/extract.py (shim)  →  book_to_skill/                   │
 (pdf/epub/ │    ├─ cli.py · utils.py   CLI parse · multi-source · runner     │
  docx/...) │    ├─ config.py           supported extensions · paths · deps   │
     │      │    ├─ dependencies.py     optional-dep probing · --check report │
     ▼      │    ├─ sanitize.py         strip invisible/zero-width Unicode    │
 ───────────│    └─ parsers/            pdf · epub · docx · html · rtf ·      │
            │                             calibre · text (best tool, fallback)│
            │  output → <tempdir>/book_skill_work/                            │
            │    full_text.txt   (all sources merged, source-marked)          │
            │    metadata.json   (pages, words, tokens, chapters, ToC)        │
            └────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
            ┌─────────────────────────── GENERATOR (agent, follows SKILL.md) ┐
            │  Step 1.5  ask content type → BOOK_TYPE (technical | text)      │
            │  Step 2/2.5 extract · cost estimate · confirm                   │
            │  Step 2.6  REPL-style probing for large books (grep/sed, no     │
            │            full re-reads)                                        │
            │  Step 3    analyze structure (title, author, chapters, ToC)     │
            │  Step 4    purpose → DEPTH (reference | study)                   │
            │  Step 7    per-chapter summaries (budget = BOOK_TYPE × DEPTH)    │
            │  Step 8    glossary · patterns · cheatsheet (decision layer)    │
            │  Step 9/9.5 SKILL.md core + indexes                             │
            └────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                <SKILLS_HOME>/<slug>/  ← chosen per host:
                  ~/.copilot/skills/   GitHub Copilot CLI
                  ~/.agents/skills/    Copilot CLI or Amp (cross-agent)
                  ~/.claude/skills/    Claude Code
                  .github|.claude|.agents/skills/  project-local
                  SKILL.md         core frameworks + chapter & topic index (~4K)
                  chapters/*.md    on-demand, loaded only when asked
                  glossary.md      terms
                  patterns.md      techniques
                  cheatsheet.md    decision rules / trees / trade-offs / tells
```

## Design principles

1. **Extract structure, not summaries** — named frameworks, decision rules,
   anti-patterns; never raw passages.
2. **Compile-time over runtime** — pay navigation/structuring once; at query time
   load only the relevant chapter. See [Performance & Cost](performance.md).
3. **On-demand chapters** — `SKILL.md` stays small; chapter files cost tokens only
   when read.
4. **Front-loaded `SKILL.md`** — most important content first (compaction truncates
   from the end).
5. **Graceful degradation** — every format has a stdlib fallback; one bad source is
   skipped, not fatal.

## Key components

| Path | Responsibility |
|------|----------------|
| `scripts/extract.py` | thin entrypoint shim → `book_to_skill.cli` (kept so old invocations keep working) |
| `book_to_skill/cli.py`, `utils.py` | CLI parsing, multi-source resolution, chapter/ToC detection, runner |
| `book_to_skill/parsers/` | one module per format (`pdf`, `epub`, `docx`, `html`, `rtf`, `calibre`, `text`) |
| `book_to_skill/config.py` | supported extensions, output paths, dependency map |
| `book_to_skill/dependencies.py` | optional-dependency probing + `--check` |
| `book_to_skill/sanitize.py` | strips zero-width / Unicode-tag-block characters from extracted text (see Security) |
| `tools/discovery_tax.py` | measures token cost vs context-dump / discovery loop |
| `tools/validate_skill.py` | checks a generated SKILL.md against host rules (`--lens claude\|copilot\|amp`) |
| `tools/scan_generated_skill.py` | advisory prompt-injection scan of a generated skill (see Security) |
| `SKILL.md` | the generator spec (Steps 0–10 + fold-in workflow) |

## Security

Untrusted documents flow into an agent's context and then into a generated skill
that later loads into other agents — a document→context supply chain. The hardening
is layered:

- **Extraction sanitization** (`book_to_skill/sanitize.py`) — strips zero-width
  (`U+200B/200C/200D/2060/FEFF`) and the Unicode tag block (`U+E0000–E007F`) from
  every parser's output before metrics or `full_text.txt`, so invisible
  document-borne instructions never reach the agent. Reports the removal count;
  rejects a source with no visible content left.
- **DOCX XXE / Billion-Laughs guard** (`parsers/docx.py`) — rejects any XML part
  declaring a DTD or entities before parsing.
- **Subprocess argument-injection** — file paths are absolutised before reaching
  `pdftotext` / `pdfinfo` / `ebook-convert`, so a `-`-leading filename can't be read
  as a flag.
- **Generated-skill scan** (`tools/scan_generated_skill.py`) — an advisory step in
  the generator (Step 9.5) that flags instruction-override phrases, model-control
  tags, residual invisible Unicode, authority-widening frontmatter, and
  exfiltration-shaped content across the generated `SKILL.md`, `chapters/*.md`,
  `glossary.md`, `patterns.md`, and `cheatsheet.md`. Findings name only the rule and
  file location — never the matched text.
- **CI** — CodeQL, Bandit (gate on HIGH), Zizmor, and dependency CVE review on PRs.

## Extending

- **New format** → add `book_to_skill/parsers/<fmt>.py`, register its extension in
  `config.py`, wire dependency probing in `dependencies.py`, branch in
  `utils.extract_single_file`.
- **New generation behavior** → edit the relevant Step in `SKILL.md`; keep it lean
  and back the change with evidence (see CONTRIBUTING.md).
