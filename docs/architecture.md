---
description: "How book-to-skill is built: a deterministic Python extractor plus a spec-driven agent generator. Pipeline, component map, and the design tradeoffs behind both."
seo_title: "Architecture - How book-to-skill Extracts and Generates"
---

# Architecture

book-to-skill has two halves: a **deterministic Python core** (`book_to_skill/`,
handling local extraction in Mode 1 and offline MCP payload/session processing
in Mode 2) and a **spec-driven generator** (the agent following `SKILL.md`, plus
the lazy-loaded `references/search-and-read.md` in Mode 2). Both input modes
produce the same structured skill output.

## Mode 1: Local Extraction (Default)

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
            │    pdf_pages.json  (optional, physical-page text evidence)       │
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
                 <SKILLS_HOME>/<slug>/  ← chosen per host + scope:
                  ~/.copilot/skills/   GitHub Copilot CLI (personal)
                  ~/.agents/skills/    Copilot CLI or Amp (cross-agent, personal)
                  ~/.claude/skills/    Claude Code (personal)
                  ~/.openclaw/skills/  OpenClaw (personal, default state only)
                  $HERMES_HOME/skills/<category>/  Hermes Agent (personal)
                  .github/skills/ | .claude/skills/ | .agents/skills/  project-local (any host)
                  .hermes/skills/<category>/                         Hermes project-local
                  skills/                                                   OpenClaw workspace
                  ~/.config/opencode/skills/                         OpenCode (own root; on request)
                  .opencode/skills/                                  OpenCode project-local
                  scope: personal vs project-local (Step 5, BOOK_TO_SKILL_SCOPE)
                  SKILL.md         core frameworks + chapter & topic index (~4K)
                  chapters/*.md    on-demand, loaded only when asked
                  glossary.md      terms
                  patterns.md      techniques
                  cheatsheet.md    decision rules / trees / trade-offs / tells
```

OpenClaw's shared `~/.agents/skills` compatibility root is discoverable only
when `OPENCLAW_STATE_DIR` is unset or uses the default `~/.openclaw`. A
non-default state uses its active `<state-dir>/skills` root instead; the
converter does not infer arbitrary `skills.load.extraDirs`.

## Mode 2: Search & Read (MCP)

When invoked with `/book-to-skill search <query>`, the agent switches to Mode 2
without downloading or permanently saving a full raw book file. `SKILL.md`
contains only a compact Mode 2 trigger and routes to
[`references/search-and-read.md`](../references/search-and-read.md), which is
loaded lazily only when Mode 2 runs and an MCP book provider is available. If
no MCP provider is exposed, the agent stops and offers Mode 1 (local files).

```
 Query (/book-to-skill search "...")
   │
   ▼  host agent invokes MCP `search` & `get_details`
 MCP Search ──▶ book_to_skill/remote/discovery.py + policy.py
   │              (normalize candidates, group editions, check BOOK_TO_SKILL_REMOTE_POLICY)
   ▼
 Selection  ──▶ explicit candidate pick + mandatory copyright/cache confirmation gate
   │
   ▼  host agent invokes MCP `read` (outline / section / cursor; never `download`)
 MCP Read   ──▶ book_to_skill/remote/reader.py
   │              (parse outline or sequential_fallback, sanitize chunks via sanitize.py,
   │               guard cursor loops & request caps)
   ▼
 Incremental Processing ──▶ book_to_skill/remote/checkpoint.py
   │                          (prose-free remote_session.json in 0o700 workdir for resume)
   ▼
 Generator (references/search-and-read.md + SKILL.md Steps 7–11)
   │  per-chapter synthesis → discard raw fragments immediately (no full_text.txt)
   │  coverage.py + provenance.py → Scope & Limits + scan_generated_skill.py
   ▼
 Skill (<SKILLS_HOME>/<slug>/: SKILL.md, chapters/*.md, glossary.md, patterns.md, cheatsheet.md)
```

### `book_to_skill/remote/` zero-network helper modules

`book_to_skill/remote/` is a deterministic, stdlib-only offline package. It
performs **no** outbound HTTP requests, opens **no** sockets, and has **no**
runtime dependency on `libgen-mcp` or any MCP SDK. The host coding agent
executes MCP tool calls and passes JSON/text payloads into these helpers:

| Module | Responsibility |
|--------|----------------|
| `book_to_skill/remote/__init__.py` | Re-exports the public offline helper API and constants |
| `book_to_skill/remote/discovery.py` | Normalizes MCP `search` / `get_details` payloads (`normalize_search_results`, `normalize_work_details`), deduplicates editions (`group_duplicate_editions`), and formats selection tables |
| `book_to_skill/remote/policy.py` | Loads `BOOK_TO_SKILL_REMOTE_POLICY` (`load_policy`), enforces provider allow/block rules (`check_provider_allowed`), builds the copyright/cache notice (`build_access_copyright_notice`), verifies explicit consent (`verify_user_confirmation`), and enforces private-by-default publish visibility (`resolve_publish_visibility`) |
| `book_to_skill/remote/reader.py` | Parses outlines with `sequential_fallback` (`parse_outline_response`), sanitizes every chunk (`sanitize_remote_chunk`), and paginates sections with cursor-loop and request-cap guards (`process_section_page`, `read_section_from_pages`) |
| `book_to_skill/remote/checkpoint.py` | Initializes, atomically saves, and reloads prose-free `remote_session.json` state (`init_remote_session`, `save_remote_session`, `load_remote_session`, `update_chapter_progress`, `pending_chapters`) |
| `book_to_skill/remote/coverage.py` | Computes chapter completion, missing/truncated sections, and `complete` / `partial` / `degraded` status (`build_coverage_report`, `format_coverage_summary`) |
| `book_to_skill/remote/provenance.py` | Builds and renders prose-free source/edition/coverage metadata for `SKILL.md` (`build_remote_provenance`, `render_provenance_markdown`, `storage_mode="incremental_ephemeral_no_full_text"`) |

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
| `book_to_skill/sanitize.py` | strips zero-width / Unicode-tag-block characters from extracted text, and folds Kangxi radicals to their ideographs (see Security) |
| `book_to_skill/remote/` | zero-network offline helpers for Mode 2 discovery, policy, sanitized reading, checkpoints, coverage, and provenance |
| `references/search-and-read.md` | lazy-loaded Mode 2 Search & Read protocol spec (loaded only when MCP Search & Read is triggered) |
| `tools/discovery_tax.py` | measures token cost vs context-dump / discovery loop |
| `tools/validate_skill.py` | checks a generated SKILL.md against host rules (`--lens claude\|copilot\|amp\|hermes\|openclaw\|opencode`) |
| `tools/scan_generated_skill.py` | advisory prompt-injection scan of a generated skill (see Security) |
| `SKILL.md` | the generator spec (Steps 0–10 + fold-in workflow) |

## Security

For page-level PDF evidence, run
`python3 scripts/extract.py book.pdf --pdf-page-sidecar`. It additionally
writes `pdf_pages.json` in the workdir.
This opt-in sidecar uses pypdf's text layer even when the main extractor is
different. Each record carries the source SHA-256, one-based physical page,
sanitized text, extraction method, and low-confidence reasons. It does not
change `full_text.txt` or `metadata.json`, and it provides no exact character
offsets into the cleaned full text. A suspected merged decimal token (for
example `0.2070.110`) remains untouched and is marked for manual PDF-table
review; the code does not infer column separators. If pypdf cannot read the
source or the source hash changes, the sidecar marks that source unavailable
instead of inventing page evidence.

Untrusted documents flow into an agent's context and then into a generated skill
that later loads into other agents — a document→context supply chain. The hardening
is layered:

- **Extraction sanitization** (`book_to_skill/sanitize.py`) — strips zero-width
  (`U+200B/200C/200D/2060/FEFF`) and the Unicode tag block (`U+E0000–E007F`) from
  every parser's output before metrics or `full_text.txt`, so invisible
  document-borne instructions never reach the agent. Reports the removal count;
  rejects a source with no visible content left.
- **CJK radical folding** (`book_to_skill/sanitize.py`) — PDFs whose embedded
  font subset carries no correct Unicode mapping emit a Kangxi radical
  (`U+2F00–U+2FDF`) where a character belongs, so a Chinese book extracts
  "判断⼒" for "判断力". Each radical in that block has a Unicode compatibility
  decomposition, so the fold is NFKC applied to those code points only: the rest
  of the text is passed through byte for byte. Nothing is removed, so it does
  not count toward the security removal total. CJK Radicals Supplement
  (`U+2E80–U+2EF3`) is deliberately not folded — Unicode defines no
  decomposition for it, and some entries are ordinary kanji.
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
- **Mode 2 remote boundaries** —
  - *Zero-network Python core*: `book_to_skill/` performs no network I/O; the host agent mediates MCP `search`, `get_details`, and `read` (MCP `download` is never called).
  - *Untrusted MCP chunk sanitization*: every remote fragment passes through `sanitize.py` (`sanitize_extracted_text()`) via `sanitize_remote_chunk()` / `process_section_page()` before inspection or synthesis.
  - *No permanent `full_text.txt` or stored raw prose*: raw fragments are discarded immediately after each `chapters/*.md` file is written; `checkpoint.py` and `provenance.py` reject prose keys (`FORBIDDEN_PROSE_KEYS`), and `remote_session.json` is written atomically (`0o600`) inside a symlink-checked `0o700` `workdir`.
  - *Bounded pagination & explicit gates*: `reader.py` enforces `max_cursors_per_section` (default `100`), `max_total_requests` (default `1000`), and seen-cursor loop detection; `policy.py` enforces explicit user consent before `read` and private-by-default publishing (`--private`).
- **CI** — CodeQL, Bandit (gate on HIGH), Zizmor, and dependency CVE review on PRs.

## Extending

- **New format** → add `book_to_skill/parsers/<fmt>.py`, register its extension in
  `config.py`, wire dependency probing in `dependencies.py`, branch in
  `utils.extract_single_file`.
- **New generation behavior** → edit the relevant Step in `SKILL.md`; keep it lean
  and back the change with evidence (see CONTRIBUTING.md).
