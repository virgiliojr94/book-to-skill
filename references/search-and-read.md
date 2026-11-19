# Mode 2 — Search & Read Protocol (MCP-Assisted Discovery & Incremental Synthesis)

> **Lazy-loaded reference.** Read this file **only** when Mode 2 (`/book-to-skill search <query>`) is triggered and an MCP book provider is available in Step 0. Local document paths (Input Mode 1) must not load this file.

## Overview & Non-Negotiable Boundaries

Mode 2 builds the **exact same skill output** as Mode 1 (`SKILL.md`, `chapters/`, `glossary.md`, `patterns.md`, `cheatsheet.md`) without downloading or permanently storing a raw book file:

- **Host-invoked MCP only:** The host coding agent calls MCP tools (`search`, `get_details`, `read`). Never call MCP `download`, never save `full_text.txt`, and never write raw book prose into `remote_session.json` or provenance metadata.
- **Python zero-network helpers (`book_to_skill.remote`):** Deterministic stdlib-only offline helpers implement the frozen contracts across six modules:
  - `book_to_skill.remote.discovery` — `normalize_search_results()`, `group_duplicate_editions()`, `format_candidate_selection_table()`, `normalize_work_details()`
  - `book_to_skill.remote.policy` — `load_policy()`, `check_provider_allowed()`, `build_access_copyright_notice()`, `verify_user_confirmation()`, `resolve_publish_visibility()`
  - `book_to_skill.remote.reader` — `parse_outline_response()`, `sanitize_remote_chunk()`, `process_section_page()`, `read_section_from_pages()`
  - `book_to_skill.remote.checkpoint` — `init_remote_session()`, `save_remote_session()`, `load_remote_session()`, `update_chapter_progress()`, `pending_chapters()`
  - `book_to_skill.remote.coverage` — `build_coverage_report()`, `format_coverage_summary()`
  - `book_to_skill.remote.provenance` — `build_remote_provenance()`, `render_provenance_markdown()`
- **Untrusted external data:** Every text chunk returned by MCP `read` MUST pass through `book_to_skill.sanitize.sanitize_extracted_text()` (via `sanitize_remote_chunk()` / `process_section_page()`) before synthesis or inspection.

---

## Pre-Flight — Provider & Policy Check

1. Confirm an MCP book provider (`libgen-mcp` or another configured provider exposing `search`, `get_details`, and `read`) is present in the host agent's active toolset.
   - If no provider is exposed, STOP without exposing internal "Mode 1/Mode 2" labels: explain that Search & Read needs a book MCP server, offer to run the **Guided Setup** below (with explicit user confirmation), and offer converting a local file immediately (`/book-to-skill ~/books/pro-git.pdf`).
2. Load policy via `load_policy()` (honoring `BOOK_TO_SKILL_REMOTE_POLICY` env JSON/path; defaults: `enabled_providers=["*"]`, `blocked_providers=[]`, `require_explicit_confirmation=True`, `default_publish_visibility="private"`, `allow_public_publish=False`, `warn_mcp_temporary_cache=True`).
3. Verify the active provider with `check_provider_allowed(provider, policy)`. If disallowed, stop and report the reason.
4. If the user ran bare `/book-to-skill search` without a `<query>`, ask what book, author, ISBN, or DOI they want to search for (with an example such as `Pro Git` or `Think Python`) instead of throwing a syntax error.

---

## Setup — Installing & Configuring an MCP Book Provider (Opt-in)

Only enter this section when the user explicitly confirms they want help installing or configuring `libgen-mcp` (`github.com/jmrplens/libgen-mcp`). **Never install packages or modify host MCP configuration files without explicit user consent.**

