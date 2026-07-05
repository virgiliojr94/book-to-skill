# Proposed changes — book-to-skill

This document summarizes six improvements proposed as a contribution to
[virgiliojr94/book-to-skill](https://github.com/virgiliojr94/book-to-skill). Each
change is small, self-contained, additive, and backward-compatible. The full test
suite passes and `ruff check` is clean.

## Summary

| # | Area | Change | Files |
|---|------|--------|-------|
| 1 | Extraction | Emit per-chapter offsets in `metadata.json` | `book_to_skill/utils.py`, `SKILL.md` |
| 2 | Cost estimate | CJK-aware `estimate_tokens` (fixes ~1000x undercount) | `book_to_skill/utils.py`, `book_to_skill/config.py` |
| 3 | Quality | `tools/verify_fidelity.py` + fidelity rules | `tools/verify_fidelity.py`, `SKILL.md` |
| 4 | Cost estimate | Stop hardcoding model prices in the pre-flight | `SKILL.md` |
| 5 | Extraction | Detect image-only/scanned PDFs; opt-in `--ocr` | `book_to_skill/parsers/pdf.py`, `book_to_skill/utils.py` |
| 6 | Hygiene | Untrack committed `.pyc`; gate the stderr banner | `book_to_skill/utils.py`, repo |
| 7 | Install | SKILL.md self-bootstraps the engine when only SKILL.md is present | `SKILL.md`, `README.md` |

## 1. Chapter offsets in metadata.json
**Problem.** `detect_structure()` already locates every chapter heading, but it
discarded the positions and emitted only a count plus a 10-item sample. SKILL.md
Step 7 then asked the agent to re-locate each chapter by "character offsets or
grep" — redundant work and a source of missed/duplicated sections.

**Change.** `detect_structure()` now emits `chapters`: an ordered list of
`{number, title, line_start, line_end, char_start, char_end}` for each chapter's
*body* heading (last occurrence wins, so a ToC entry does not shadow the body).
SKILL.md Step 7 slices each chapter from those offsets with a bounded `Read`.

**Compatibility.** Additive key; `chapters_detected` / `has_toc` unchanged; all
existing `detect_structure` tests pass.


## 2. CJK-aware token estimate
**Problem.** `estimate_tokens` counted whitespace-delimited words. CJK text is
space-less, so a 1,500-character Chinese/Japanese book counted as ~1 token — the
cost pre-flight under-reported by ~1000x for exactly the languages the chapter
detector already supports.

**Change.** `estimate_tokens` now counts CJK codepoints directly against a new
`CJK_CHARS_PER_TOKEN` constant (~1.5), while Latin text keeps the existing
`words / WORDS_PER_TOKEN` path. Kept deterministic and dependency-free on purpose
(no tiktoken) so the same book always yields the same estimate and the pinned
Latin test (`100 words -> 133`) is unchanged.

## 3. Fidelity verification
**Problem.** The project promises "answers from the actual book, not
hallucination", but nothing verified generated skills against the source;
`validate_skill.py` checks structure, not faithfulness.

**Change.** New `tools/verify_fidelity.py` pulls every bolded framework/term from
the generated skill and checks it appears in `full_text.txt`, flagging possible
confabulations and returning non-zero below a coverage threshold. SKILL.md Step
10 runs it *before* cleanup deletes the working text, and new Quality Rules
require source-anchoring each framework.

## 4. No hardcoded model prices
**Problem.** The pre-flight hardcoded "as of 2025" Sonnet/Haiku dollar figures,
which drift as prices and model names change.

**Change.** SKILL.md now reports token counts and instructs applying the user's
current per-1M-token rate; any illustrative figure must be dated and labeled.


## 5. Image-only / scanned PDF handling
**Problem.** For a scanned PDF some extractors return whitespace, so the chain
"succeeded" with no real text and produced an empty skill silently.

**Change.** `looks_image_only()` detects a multi-page PDF with near-zero
extractable text. When detected, extraction either OCRs the file (opt-in via
`--ocr` / `BOOK_SKILL_OCR=1`, using ocrmypdf->pdftotext or Docling OCR) or fails
with an actionable message instead of emitting an empty skill.

## 6. Hygiene
- Untracked `scripts/__pycache__/extract.cpython-313.pyc`, which was committed
  before `.gitignore` covered it (`git rm --cached`).
- The attribution banner (`print_banner`) now prints only on an interactive TTY
  or when forced with `--banner` / `BOOK_SKILL_BANNER=1`, and is suppressed for
  agent/pipeline runs so it stops adding noise to the caller's context.

## 7. Self-bootstrapping install
**Problem.** The README offers a copy-paste one-liner
(`Install book-to-skill: <raw SKILL.md URL>`), but SKILL.md never self-cloned. If a
host acted on it by saving only `SKILL.md`, Step 2's engine-discovery loop found no
`scripts/extract.py` and exited with "Could not find scripts/extract.py".

**Change.** Step 2 now self-bootstraps: when no installed copy is found it clones the
repo into `~/.cache/book-to-skill` and runs from there; if git or network is
unavailable it prints an actionable `git clone` command instead of the bare error.
The existing `git clone` install path is unchanged; README documents the behavior.

**Testing.** The bootstrap block passes `bash -n`; the full suite still passes (142)
and ruff is clean (this is a docs / embedded-shell change).

## Testing
- `python3 -m pytest -q` -> all tests pass (142 in the suite).
- `ruff check book_to_skill tools` -> clean.
- Functional checks: CJK 1,500 chars -> 1000 tokens (was 1); Latin 100 words ->
  133 (unchanged); chapter offsets select body headings over ToC entries; banner
  suppressed on non-TTY; image-only heuristic; `verify_fidelity.py` flags a
  planted confabulation and exits non-zero.
