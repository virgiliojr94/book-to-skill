# Mode 2 — Search & Read Protocol (MCP-Assisted Discovery & Incremental Synthesis)

> **Lazy-loaded reference.** Read this file **only** when Mode 2 (`/book-to-skill search <query>`) is triggered and an MCP book provider is available in Step 0. Local document paths (Input Mode 1) must not load this file.

## Overview & Non-Negotiable Boundaries

Mode 2 builds the **exact same skill output** as Mode 1 (`SKILL.md`, `chapters/`, `glossary.md`, `patterns.md`, `cheatsheet.md`) without downloading or permanently storing a raw book file:

- **Host-invoked MCP only:** The host coding agent calls MCP tools (`search`, `get_details`, `read`). Never call MCP `download`, never save `full_text.txt`, and never write raw book prose into `remote_session.json` or provenance metadata.
- **Python zero-network helpers:** Deterministic offline helpers under `book_to_skill/remote/` and `book_to_skill/sanitize.py` handle normalization, policy checks, sanitization, cursor/checkpoint tracking, coverage, and provenance.
- **Untrusted external data:** Every text chunk returned by MCP `read` MUST pass through `book_to_skill.sanitize.sanitize_extracted_text()` before synthesis or inspection.

---

## Pre-Flight — Provider & Policy Check

1. Confirm an MCP book provider (`libgen-mcp` or another configured provider exposing `search`, `get_details`, and `read`) is present in the host agent's active toolset.
   - If no provider is exposed, STOP, inform the user that MCP Search & Read is unavailable in this session, and offer **Mode 1 (local files)** (`book-to-skill <path-to-document-folder-or-glob>`).
2. Enforce `RemotePolicyConfig` (`enabled_providers`, `blocked_providers`, `require_explicit_confirmation`, `default_publish_visibility="private"`, `allow_public_publish=false`, `warn_mcp_temporary_cache=true`). If the active provider is blocked or disallowed by policy, stop and explain why.

---

## Step R1 — Discovery (`search` -> `get_details` -> Explicit Selection)

1. **Search:** Invoke MCP `search` with the user's `<query>` (title, author, ISBN, or DOI).
2. **Normalize & group duplicates:** Normalize candidate fields (`title`, `authors`, `edition`, `year`, `format`, `language`, `identifiers` (`isbn`, `doi`), `source_name`, `access_info`, `license_info`, `dedup_key`) and group duplicate editions by `dedup_key` while keeping individual selectable editions/formats explicit.
3. **Require explicit selection:** Present a numbered candidate table (title, authors, edition, year, format, language, identifiers, source/provider). Ask the user to pick an exact candidate/edition number.
   - Never silently auto-select when candidates or multiple editions exist.
   - If zero results match, offer to refine the query or switch to Mode 1 (local files).
4. **Inspect details:** Call MCP `get_details` on the selected candidate to confirm full metadata, identifiers, `access_info`, and `license_info`.

---

## Step R2 — Copyright, Access & Temporary-Cache Confirmation Gate

Before calling MCP `read` for the first time, display a clear confirmation prompt containing:

1. **Work & source identity:** Provider/source name, title, authors, edition, and identifiers (ISBN/DOI).
2. **Access & license info:** Known `access_info` and `license_info` (or `"unknown"` when the provider reports none).
3. **Copyright notice (mandatory):** Explicitly warn the user that **user confirmation does not equal copyright-holder authorization** — confirming to proceed reflects only the user's own access/use basis and does not grant redistribution rights or copyright-holder permission.
4. **Temporary-cache & transmission notice (mandatory):** Explicitly warn the user that invoking MCP `read` may cache book text temporarily on the MCP server and transmits read text chunks to the host model context for synthesis.

**Hard gate:** Require explicit user confirmation (e.g., `"yes"` / `"confirm"` / `"proceed"`) after displaying this notice. Never infer consent from the initial `search` command. If the user declines or gives an ambiguous answer, stop without calling `read`.

---

## Step R3 — Purpose, Destination & Checkpoint Setup

1. Gather `BOOK_TYPE` (`technical` vs `text`, Step 1.5) and `DEPTH` (`reference` vs `study`, Step 4), unless already specified.
2. Resolve `SKILLS_HOME` and `SKILL_NAME` per Step 5, applying the Step 0 re-run guard if `<skill_name>` already exists.
3. Create `$SKILLS_HOME/<skill_name>/chapters/` (Step 6).
4. Initialize a private per-run checkpoint directory (`chmod 0700`) containing `remote_session.json` to track work identity, `outline_mode`, limits (`max_cursors_per_section`, `max_total_requests`), and per-chapter progress (`status`, `next_cursor`, `chunks_read`, `sanitized_removed_count`, `truncated`, `error_reason`) — **storing zero raw book prose**.