1. **Probe available local runtimes** (`command -v docker npx npm brew go winget` as applicable) and recommend the cleanest option already available on the user's system:
   - **Docker:** `{"command": "docker", "args": ["run", "-i", "--rm", "ghcr.io/jmrplens/libgen-mcp:latest"]}`
   - **Node / NPX:** `{"command": "npx", "args": ["-y", "@jmrp.io/libgen-mcp"]}` (or install CLI with `npm install -g @jmrp.io/libgen-mcp`)
   - **Homebrew (macOS/Linux):** `brew install jmrplens/tap/libgen-mcp` → `{"command": "libgen-mcp", "args": []}`
   - **Go:** `go install github.com/jmrplens/libgen-mcp@latest` → `{"command": "libgen-mcp", "args": []}`
   - **WinGet (Windows):** `winget install -e --id jmrplens.libgen-mcp` → `{"command": "libgen-mcp", "args": []}`
2. **Confirm method and host config path with the user**, then merge the `"libgen-mcp"` entry safely into the active host's MCP configuration **without overwriting existing MCP servers**:
   - **Antigravity (`agy`):** `~/.gemini/config/mcp_config.json` (`mcpServers.libgen-mcp`)
   - **Claude Code:** `claude mcp add libgen-mcp ...` or `~/.claude.json` (`mcpServers.libgen-mcp`)
   - **GitHub Copilot CLI:** `~/.copilot/mcp-config.json` (`mcpServers.libgen-mcp`)
   - **OpenAI Codex:** `~/.codex/config.toml` (`[mcp_servers.libgen-mcp]`)
   - **OpenCode:** `~/.config/opencode/opencode.json` (`mcp.libgen-mcp`)
3. **Reload & verify:** Report the exact config path updated, note that other configured servers were preserved, and ask the user to start a **new session** so the host loads the MCP tools, then run `/book-to-skill search "Pro Git"`.

---

## Step R1 — Discovery (`search` -> `get_details` -> Explicit Selection)

When calling Python helpers (`book_to_skill.remote.*`), run via `PYTHONPATH=<skill-root>` (for example `~/.agents/skills/book-to-skill`) rather than guessing package paths.

1. **Search:** Invoke MCP `search` with `<query>` (title, author, ISBN, or DOI). When the provider is `libgen-mcp`:
   - Pass `"extra_sources": "always"` so keyless `open_access` results (OAPEN, arXiv, OpenAlex, Europe PMC, Crossref, Gutenberg, RFC, NIST) are returned alongside catalog results.
   - Pass `"topics": ["nonfiction"]` for general technical/non-fiction books (omit or adjust if the user explicitly asks for papers, standards, or fiction) to avoid noisy comics/magazine hits.
2. **Normalize & group duplicates:** Pass raw results (the full dict including `open_access`, or list) to `normalize_search_results(raw_results, provider=provider)`, then `group_duplicate_editions(candidates)` to surface `open_access` copies clearly and group works sharing `dedup_key`.
3. **Require explicit selection:** Render the numbered selection summary with `format_candidate_selection_table(grouped)` and ask the user to pick an exact candidate/edition number.
   - Never silently auto-select when candidates or multiple editions exist.
   - If zero results match, offer to refine the query or switch to a local file.
4. **Inspect details:** Call MCP `get_details` on the selected candidate and pass the response through `normalize_work_details(raw_details, provider=provider)` to confirm full metadata, identifiers (`isbn`, `doi`), `access_info`, and `license_info`. If the selected candidate has a verified `doi` from an open-access provider, prefer `read(doi=...)` over `read(md5=...)` so retrieval avoids unstable `md5` mirrors.

---

## Step R2 — Copyright, Access & Temporary-Cache Confirmation Gate

Before calling MCP `read` for the first time, generate and display the mandatory confirmation notice with `build_access_copyright_notice(candidate, policy)`, which includes:

1. **Work & source identity:** Provider/source name, title, authors, edition, and identifiers (ISBN/DOI).
2. **Access & license info:** Known `access_info` and `license_info` (or `"unknown"` when the provider reports none).
3. **Copyright notice (mandatory):** Explicitly warn the user that **user confirmation does not equal copyright-holder authorization** — confirming to proceed reflects only the user's own access/use basis and does not grant redistribution rights or copyright-holder permission.
4. **Temporary-cache & transmission notice (mandatory):** Explicitly warn the user that invoking MCP `read` may cache book text temporarily on the MCP server and transmits read text chunks to the host model context for synthesis.

