---
name: book-to-skill
description: "Converts books and documents (PDF, EPUB, DOCX, HTML, Markdown, plain text, RTF, MOBI/AZW with Calibre) into structured agent skills, extracting frameworks, mental models, principles, techniques, and anti-patterns. Use when the user wants to study a document through Amp or Claude Code, apply an author's frameworks while working, or build a reusable knowledge base from a file."
compatibility: "Amp skill directories (.agents/skills, ~/.config/agents/skills, ~/.config/amp/skills) and Claude Code skill directories (~/.claude/skills)."
allowed-tools:
  - shell_command
  - Read
  - Write
  - Glob
  - Grep
argument-hint: <path-to-document> [skill-name-slug]
---

# Book-to-Skill Converter

Transform written knowledge into actionable agent skills by extracting structure — not producing summaries.

## Philosophy

Books contain crystallized expertise: frameworks, principles, and techniques that took years to develop. This skill extracts that knowledge into a format Amp, Claude Code, or another compatible agent can leverage repeatedly.

**Extract structure, not summaries.** A skill isn't a book report. It's a toolkit of:
- Named frameworks (mental models with clear application)
- Actionable principles (rules that guide decisions)
- Techniques (step-by-step methods)
- Anti-patterns (what to avoid and why)
- Voice calibration (how the author thinks and communicates)

**Preserve the author's precision.** Frameworks often have specific names for reasons. "The 5 Whys" isn't interchangeable with "ask why multiple times." Capture the exact formulation.

**Layer depth appropriately.** Simple books → simple skills. Complex books with 10+ frameworks → skills with reference files and on-demand chapters.

---

## Modes of Operation

Three paths available. Route based on what the user asks:

### 1. Full Conversion (Default)
**Trigger:** User provides a supported document path without special instructions
**Action:** Run all steps below (Steps 0–9)
**Output:** Complete skill with SKILL.md, chapters/, glossary, patterns, cheatsheet

### 2. Analyze Only
**Trigger:** User says "analyze", "just extract", or "I want to review before generating"
**Action:** Run Steps 0–3, then produce a structured extraction report (frameworks, principles, techniques found). Stop — do NOT generate skill files.
**Output:** Analysis report for user review

### 3. Generate from Prior Analysis
**Trigger:** User has existing analysis notes or previously ran analyze-only
**Action:** Skip Steps 0–3, use the provided analysis as input, run Steps 4–9
**Output:** Skill files from the provided analysis

---

## Skill Locations

This converter can run from multiple skill systems. When looking for this converter's helper script or writing the generated book skill, prefer these locations in order:

1. Amp project-local skills: `.agents/skills/`
2. Amp global skills: `~/.config/agents/skills/`
3. Amp legacy global skills: `~/.config/amp/skills/`
4. Claude Code skills: `~/.claude/skills/`

Generated skills should default to `~/.config/agents/skills/` for Amp unless the user asks for project-local or Claude Code output.

---

## Step 0 — Out-of-scope check

If the argument is NOT a path to a supported document file, stop and respond:
> "book-to-skill requires a supported document path. Usage: `book-to-skill /path/to/book.pdf [skill-name]`, `book-to-skill /path/to/book.epub [skill-name]`, or another supported format such as `.docx`, `.md`, `.txt`, `.html`, `.rtf`, `.mobi`, or `.azw3`."

Throughout the workflow, treat the first argument as `BOOK_PATH` and the optional second argument as `SKILL_NAME`.

---

## Step 1 — Validate input

```bash
test -f "$BOOK_PATH" && echo "FILE_OK" || echo "FILE_NOT_FOUND: $BOOK_PATH"
case "${BOOK_PATH##*.}" in
  pdf|PDF|epub|EPUB|docx|DOCX|txt|TXT|md|MD|markdown|MARKDOWN|rst|RST|adoc|ADOC|asciidoc|ASCIIDOC|html|HTML|htm|HTM|rtf|RTF|mobi|MOBI|azw|AZW|azw3|AZW3) echo "FORMAT_OK" ;;
  *) echo "FORMAT_UNKNOWN" ;;
esac
```

Check the file extension (`.pdf`, `.epub`, `.docx`, `.txt`, `.md`, `.markdown`, `.rst`, `.adoc`, `.html`, `.htm`, `.rtf`, `.mobi`, `.azw`, `.azw3`) or magic bytes (`%PDF` or `PK` zip header for EPUB/DOCX).

If the file is not found or the format is not supported, stop with a clear error message listing supported formats.

---

## Step 1.5 — Identify book type

Before extracting, ask the user:

> "What kind of content does this book have? This helps me choose the best extraction method.
>
> 1. **Technical** — has code blocks, tables, formulas, diagrams (e.g. programming books, academic papers, architecture guides)
> 2. **Text-heavy** — mostly prose, few or no tables/code (e.g. management, productivity, narrative non-fiction)
> 3. **Not sure** — I'll use the fast method and warn you if quality seems limited"

