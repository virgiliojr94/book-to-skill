# Architecture

book-to-skill has two halves: a **deterministic extractor** (Python) and a
**spec-driven generator** (the agent following `SKILL.md`). The extractor turns any
document into clean text + metadata; the agent turns that into a structured skill.

```
            ┌─────────────────────────── EXTRACTOR (Python, deterministic) ──┐
 documents  │  scripts/extract.py  →  extractor/                              │
 (pdf/epub/ │    ├─ utils.py        CLI parse · multi-source resolve · runner │
  docx/...) │    ├─ config.py       supported extensions · paths · deps map   │
     │      │    ├─ dependencies.py optional-dep probing · --check report     │
     ▼      │    └─ parsers/        pdf · epub · docx · html · rtf · calibre · │
 ───────────│                        text  (best tool first, stdlib fallback) │
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
   load only the relevant chapter. See [PERFORMANCE.md](PERFORMANCE.md).
3. **On-demand chapters** — `SKILL.md` stays small; chapter files cost tokens only
   when read.
4. **Front-loaded `SKILL.md`** — most important content first (compaction truncates
   from the end).
5. **Graceful degradation** — every format has a stdlib fallback; one bad source is
   skipped, not fatal.

## Key components

| Path | Responsibility |
|------|----------------|
| `scripts/extract.py` | thin entrypoint wrapper |
| `scripts/extractor/utils.py` | CLI parsing, multi-source resolution, chapter/ToC detection, runner |
| `scripts/extractor/parsers/` | one module per format |
| `scripts/extractor/dependencies.py` | optional-dependency probing + `--check` |
| `tools/discovery_tax.py` | measures token cost vs context-dump / discovery loop |
| `tools/validate_skill.py` | checks a generated SKILL.md against host rules (`--lens claude|copilot|amp`) |
| `SKILL.md` | the generator spec (Steps 0–10 + fold-in workflow) |

## Extending

- **New format** → add `parsers/<fmt>.py`, register its extension in `config.py`,
  wire dependency probing in `dependencies.py`, branch in `utils.extract_single_file`.
- **New generation behavior** → edit the relevant Step in `SKILL.md`; keep it lean
  and back the change with evidence (see CONTRIBUTING.md).