**Hard gate:** Pass the user's reply to `verify_user_confirmation(reply, candidate, policy)`. Never infer consent from the initial `search` command or an ambiguous/empty reply. If `verify_user_confirmation(...)` returns `False`, stop without calling `read`.

---

## Step R3 — Purpose, Destination & Checkpoint Setup

1. Gather `BOOK_TYPE` (`technical` vs `text`, Step 1.5) and `DEPTH` (`reference` vs `study`, Step 4), unless already specified.
2. Resolve `SKILLS_HOME` and `SKILL_NAME` per Step 5, applying the Step 0 re-run guard if `<skill_name>` already exists.
3. Create `$SKILLS_HOME/<skill_name>/chapters/` (Step 6).
4. Initialize a private per-run checkpoint `workdir` (`chmod 0700`, symlink-checked) and persist `remote_session.json` using `init_remote_session(...)` and `save_remote_session(session, workdir)`.
   - To resume an interrupted run, call `load_remote_session(workdir)` and iterate only `pending_chapters(session)` (skipping chapters already marked `"done"`).
   - `remote_session.json` rejects symlinks and forbids prose keys (`text`, `raw_text`, `content`, `body`, `full_text`, `chunks`, `pages`, `excerpt`, etc.) — **zero raw book prose is stored**.

---

## Step R4 — Outline & Incremental Chapter Synthesis (`read(outline)` -> `read(section)` / `read(cursor)`)

### 1. Obtain Outline or Activate Sequential Fallback
- Call MCP `read` in `"outline"` mode (`read(outline)`) and normalize via `parse_outline_response(raw_outline)` -> `(outline_mode, chapters)`.
- **Sequential fallback:** When the outline is missing, empty, or unreliable, `parse_outline_response()` returns `outline_mode="sequential_fallback"`. Inform the user explicitly that chapter boundaries are sequential/inferred rather than outline-verified and paginate sequentially with `read(cursor)`.

### 2. Incremental Chapter Loop
For each chapter returned by `pending_chapters(session)`:

1. **Read & paginate safely:** Call MCP `read(section)` (or `read(cursor)` in sequential mode) page by page, processing each page through `process_section_page(raw_page, seen_cursors=seen_cursors, max_cursors_per_section=...)` or reducing the chapter's pages via `read_section_from_pages(...)`.
   - Enforces `max_cursors_per_section` (default `100`) and `max_total_requests` (default `1000`).
   - Detects infinite cursor loops (`next_cursor in seen_cursors`) and immediately stops with `status="incomplete"` and an explicit `error_reason`.
2. **Sanitize before synthesis:** `sanitize_remote_chunk()` / `process_section_page()` automatically runs `sanitize_extracted_text()` on every chunk before synthesis and tracks `sanitized_removed_count`.
3. **Synthesize chapter file:** Write `$SKILLS_HOME/<skill_name>/chapters/ch<NN>-<slug>.md` using the Step 7 structure and adaptive token budget (`BOOK_TYPE` × `DEPTH`).
4. **Discard raw fragments immediately:** Once the chapter summary file is written, drop the raw chapter text and `chunks` from working memory/scratch. Never save `full_text.txt`, never keep raw excerpts on disk, and never copy raw prose verbatim.
5. **Checkpoint atomically:** Record progress via `update_chapter_progress(session, section_id, status=..., next_cursor=..., chunks_read=..., sanitized_removed_count=..., truncated=..., error_reason=...)` and persist via `save_remote_session(session, workdir)`.