Store the answer as `BOOK_TYPE`:
- Option 1 → `BOOK_TYPE=technical`
- Option 2 → `BOOK_TYPE=text`
- Option 3 → `BOOK_TYPE=text`

**If `BOOK_TYPE=technical`**, inform the user before proceeding:
> "📐 Technical mode selected — using Docling for structure-aware extraction (tables, code blocks, formulas preserved as markdown). This takes ~1.5s per page, so expect a few minutes for longer books. Starting now…"

**If `BOOK_TYPE=text`**, inform:
> "📄 Text mode selected — using the fastest suitable extractor for this file type. Plain text/Markdown/HTML are usually ready in seconds; PDFs use pdftotext when available."

---

## Step 2 — Extract text from the source document

Run the extraction script, passing the book type:

```bash
SCRIPT_PATH=""
for candidate in \
  ".agents/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.config/agents/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.config/amp/skills/book-to-skill/scripts/extract.py" \
  "$HOME/.claude/skills/book-to-skill/scripts/extract.py"
do
  if [ -f "$candidate" ]; then
    SCRIPT_PATH="$candidate"
    break
  fi
done

if [ -z "$SCRIPT_PATH" ]; then
  echo "Could not find scripts/extract.py for book-to-skill" >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" "$SCRIPT_PATH" "$BOOK_PATH" --mode <BOOK_TYPE> --install-missing ask
```

Before extraction, the script checks optional Python packages needed for the detected format. If a better extractor is missing, it prompts the user with the available fallback, for example:

> "DOCX extraction uses python-docx if installed, otherwise a stdlib ZIP/XML parser. Missing package(s) detected. Do you want to install? y=install, n=fallback"

Use `--install-missing yes` to install missing Python packages without prompting, `--install-missing no` or `--no-install-missing` to always use fallbacks, or `BOOK_SKILL_INSTALL_MISSING=yes|no|ask` to set the behavior by environment variable. Non-interactive sessions default to fallback unless install mode is explicitly `yes`.

- PDF `--mode technical` → uses Docling (layout-aware, preserves tables and code blocks as markdown)
- PDF `--mode text` → uses pdftotext → PyPDF2 → pdfminer fallback chain (fast, plain text)
- EPUB → uses ebooklib + BeautifulSoup4, then stdlib ZIP/HTML fallback
- DOCX → uses python-docx, then stdlib ZIP/XML fallback
- TXT/Markdown/reStructuredText/AsciiDoc → reads directly as text
- HTML → uses BeautifulSoup4, then stdlib HTML fallback
- RTF → uses striprtf, then a basic regex fallback
- MOBI/AZW/AZW3 → uses Calibre `ebook-convert` when installed. Calibre is an external app, not a pip package, so the script reports how to install it if missing.

This creates:
- `<tempdir>/book_skill_work/full_text.txt` — full extracted text
- `<tempdir>/book_skill_work/metadata.json` — title, estimated pages, token count, size, extraction_mode

Read the `output_text` path in `<tempdir>/book_skill_work/metadata.json` to understand what was extracted. The extractor uses the platform temp directory by default and supports `BOOK_SKILL_WORKDIR` if an explicit work directory is needed.

---

## Step 2.5 — Pre-flight cost estimate

Read `<tempdir>/book_skill_work/metadata.json` and present the user with an estimate **before doing any generation**:

```
📖 Source detected: <filename> (<format>)
📄 Pages/Spine items/Sections: ~<N> | Words: ~<N> | Source tokens: ~<N>K

💰 Estimated token cost (Full Conversion):
   Input  (book reading + prompts): ~<N>K tokens
   Output (skill files generated):  ~<N>K tokens
   Total:                           ~<N>K tokens

   Reference prices (as of 2025):
   Claude Sonnet 4.5 → ~$<X> USD
   Claude Haiku 4.5  → ~$<X> USD

   ⏱  Estimated time: ~<N> minutes

📁 Files to be generated:
   SKILL.md + <N> chapter files + glossary + patterns + cheatsheet

➡  Proceed with Full Conversion? (or type "analyze only" to preview first)
```

**How to estimate:**
- Input tokens ≈ `estimated_tokens` from metadata × 1.3 (prompts overhead per chapter pass)
- Output tokens ≈ chapters × 1,000 + 4,000 (SKILL.md) + 4,500 (glossary + patterns + cheatsheet)
- Price: Sonnet input=$3/MTok output=$15/MTok — Haiku input=$0.80/MTok output=$4/MTok

Wait for the user to confirm before proceeding. If they say "analyze only", switch to Mode 2.

---

## Step 3 — Analyze book structure

