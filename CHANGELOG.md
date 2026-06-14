# Changelog

All notable changes to **book-to-skill** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Structure detection now recognizes Markdown/AsciiDoc ATX headings (`#`, `==`)
  as chapters when no numeric "Chapter N" headings are present, fixing a
  zero-chapter result for `.md`/`.adoc` sources. Headings inside fenced code
  blocks are ignored.
- Table-of-contents detection extended to Chinese, Japanese, French, German,
  Italian, and Dutch.

### Security
- **CI security scanning** — added CodeQL (Python, security-and-quality + weekly
  schedule), Bandit (gates on HIGH severity; reports MEDIUM+ informationally), and
  Zizmor (GitHub Actions workflow audit, informational). Added a Dependabot config
  for the `github-actions` ecosystem. Known open finding to harden in a follow-up:
  Bandit B314 (`xml.etree.ElementTree.fromstring` in the DOCX parser — untrusted
  XML).

### Fixed
- **Package now imports on interpreters that evaluate annotations eagerly.**
  Added `from __future__ import annotations` to every module using PEP 604
  unions (`str | None`) — `scripts/extractor/{utils,dependencies}.py`, all
  `scripts/extractor/parsers/*.py`, and `tools/discovery_tax.py`. Before this,
  importing the package under Python 3.9 raised `TypeError: unsupported operand
  type(s) for |: 'type' and 'NoneType'` at import time, so the whole test suite
  failed during collection. The annotations are now lazy (free at runtime), so
  the package imports and runs cleanly on Python 3.9 as well.

### Changed
- CI test matrix now includes Python 3.9 so the import path above is guarded and
  cannot silently re-break.

## [1.1.0] — 2026-06-12

### Added
- **GitHub Copilot CLI as a first-class target** — the same `SKILL.md` now
  discovers, installs, and runs across GitHub Copilot CLI, Amp, and Claude Code
  via the open Agent Skills standard. Skill Locations cover 8 discovery paths and
  the script probe walks all of them (#30).
- **`validate_skill.py --lens claude|copilot|amp`** — audits a generated SKILL.md
  against each host's rules; `claude` stays the default for CI back-compat (#30).
- **Attribution banner** — `scripts/banner.txt` is printed at the start of each
  run (best-effort, never fails the run).

### Changed
- `SKILL.md` frontmatter trimmed toward the open-standard minimum and the
  description now names all three hosts so each agent's auto-loader picks it up (#30).
- README headline + "Agent Skills" badge; install/usage sections cover all three
  hosts. `docs/ARCHITECTURE.md` shows per-host destination paths (#30).

### Notes
- `allowed-tools` was dropped from the frontmatter for host-neutrality; the skill
  is conformant on all three hosts (validated with all three lenses). If Claude
  users hit permission-prompt friction, the Bash grant from #18 will be restored
  with Claude-native tokens (Copilot ignores the key either way).

## [1.0.0] — 2026-06-08

First formally tagged release. The converter is stable, multi-format, and
validated on real books.

### Added
- **Multi-format extraction** — PDF, EPUB, DOCX, HTML, Markdown, reStructuredText,
  AsciiDoc, RTF, and MOBI/AZW/AZW3 (via Calibre), through a modular `extractor`
  package with per-format parsers and graceful stdlib fallbacks.
- **`extract.py --check`** — preflight that reports which extractors are installed
  for every format and the exact command to install whatever is missing (#21).
- **Adaptive per-chapter depth** — token budget scales with `BOOK_TYPE × DEPTH`;
  study-depth chapters require a worked example, and the cheatsheet is generated as
  a decision/reasoning layer (decision rules, trees, trade-offs, thresholds, tells)
  rather than a keyword list (#20).
- **`tools/discovery_tax.py`** — measures the "Discovery Loop Tax": tokens a
  context-dump vs a discovery loop vs book-to-skill put into context to answer one
  question, on a real book (#23).
- **Update / fold-in workflow** — merge new sources into an existing skill, keeping
  chapter index, topic index, glossary, patterns, and cheatsheet in sync.
- **GitHub Actions CI** — lint (ruff), test matrix (py3.10–3.13), dependency-free
  smoke test, and SKILL.md Claude-conformance validation (#15, #18).

### Changed
- **README positioning** — copyright & fair-use section, "Beyond books" use cases,
  context-dump / RAG / 1M-window FAQ, and a measured Discovery Loop Tax + real
  per-conversion cost table across four books (#19, #27).
- Default output target is `~/.claude/skills/` for Claude Code, with Amp skill
  directories also supported (#13, #14).

### Fixed
- **Chapter detection** — scans the full text (was capped at 50k chars) and counts
  distinct explicit `Chapter N` / `Capítulo N` headings, rejecting numbered list
  items, inline cross-references, and years; adds Portuguese support (#26).
- **Roman-numeral headings** — `I: Loomings`, `II. The Carpet-Bag` are now detected
  with canonical-numeral validation (#28).
- **EPUB extraction** — resolve OPF-relative hrefs in the stdlib zipfile fallback (#11, #12).
- **Batch resilience** — one bad source is skipped with a warning instead of aborting
  the whole run; explicit input order is preserved (#7).

### Known limitations
- Chapter auto-detection needs explicit `Chapter N` / `Capítulo N` or Roman-numeral
  headings. Books that head chapter bodies with bare titles (e.g. *Moby-Dick*, where
  numerals appear only in the table of contents) or use section titles (e.g. Pro Git)
  do not auto-segment.
- Technical PDFs extracted in text mode may lose heading structure; use technical
  mode (Docling) to preserve tables, code, and headings.

[1.1.0]: https://github.com/virgiliojr94/book-to-skill/releases/tag/v1.1.0
[1.0.0]: https://github.com/virgiliojr94/book-to-skill/releases/tag/v1.0.0