---

## Step R4 — Outline & Incremental Chapter Synthesis (`read(outline)` -> `read(section)` / `read(cursor)`)

### 1. Obtain Outline or Activate Sequential Fallback
- Call MCP `read` in `"outline"` mode (`read(outline)`) to retrieve the chapter/section list (`index`, `section_id`, `title`).
- **Sequential fallback:** If the outline is missing, empty, or unreliable (e.g., missing section IDs or flat unsegmented response), switch explicitly to `sequential_fallback` mode using sequential `read(cursor)` pagination from the beginning of the work, and inform the user that chapter boundaries are sequential/inferred rather than outline-verified.

### 2. Incremental Chapter Loop
Process chapters one at a time (skipping chapters already marked `done` when resuming from `remote_session.json`):

1. **Read & paginate:** Call MCP `read(section)` (or `read(cursor)` in sequential mode), following `next_cursor` until the section completes.
   - Enforce per-section and total request limits (`max_cursors_per_section` default `100`, `max_total_requests` default `1000`).
   - Track `seen_cursors` per section; if `next_cursor` repeats (infinite cursor loop) or a limit is reached, stop reading that section and mark it `incomplete` with an explicit `error_reason`.
2. **Sanitize before synthesis:** Run every returned text chunk through `sanitize_extracted_text()` before passing it into synthesis prompts. Accumulate `sanitized_removed_count` in the checkpoint.
3. **Synthesize chapter file:** Write `$SKILLS_HOME/<skill_name>/chapters/ch<NN>-<slug>.md` using the Step 7 structure and adaptive token budget (`BOOK_TYPE` × `DEPTH`).
4. **Discard raw fragments immediately:** Once the chapter summary file is written, drop the raw chapter text from working memory/scratch. Never save `full_text.txt`, never keep raw excerpts on disk, and never copy raw prose verbatim.
5. **Checkpoint atomically:** Update `remote_session.json` (`status`: `done | incomplete | failed`, `next_cursor`, `chunks_read`, `truncated`, `error_reason`).

### 3. Incomplete or Truncated Chapters (Explicit Warning Rule)
- If a section returns `truncated: true`, ends early due to cursor/request caps or a cursor loop, or yields empty/unreadable content:
  - Mark the chapter `incomplete` (or `failed`) with the exact `error_reason`.
  - Add an **explicit incomplete/truncated warning** at the top of that chapter file (and in `Scope & Limits` / the Step 10 report) stating which section(s) were truncated or missing and why.
  - Never present partial or truncated output as a complete synthesis.

---

## Step R5 — Consolidated Supporting Files, Master `SKILL.md`, Scan, Report & Publish

1. **Consolidated supporting files (Step 8):** Across the synthesized `chapters/` files (not raw text), generate:
   - `$SKILLS_HOME/<skill_name>/glossary.md` (alphabetized key terms, max 1,500 tokens)
   - `$SKILLS_HOME/<skill_name>/patterns.md` (techniques & design patterns, max 2,000 tokens)
   - `$SKILLS_HOME/<skill_name>/cheatsheet.md` (decision rules, trade-offs, thresholds, smells, max 1,200 tokens)
2. **Master `SKILL.md` (Step 9):** Generate `$SKILLS_HOME/<skill_name>/SKILL.md` under the 4,000-token budget with Core Frameworks & Mental Models, Chapter Index, Topic Index, Supporting Files (do **not** add a `full_text.txt` line, since Mode 2 stores no raw book file), and Scope & Limits (recording source provider, edition/identifiers, coverage status, and any missing/truncated section warnings — zero raw book prose).
3. **Security scan (Step 9.5):** Run `tools/scan_generated_skill.py "$SKILLS_HOME/<skill_name>"` before reporting success or publishing. If it exits non-zero, stop and ask a human to review the findings.
4. **Cleanup & report (Step 10):**
   - Create and verify the Claude Code symlink when `SKILLS_HOME` is `~/.agents/skills` (per Step 10).
   - Remove the temporary checkpoint `workdir` once all chapters succeed (if the run is `partial` or `degraded`, inform the user of the checkpoint path in case they choose to resume, or remove it if they discard).
   - Print the Step 10 summary plus the coverage report (`complete`, `partial`, or `degraded`) and explicit warnings for any missing or truncated chapters.
5. **Private-by-default publish gate (Step 11):**
   - Offer publishing once only if the Step 9.5 scan passed.
   - Apply the Step 11 visibility gate verbatim: `gh repo create` MUST default to `--private`, and `--public` is allowed **only** when the user replies with the bare word `public` to the separate closed visibility question **and** the copyright/policy gate permits it (`allow_public_publish` / author-owned or openly licensed/authorized material). Third-party copyrighted books retrieved via MCP **must stay private**.