Read the first 8,000 characters of the extracted `full_text.txt` to identify:
- Book **title** and **author(s)**
- **Chapter structure** (look for "Chapter N", "PART I", numbered headings, table of contents)
- **Core themes** and subject domain
- Approximate number of chapters

Then read the Table of Contents section if present to map all chapters.

**If mode is "Analyze Only":** produce the extraction report now and stop. Structure:
```
## Extraction Report — <Title>

### Author's Core Frameworks
- **<Framework Name>**: <what it is and when to apply>

### Key Principles
- <Principle>: <actionable rule>

### Techniques & Methods
- <Technique>: <step-by-step or how-to>

### Anti-patterns
- <What to avoid>: <why>

### Suggested Skill Name
`{author-lastname}-{core-concept}` — e.g. `cialdini-influence`

### Chapters Detected
| # | Title | Main Frameworks |
```

---

## Step 4 — Ask purpose (Full Conversion only)

Before generating, ask the user:

> "What should this skill help you do? (Pick one or more)
> 1. Apply the author's frameworks while working
> 2. Think with the author's mental models
> 3. Reference specific chapters and concepts
> 4. All of the above"

Use the answer to weight what gets highlighted in the SKILL.md Core section.

---

## Step 5 — Determine skill name

If `SKILL_NAME` was provided, use it as the skill slug.
Otherwise, propose two options and let the user choose:
- **By author-concept**: `{author-lastname}-{core-concept}` (e.g. `cialdini-influence`, `meadows-systems`)
- **By title**: lowercase hyphens from book title (e.g. `designing-data-intensive-apps`)

Default to author-concept format if the book has a strong methodological identity.

Choose the destination skill root:
- **Amp default**: `~/.config/agents/skills`
- **Amp project-local**: `.agents/skills` when the user explicitly wants the generated book skill scoped to the current workspace
- **Amp legacy**: `~/.config/amp/skills` if that is the user's existing global skill location
- **Claude Code**: `~/.claude/skills` if the user explicitly asks for Claude Code output

Set `SKILLS_HOME` to the selected root and check that `$SKILLS_HOME/<skill_name>/` does NOT already exist.
If it does, append `-2` or ask the user before overwriting.

---

## Step 6 — Create skill directory structure

```bash
mkdir -p "$SKILLS_HOME/<skill_name>/chapters"
```

---

## Step 7 — Generate chapter summaries

**TOKEN BUDGET RULE — CRITICAL:**
- Each chapter summary file: **800–1,200 tokens** (dense, not verbose)
- Files are loaded on-demand — they are NOT capped per se, but keep them useful and tight

For EACH chapter/major section identified in Step 3:

Read the corresponding section of the extracted `full_text.txt` (use character offsets or grep for chapter headings).

Create `$SKILLS_HOME/<skill_name>/chapters/ch<NN>-<slug>.md` using the structure below.

**Adapt emphasis based on `BOOK_TYPE`:**
- `technical` → prioritize "Code Examples", "Reference Tables", and "Commands & APIs" sections; preserve exact syntax
- `text` → prioritize "Frameworks Introduced", "Mental Models", and "Key Takeaways"; skip empty technical sections

```markdown
# Chapter N: <Full Title>

## Core Idea
<1–2 sentences: the single most important thing this chapter teaches>

## Frameworks Introduced
- **<Framework Name>**: <exact formulation — preserve the author's naming>
  - When to use: <specific situation>
  - How: <steps or criteria>

## Key Concepts
- **<Term>**: <precise definition in 1 sentence>
(5–10 most important terms from this chapter)

## Mental Models
<2–4 frameworks or thinking tools. Write as "Use X when Y" or "Think of X as Y">

## Anti-patterns
- **<What to avoid>**: <why it fails>

## Code Examples *(technical books only — omit if BOOK_TYPE=text)*
<!-- Copy the most instructive snippet from the chapter. Preserve indentation exactly. -->
```<language>
<key code example from this chapter>
```
- **What it demonstrates**: <one line>

## Reference Tables *(technical books only — omit if BOOK_TYPE=text)*
<!-- Reproduce any comparison matrix, parameter table, or decision table from the chapter in markdown. -->

## Key Takeaways
1. <Actionable insight>
2. <Actionable insight>
3. <Actionable insight>
(3–7 takeaways a practitioner must remember)

## Connects To
- **Ch N**: <why this chapter relates>
- **<Concept>**: <external concept or standard it connects with>
```

---

## Step 8 — Generate supporting files

### glossary.md
Create `$SKILLS_HOME/<skill_name>/glossary.md`:
- Every significant term from the book, alphabetically sorted
- Format: `**Term** — definition (Ch N)`
- Max 1,500 tokens