### 3. Incomplete, Truncated, or Unreachable Remote Sources (Explicit Warning Rule)
- **Upstream mirror failures / anti-bot challenges:** If MCP `read(md5=...)` fails across upstream mirrors (e.g., `HTTP 500`, expired mirror HTML, or a browser challenge/CAPTCHA), **never attempt to bypass anti-bot challenges**. Clearly explain that the external mirror servers failed outside `book-to-skill`, and offer actionable next steps: *(1)* try an `open_access` / `doi` edition if available (`read(doi=...)`), *(2)* try another edition, *(3)* configure an alternate mirror via `libgen-mcp -mirror <url>` if applicable, or *(4)* convert a local file directly.
- If `read_section_from_pages()` / `process_section_page()` reports `truncated: True` or `status` in `("incomplete", "failed")` (cursor loop, request cap, missing/empty section):
  - Keep the chapter marked `incomplete` or `failed` with its `error_reason` in `remote_session.json`.
  - Add an **explicit incomplete/truncated warning** at the top of that chapter file (if partially synthesized) and in `Scope & Limits` / Step 10 report.
  - Never present partial or truncated output as complete.

---

## Step R5 — Consolidated Supporting Files, Master `SKILL.md`, Scan, Report & Publish

1. **Consolidated supporting files (Step 8):** Synthesize across the written `chapters/` files (never from stored raw prose):
   - `$SKILLS_HOME/<skill_name>/glossary.md` (alphabetized key terms, max 1,500 tokens)
   - `$SKILLS_HOME/<skill_name>/patterns.md` (techniques & design patterns, max 2,000 tokens)
   - `$SKILLS_HOME/<skill_name>/cheatsheet.md` (decision rules, trade-offs, thresholds, smells, max 1,200 tokens)
2. **Coverage & provenance metadata (Contract D):**
   - Compute `coverage = build_coverage_report(session)` (yielding `chapters_total`, `chapters_done`, `chapters_incomplete`, `chapters_failed`, `missing_sections`, `truncated_sections`, `completeness_status` in `{"complete", "partial", "degraded"}`, and `warnings`).
   - Compute `provenance = build_remote_provenance(candidate, session, policy, coverage=coverage)` (guaranteed free of raw prose; `storage_mode="incremental_ephemeral_no_full_text"`).
   - Render Markdown with `render_provenance_markdown(provenance)` (and `format_coverage_summary(coverage)`).
3. **Master `SKILL.md` (Step 9):** Generate `$SKILLS_HOME/<skill_name>/SKILL.md` under the 4,000-token budget with Core Frameworks & Mental Models, Chapter Index, Topic Index, Supporting Files (do **not** add a `full_text.txt` line, since Mode 2 stores no raw book file), and `## Scope & Limits` containing the rendered `render_provenance_markdown(provenance)` block.
4. **Security & skill validation scan (Step 9.5):**
   - Run `tools/scan_generated_skill.py "$SKILLS_HOME/<skill_name>"` before reporting success or publishing. If it exits non-zero, stop and ask a human to review findings.
   - Optionally validate the generated `SKILL.md` with `tools/validate_skill.py "$SKILLS_HOME/<skill_name>/SKILL.md"`.
5. **Cleanup & report (Step 10):**
   - Create and verify the Claude Code symlink when `SKILLS_HOME` is `~/.agents/skills` (per Step 10).
   - Remove the temporary checkpoint `workdir` once `completeness_status == "complete"`; if `"partial"` or `"degraded"`, retain or inform the user of the `workdir` path so they can resume or discard it.
   - Print the Step 10 summary together with `format_coverage_summary(coverage)` and `render_provenance_markdown(provenance)`.
6. **Private-by-default publish gate (Step 11):**
   - Offer publishing once only if the Step 9.5 scan passed.
   - Enforce both the Step 11 visibility gate and `resolve_publish_visibility(requested, policy)`: `gh repo create` MUST default to `--private`, and `--public` is permitted **only** when the user answers the separate closed visibility question with the bare word `public` **and** `policy["allow_public_publish"]` is `True` and the copyright gate confirms authorization. Third-party copyrighted books retrieved via MCP **must stay private**.