### patterns.md
Create `$SKILLS_HOME/<skill_name>/patterns.md`:
- All concrete techniques, design patterns, algorithms from the book
- Format: `## Pattern Name\n**When to use**: ...\n**How**: ...\n**Trade-offs**: ...`
- Max 2,000 tokens

### cheatsheet.md
Create `$SKILLS_HOME/<skill_name>/cheatsheet.md`:
- Decision tables, comparison matrices, quick-reference rules
- The content you'd want on a single printed page
- Max 1,000 tokens

---

## Step 9 — Generate the master SKILL.md

**CRITICAL TOKEN BUDGET: Keep SKILL.md body under 4,000 tokens.**
Compaction truncates from the END — put the most important content FIRST.

Create `$SKILLS_HOME/<skill_name>/SKILL.md`:

```markdown
---
name: <skill_name>
description: "Knowledge base from \"<Full Title>\" by <Author(s)>. Use when applying <author>'s frameworks for <key topics, 3–6 terms>, studying the book, or referencing its concepts."
allowed-tools:
  - Read
  - Grep
argument-hint: [topic, framework name, or chapter number]
---

# <Full Title>
**Author**: <Author(s)> | **Pages**: ~<N> | **Chapters**: <N> | **Generated**: <YYYY-MM-DD>

## How to Use This Skill

- **Without arguments** — load core frameworks for reference
- **With a topic** — ask about `replication`, `pricing`, or another indexed topic; I find and read the relevant chapter
- **With chapter** — ask for `ch05`; I load that specific chapter
- **Browse** — ask "what chapters do you have?" to see the full index

When you ask about a topic not covered in Core Frameworks below, I will read
the relevant chapter file before answering.

---

## Core Frameworks & Mental Models
<!-- ~2,000 tokens: the author's most important named frameworks and principles.
     Preserve exact names. Write as "Use X when Y", "Prefer X over Y because Z".
     This is a toolkit, not a summary. -->

<generate 2,000 tokens of the most critical frameworks and insights here>

---

## Chapter Index

| # | Title | Key Frameworks |
|---|-------|----------------|
| [ch01](chapters/ch01-<slug>.md) | <Title> | <framework1>, <framework2> |
| [ch02](chapters/ch02-<slug>.md) | <Title> | <framework1>, <framework2> |
...

## Topic Index

<!-- Alphabetical. Major terms/frameworks → chapter(s) that cover them. -->
- **<Term>** → ch<N>[, ch<N>]
- **<Term>** → ch<N>

## Supporting Files

- [glossary.md](glossary.md) — all key terms with definitions
- [patterns.md](patterns.md) — all techniques and design patterns
- [cheatsheet.md](cheatsheet.md) — quick reference tables and decision guides

---

## Scope & Limits

This skill covers the book content only. For hands-on implementation in your codebase,
combine with project-specific tools. For topics beyond this book, check related skills
or ask the agent directly.
```

---

## Step 10 — Cleanup and report

```bash
PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" - <<'PY'
import os
import shutil
import tempfile
from pathlib import Path
shutil.rmtree(
    os.environ.get("BOOK_SKILL_WORKDIR", Path(tempfile.gettempdir()) / "book_skill_work"),
    ignore_errors=True,
)
PY
```

Then report to the user:

```
✅ Skill created: $SKILLS_HOME/<skill_name>/

📚 Book: <Full Title> — <Author>
📄 Pages: ~<N> | Chapters: <N>

Files generated:
  SKILL.md         — core frameworks + index   (~X tokens)
  chapters/        — <N> chapter summaries     (~X tokens each, ~X total)
  glossary.md      — key terms                 (~X tokens)
  patterns.md      — techniques & patterns     (~X tokens)
  cheatsheet.md    — quick reference           (~X tokens)
  ─────────────────────────────────────────────────────
  Total skill size: ~X tokens (loaded on-demand, not all at once)

💡 Tip: check your agent's session cost/usage command to see actual token usage.

Usage:
  Ask for <skill_name>                  → load core frameworks
  Ask <skill_name> about <topic>        → find and explain a topic
  Ask <skill_name> for ch<N>            → dive into a specific chapter
```

---

## Quality Rules

1. **Extract structure, not summaries** — capture named frameworks, exact formulations, anti-patterns; not chapter recaps
2. **Preserve the author's precision** — "The 5 Whys" ≠ "ask why multiple times"; keep exact naming
3. **Density over completeness** — a 1,000-token summary beats a 10,000-token excerpt
4. **Practitioner voice** — write "Use X when Y", not "The book explains X"
5. **Front-load SKILL.md** — compaction keeps the first 5,000 tokens; most important content comes first
6. **Chapter files are on-demand** — they don't count against skill budget until loaded
7. **Never copy raw book text** — always synthesize, summarize, extract signal
8. **Topic index is critical** — it's how the agent navigates to the right chapter file
